"""A short Telegram message about a run; does nothing unless the bot is set up in the env."""

import os

import httpx
from loguru import logger

API = "https://api.telegram.org"


def send_telegram(text: str, *, client: httpx.Client | None = None) -> bool:
    """Send ``text`` to the chat in TELEGRAM_CHAT_ID; False when not configured or not delivered.

    A notification must never fail a run, so errors are logged and swallowed. The token is read
    from the environment only and never logged.
    """
    token, chat_id = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return False
    owned = client is None
    http = client or httpx.Client(timeout=15)
    try:
        response = http.post(
            f"{API}/bot{token}/sendMessage", json={"chat_id": chat_id, "text": text}
        )
        response.raise_for_status()
    except httpx.HTTPError as error:
        # the exception text can contain the URL, which contains the token: log the type only
        logger.warning("telegram message was not delivered ({})", type(error).__name__)
        return False
    finally:
        if owned:
            http.close()
    return True
