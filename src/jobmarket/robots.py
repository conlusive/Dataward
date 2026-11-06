"""robots.txt policy following RFC 9309: 4xx = allow all, 5xx / network failure = disallow all."""

from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import httpx

# A parsed robots.txt, or a blanket decision (True = allow all, False = disallow all).
_Rules = RobotFileParser | bool


class RobotsPolicy:
    def __init__(self, client: httpx.AsyncClient, user_agent: str) -> None:
        self._client = client
        self._user_agent = user_agent
        self._rules: dict[str, _Rules] = {}

    async def allowed(self, url: str) -> bool:
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        rules = self._rules.get(origin)
        if rules is None:
            rules = await self._load(origin)
            self._rules[origin] = rules
        if isinstance(rules, bool):
            return rules
        return rules.can_fetch(self._user_agent, url)

    async def _load(self, origin: str) -> _Rules:
        try:
            response = await self._client.get(f"{origin}/robots.txt")
        except httpx.HTTPError:
            return False
        if response.status_code == 200:
            parser = RobotFileParser()
            parser.parse(response.text.splitlines())
            return parser
        return 400 <= response.status_code < 500
