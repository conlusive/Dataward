"""Runtime settings read from environment variables (see .env.example)."""

import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_USER_AGENT = "jobmarket-research-bot (+https://github.com/conlusive/Dataward)"


@dataclass(frozen=True)
class Settings:
    bronze_dir: Path = Path("data/bronze")
    duckdb_path: Path = Path("data/jobmarket.duckdb")
    rate_limit_rps: float = 1.0
    user_agent: str = DEFAULT_USER_AGENT
    concurrency: int = 2
    max_attempts: int = 4
    retry_base_s: float = 1.0
    rate_limit_pause_s: float = 60.0
    request_timeout_s: float = 30.0
    # A vacancy page fetched within this many days is not downloaded again (interim until silver
    # can tell which vacancies are already known).
    detail_refresh_days: int = 7
    # Cap on listing pages per category/keyword; None means follow pagination to the end.
    max_list_pages: int | None = None

    @classmethod
    def from_env(cls) -> "Settings":
        defaults = cls()
        max_pages = os.environ.get("SCRAPE_MAX_LIST_PAGES")
        return cls(
            max_list_pages=int(max_pages) if max_pages else defaults.max_list_pages,
            bronze_dir=Path(os.environ.get("BRONZE_DIR") or defaults.bronze_dir),
            duckdb_path=Path(os.environ.get("DUCKDB_PATH") or defaults.duckdb_path),
            rate_limit_rps=float(
                os.environ.get("SCRAPE_RATE_LIMIT_RPS") or defaults.rate_limit_rps
            ),
            user_agent=os.environ.get("SCRAPE_USER_AGENT") or defaults.user_agent,
        )
