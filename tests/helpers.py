import json
from pathlib import Path

import httpx

SAMPLES = Path(__file__).parent.parent / "data" / "bronze_sample"


class NoSleep:
    async def __call__(self, seconds: float) -> None:
        return None


def sample(relative: str) -> bytes:
    return (SAMPLES / relative).read_bytes()


def xhr_payload(*, last: bool) -> bytes:
    """The recorded DOU XHR response with a chosen ``last`` flag."""
    payload = json.loads(sample("dou/xhr_python_count20.json"))
    payload["last"] = last
    return json.dumps(payload).encode()


def robots_allow_all(request: httpx.Request) -> httpx.Response | None:
    if request.url.path == "/robots.txt":
        return httpx.Response(200, text="User-agent: *\nAllow: /\n")
    return None
