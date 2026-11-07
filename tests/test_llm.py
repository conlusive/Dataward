import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from jobmarket.skills.llm import (
    ExtractionResult,
    LlmError,
    OpenAICompatibleClient,
    Reply,
    Usage,
    client_from_env,
    estimate_cost,
    extract,
    load_prompt,
    user_message,
)


def _answer(content: str, prompt: int = 100, completion: int = 20) -> dict[str, Any]:
    return {
        "choices": [{"message": {"content": content}}],
        "usage": {"prompt_tokens": prompt, "completion_tokens": completion},
    }


class Sleeps:
    def __init__(self) -> None:
        self.calls: list[float] = []

    async def __call__(self, seconds: float) -> None:
        self.calls.append(seconds)


def _client(
    handler: Any, *, model: str = "gpt-4o-mini", attempts: int = 4, sleeps: Sleeps | None = None
) -> OpenAICompatibleClient:
    return OpenAICompatibleClient(
        base_url="https://api.example.com/v1/",
        model=model,
        api_key="secret-key",
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        max_attempts=attempts,
        sleep=sleeps or Sleeps(),
    )


async def test_request_shape_and_reply_parsing() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=_answer('{"skills": []}', 321, 45))

    reply = await _client(handler).complete("SYSTEM", "USER")

    request = seen[0]
    body = json.loads(request.content)
    assert str(request.url) == "https://api.example.com/v1/chat/completions"
    assert request.headers["authorization"] == "Bearer secret-key"
    assert body["model"] == "gpt-4o-mini" and body["temperature"] == 0
    assert body["response_format"] == {"type": "json_object"}
    assert [m["role"] for m in body["messages"]] == ["system", "user"]
    assert reply == Reply('{"skills": []}', Usage(321, 45))


async def test_rate_limits_and_server_errors_are_retried_with_a_growing_pause() -> None:
    statuses = iter([429, 503, 200])
    sleeps = Sleeps()

    def handler(request: httpx.Request) -> httpx.Response:
        status = next(statuses)
        return httpx.Response(status, json=_answer("{}") if status == 200 else {})

    reply = await _client(handler, sleeps=sleeps).complete("s", "u")

    assert reply.content == "{}"
    assert sleeps.calls == [2.0, 4.0]


async def test_it_gives_up_after_the_last_attempt() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(500)

    with pytest.raises(LlmError, match="giving up after 3 attempts"):
        await _client(handler, attempts=3).complete("s", "u")
    assert calls == 3


async def test_a_client_error_is_not_retried() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(401, text="bad key")

    with pytest.raises(LlmError, match="HTTP 401"):
        await _client(handler).complete("s", "u")
    assert calls == 1


async def test_a_response_of_the_wrong_shape_is_an_error() -> None:
    with pytest.raises(LlmError, match="unexpected response shape"):
        await _client(lambda r: httpx.Response(200, json={"nope": 1})).complete("s", "u")


async def test_provider_prefixes_are_not_sent_to_the_provider() -> None:
    seen: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        return httpx.Response(200, json=_answer("{}"))

    await _client(handler, model="gemini/gemini-2.0-flash").complete("s", "u")
    await _client(handler, model="ollama/llama3.1").complete("s", "u")

    assert [body["model"] for body in seen] == ["gemini-2.0-flash", "llama3.1"]


def test_the_provider_comes_from_llm_model() -> None:
    openai = client_from_env({"OPENAI_API_KEY": "k"})
    gemini = client_from_env({"LLM_MODEL": "gemini/gemini-2.0-flash", "GEMINI_API_KEY": "g"})
    ollama = client_from_env(
        {"LLM_MODEL": "ollama/llama3.1", "OLLAMA_BASE_URL": "http://box:11434/"}
    )

    assert (
        openai.model == "gpt-4o-mini"
        and openai._url == "https://api.openai.com/v1/chat/completions"
    )
    assert gemini._url.startswith("https://generativelanguage.googleapis.com/v1beta/openai/")
    assert ollama._url == "http://box:11434/v1/chat/completions" and ollama._headers == {}


def test_a_missing_key_is_reported_by_name_not_value() -> None:
    with pytest.raises(LlmError, match="OPENAI_API_KEY"):
        client_from_env({})
    with pytest.raises(LlmError, match="GEMINI_API_KEY"):
        client_from_env({"LLM_MODEL": "gemini/x"})


class Scripted:
    model = "gpt-4o-mini"

    def __init__(self, *contents: str) -> None:
        self._contents = list(contents)
        self.messages: list[str] = []

    async def complete(self, system: str, user: str) -> Reply:
        self.messages.append(user)
        return Reply(self._contents.pop(0), Usage(100, 10))


async def test_invalid_json_is_asked_for_again_and_the_tokens_add_up() -> None:
    client = Scripted(
        "not json",
        '{"skills": [{"name": "Python", "importance": "oops"}]}',
        '{"skills": [{"name": "Python"}]}',
    )

    extraction = await extract(client, "Dev", "text", prompt="P")

    assert [(s.name, s.importance) for s in extraction.result.skills] == [("Python", "required")]
    assert extraction.usage == Usage(300, 30)
    assert (
        "previous answer was invalid" in client.messages[1]
        and "previous answer was invalid" in client.messages[2]
    )
    assert "previous answer was invalid" not in client.messages[0]


async def test_it_fails_when_the_model_never_returns_valid_json() -> None:
    with pytest.raises(LlmError, match="invalid JSON"):
        await extract(Scripted("x", "y", "z"), "Dev", "text", prompt="P")


def test_the_extraction_schema_ignores_extra_fields_and_rejects_bad_ones() -> None:
    ok = ExtractionResult.model_validate(
        {"skills": [{"name": "Go", "importance": "nice", "extra": 1}], "note": "x"}
    )
    assert ok.skills[0].importance == "nice"
    with pytest.raises(ValueError):
        ExtractionResult.model_validate({"skills": [{"name": ""}]})


def test_the_description_is_cut_to_keep_the_cost_bounded() -> None:
    assert len(user_message("T", "x" * 100_000)) < 6100
    assert "Title: Senior Dev" in user_message("Senior Dev", "text")


def test_the_prompt_is_versioned_and_non_empty() -> None:
    assert "JSON" in load_prompt("extract_v1") and "skills" in load_prompt("extract_v1")


def test_cost_comes_from_the_price_file_and_is_zero_for_unknown_models(tmp_path: Path) -> None:
    prices = tmp_path / "p.yaml"
    prices.write_text("models:\n  m: {input: 1.0, output: 2.0}\n", encoding="utf-8")
    usage = Usage(1_000_000, 500_000)

    assert estimate_cost("m", usage, prices) == 2.0
    assert estimate_cost("gemini/m", usage, prices) == 2.0  # the provider prefix is ignored
    assert estimate_cost("local-model", usage, prices) == 0.0
