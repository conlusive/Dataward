"""Start the next hourly run from the end of this one, with the token the run already has.

GitHub starts a ``schedule`` when it has room, and for a small public repository that is every
four to six hours, not every hour. A workflow may start another one with ``workflow_dispatch`` using
its own ``GITHUB_TOKEN`` (the one exception to "events made by this token start nothing"), so the
last job of a run waits for the next ``:17`` and starts the next run itself. The chain needs no
outside scheduler and no stored secret; the hourly ``schedule`` stays as a net that starts a chain
again if it ever breaks.

Only the newest run carries the chain on: a run that finds a newer one (a schedule fired while it
waited) lets go, so chains merge instead of multiplying. The full sweep is started when none has
succeeded for a day. While it waits the job also asks the hosted site for its health every few
minutes: a free Render service falls asleep after 15 idle minutes and a visitor then waits a minute
for it to wake, so a visit every few minutes keeps it awake. The standard library only: this runs in
a job that installs nothing.
"""

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Final, Literal

WORKFLOW: Final = "pipeline-daily.yml"
TARGET_MINUTE: Final = 17  # the minute of the hourly schedule: the chain keeps the same rhythm
MIN_WAIT: Final = timedelta(minutes=10)  # never start sooner than this after a run ends
SWEEP_EVERY: Final = timedelta(hours=20)  # a full sweep succeeded within this: none is due
SWEEP_RETRY_AFTER: Final = timedelta(hours=6)  # a sweep started within this: do not start another
SITE_URL: Final = os.environ.get("DASHBOARD_SITE_URL") or "https://dataward.onrender.com"
PING_EVERY: Final = timedelta(minutes=8)  # under the 15 minutes after which a free service sleeps

Flow = Literal["daily", "fresh"]


@dataclass(frozen=True)
class Run:
    """One run of the workflow; ``title`` is its ``run-name``: ``daily`` or ``fresh``."""

    id: int
    created_at: datetime
    title: str
    status: str
    conclusion: str | None


def next_start(now: datetime) -> datetime:
    """The next ``HH:17`` that is at least ``MIN_WAIT`` away."""
    candidate = now.replace(minute=TARGET_MINUTE, second=0, microsecond=0)
    while candidate < now + MIN_WAIT:
        candidate += timedelta(hours=1)
    return candidate


def superseded(mine: Run, runs: Sequence[Run]) -> bool:
    """Is there a run newer than this one? Then that one carries the chain on."""
    return any(run.id != mine.id and run.created_at > mine.created_at for run in runs)


def choose_flow(now: datetime, runs: Sequence[Run]) -> Flow:
    """``daily`` if no full sweep succeeded in a day and none started lately, else ``fresh``."""
    sweeps = [run for run in runs if run.title == "daily"]
    done = any(run.conclusion == "success" and now - run.created_at < SWEEP_EVERY for run in sweeps)
    tried = any(now - run.created_at < SWEEP_RETRY_AFTER for run in sweeps)
    return "fresh" if done or tried else "daily"


def _gh(*args: str) -> str:
    return subprocess.run(["gh", *args], capture_output=True, text=True, check=True).stdout


def fetch_runs() -> list[Run]:
    """The latest runs of the workflow, newest first."""
    fields = "databaseId,createdAt,displayTitle,status,conclusion"
    raw = json.loads(_gh("run", "list", "--workflow", WORKFLOW, "--limit", "100", "--json", fields))
    return [
        Run(
            id=int(item["databaseId"]),
            created_at=datetime.fromisoformat(item["createdAt"].replace("Z", "+00:00")),
            title=item["displayTitle"],
            status=item["status"],
            conclusion=item["conclusion"] or None,
        )
        for item in raw
    ]


def ping(url: str = SITE_URL) -> None:
    """Ask the site whether it is well; this is also what wakes it. A failure is only logged."""
    try:
        with urllib.request.urlopen(f"{url.rstrip('/')}/_stcore/health", timeout=60) as reply:  # noqa: S310
            print(f"site answered {reply.status}")
    except (urllib.error.URLError, OSError) as error:
        print(f"site did not answer: {error}")


def _find(runs: Sequence[Run], run_id: int) -> Run | None:
    return next((run for run in runs if run.id == run_id), None)


def main() -> int:
    run_id = int(os.environ["RUN_ID"])
    mine = _find(fetch_runs(), run_id)
    if mine is None:
        print(f"run {run_id} is not in the list of runs: nothing to carry on")
        return 0
    start = next_start(datetime.now(UTC))
    print(f"the next run is due at {start:%H:%M} UTC")
    last_ping: datetime | None = None
    while (left := (start - datetime.now(UTC)).total_seconds()) > 0:
        if last_ping is None or datetime.now(UTC) - last_ping >= PING_EVERY:
            ping()
            last_ping = datetime.now(UTC)
        time.sleep(min(left, 60))
    runs = fetch_runs()
    if superseded(mine, runs):
        print("a newer run exists: it carries the chain on")
        return 0
    flow = choose_flow(datetime.now(UTC), runs)
    print(f"starting the {flow} flow")
    _gh("workflow", "run", WORKFLOW, "--ref", "main", "-f", f"flow={flow}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
