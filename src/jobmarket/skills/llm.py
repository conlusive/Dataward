"""Method B: ask an LLM which skills a vacancy names.

One small client speaks the OpenAI-compatible ``/chat/completions`` protocol, which OpenAI, Gemini
(compatibility endpoint) and Ollama all offer, so changing provider is a matter of environment
variables, not code. The reply must be JSON that validates against ``ExtractionResult``; a reply
that does not is asked for again with the error attached, then reported as a failure.
"""

import asyncio
import json
import os
import time
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Protocol

import httpx
import yaml
from pydantic import BaseModel, Field, ValidationError

PROMPT_DIR = Path(__file__).with_name("prompts")
PRICES_FILE = Path(__file__).with_name("llm_prices.yaml")
DEFAULT_PROMPT_VERSION = "extract_v1"
DEFAULT_MODEL = "gpt-4o-mini"
MAX_DESCRIPTION_CHARS = 6000  # about 1500 tokens: enough for any real requirements list
MAX_SKILLS = 60

Sleep = Callable[[float], Awaitable[None]]

RATE_LIMIT_WAIT_S = 15.0  # per attempt, when a 429 does not say how long to wait
MAX_RETRY_AFTER_S = 120.0


class RateLimiter:
    """Spaces request starts at least ``60 / rpm`` seconds apart, whatever the concurrency.

    A free tier allows a few requests a minute; asking politely is cheaper than being refused and
    waiting. Each caller reserves the next free slot and sleeps until it.
    """

    def __init__(
        self,
        rpm: float,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        if rpm <= 0:
            raise ValueError("rpm must be positive")
        self._interval = 60.0 / rpm
        self._clock, self._sleep = clock, sleep
        self._next = 0.0
        self._lock = asyncio.Lock()

    async def wait(self) -> None:
        async with self._lock:
            now = self._clock()
            start = max(now, self._next)
            self._next = start + self._interval
        if start > now:
            await self._sleep(start - now)


def _retry_after(response: httpx.Response, attempt: int) -> float:
    """How long to wait after a 429: what the server asks for, else a patient wait that grows."""
    asked = response.headers.get("retry-after", "")
    try:
        return min(max(float(asked), 1.0), MAX_RETRY_AFTER_S)
    except ValueError:
        return RATE_LIMIT_WAIT_S * attempt


class ExtractedSkill(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    importance: Literal["required", "nice"] = "required"


class ExtractionResult(BaseModel):
    skills: list[ExtractedSkill] = Field(default_factory=list, max_length=MAX_SKILLS * 2)


class LlmError(Exception):
    """The model could not be reached or kept answering with unusable output."""


@dataclass(frozen=True)
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0


@dataclass(frozen=True)
class Reply:
    content: str
    usage: Usage


class LlmClient(Protocol):
    model: str

    async def complete(self, system: str, user: str) -> Reply: ...


@dataclass(frozen=True)
class Extraction:
    result: ExtractionResult
    raw: str  # the JSON text exactly as the model returned it
    usage: Usage


def load_prompt(version: str = DEFAULT_PROMPT_VERSION) -> str:
    return (PROMPT_DIR / f"{version}.md").read_text(encoding="utf-8").strip()


def user_message(title: str, description: str) -> str:
    return f"Title: {title}\n\nDescription:\n{description[:MAX_DESCRIPTION_CHARS]}"


def estimate_cost(model: str, usage: Usage, prices_file: Path = PRICES_FILE) -> float:
    """USD for ``usage`` according to llm_prices.yaml; 0 for models that are not listed."""
    prices = yaml.safe_load(prices_file.read_text(encoding="utf-8"))["models"].get(
        model.split("/")[-1]
    )
    if prices is None:
        return 0.0
    spent = usage.prompt_tokens * float(prices["input"]) + usage.completion_tokens * float(
        prices["output"]
    )
    return spent / 1e6


class OpenAICompatibleClient:
    """Chat-completions client with JSON output, temperature 0 and retries on 429/5xx."""

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        api_key: str | None = None,
        client: httpx.AsyncClient | None = None,
        max_attempts: int = 4,
        sleep: Sleep = asyncio.sleep,
        limiter: RateLimiter | None = None,
    ) -> None:
        self._limiter = limiter
        self.model = model
        self._url = base_url.rstrip("/") + "/chat/completions"
        self._headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._client = client or httpx.AsyncClient(timeout=60.0)
        self._max_attempts = max_attempts
        self._sleep = sleep

    async def complete(self, system: str, user: str) -> Reply:
        body = {
            "model": self.model.split("/", 1)[-1]
            if self.model.startswith(("gemini/", "ollama/"))
            else self.model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        last_problem = "no attempt made"
        pause = 0.0
        for attempt in range(1, self._max_attempts + 1):
            pause = 2.0**attempt
            if self._limiter is not None:
                await self._limiter.wait()
            try:
                response = await self._client.post(self._url, json=body, headers=self._headers)
            except httpx.TransportError as exc:
                last_problem = repr(exc)
            else:
                if response.status_code == 429:
                    last_problem = "HTTP 429 (rate limit or daily quota)"
                    pause = _retry_after(response, attempt)
                elif response.status_code >= 500:
                    last_problem = f"HTTP {response.status_code}"
                elif response.status_code >= 400:
                    raise LlmError(f"HTTP {response.status_code}: {response.text[:300]}")
                else:
                    return _reply(response.json())
            if attempt < self._max_attempts:
                await self._sleep(pause)
        raise LlmError(f"giving up after {self._max_attempts} attempts: {last_problem}")


def _reply(payload: Any) -> Reply:
    """The text and token usage of a chat-completions response; anything else is an LlmError."""
    try:
        content = payload["choices"][0]["message"]["content"]
        usage = payload.get("usage") or {}
        return Reply(
            content=str(content),
            usage=Usage(int(usage.get("prompt_tokens", 0)), int(usage.get("completion_tokens", 0))),
        )
    except (KeyError, IndexError, TypeError, ValueError, AttributeError) as exc:
        raise LlmError(f"unexpected response shape: {exc!r}") from exc


def client_from_env(
    env: Mapping[str, str] | None = None, *, rpm: float | None = None
) -> OpenAICompatibleClient:
    """Pick the provider from LLM_MODEL: ``gemini/...``, ``ollama/...`` or an OpenAI model name.

    ``rpm`` caps the requests per minute (for a free tier); None means no cap.
    """
    env = os.environ if env is None else env
    limiter = RateLimiter(rpm) if rpm else None
    model = env.get("LLM_MODEL") or DEFAULT_MODEL
    if model.startswith("gemini/"):
        key = env.get("GEMINI_API_KEY")
        if not key:
            raise LlmError("GEMINI_API_KEY is not set (needed for a gemini/... model)")
        return OpenAICompatibleClient(
            base_url="https://generativelanguage.googleapis.com/v1beta/openai",
            model=model,
            api_key=key,
            limiter=limiter,
        )
    if model.startswith("ollama/"):
        base = env.get("OLLAMA_BASE_URL") or "http://localhost:11434"
        return OpenAICompatibleClient(
            base_url=base.rstrip("/") + "/v1", model=model, limiter=limiter
        )
    key = env.get("OPENAI_API_KEY")
    if not key:
        raise LlmError("OPENAI_API_KEY is not set (needed for an OpenAI model)")
    return OpenAICompatibleClient(
        base_url="https://api.openai.com/v1", model=model, api_key=key, limiter=limiter
    )


async def extract(
    client: LlmClient, title: str, description: str, *, prompt: str, retries: int = 2
) -> Extraction:
    """Ask for the skills of one vacancy; unusable JSON is retried with the problem pointed out."""
    user = user_message(title, description)
    usage = Usage()
    problem = ""
    for _ in range(retries + 1):
        message = user
        if problem:
            message += (
                f"\n\nYour previous answer was invalid ({problem}). Answer with valid JSON only."
            )
        reply = await client.complete(prompt, message)
        usage = Usage(
            usage.prompt_tokens + reply.usage.prompt_tokens,
            usage.completion_tokens + reply.usage.completion_tokens,
        )
        try:
            return Extraction(
                ExtractionResult.model_validate(json.loads(reply.content)), reply.content, usage
            )
        except (json.JSONDecodeError, ValidationError) as exc:
            problem = str(exc).splitlines()[0][:200]
    raise LlmError(f"the model kept returning invalid JSON: {problem}")
