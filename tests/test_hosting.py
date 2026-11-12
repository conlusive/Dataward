"""The files that put the dashboard on a public host stay consistent with each other."""

import re
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent


def _service() -> dict[str, Any]:
    blueprint = yaml.safe_load((ROOT / "render.yaml").read_text(encoding="utf-8"))
    (service,) = blueprint["services"]
    assert isinstance(service, dict)
    return service


def test_the_blueprint_is_a_docker_web_service_with_a_health_check() -> None:
    service = _service()

    assert service["type"] == "web" and service["runtime"] == "docker"
    assert service["dockerfilePath"] == "./Dockerfile.dashboard"
    assert service["healthCheckPath"] == "/_stcore/health"


def test_a_public_host_reads_the_public_export_and_keeps_profiles_per_visitor() -> None:
    env = {item["key"]: item["value"] for item in _service()["envVars"]}

    assert env["DASHBOARD_PROFILE"] == "session"  # one file for every visitor would be shared
    assert env["DASHBOARD_DATA_URL"].endswith("/refs/heads/data")  # the public copy, not main


def test_the_image_compiles_its_bytecode_and_bakes_the_data_in() -> None:
    dockerfile = (ROOT / "Dockerfile.dashboard").read_text(encoding="utf-8")

    # the server runs as `app` and cannot write .pyc files into root's site-packages
    assert "UV_COMPILE_BYTECODE=1" in dockerfile
    assert "python -m compileall -q src dashboard" in dockerfile
    assert "ARG DASHBOARD_DATA_URL" in dockerfile  # Render passes its env vars to the build
    bake = dockerfile.index("python -m jobmarket.dashboard_sync")
    assert bake < dockerfile.index("chown -R app:app") < dockerfile.index("USER app")


def test_a_start_asks_the_sync_whether_the_data_is_stale_and_does_not_watch_files() -> None:
    script = (ROOT / "scripts" / "dashboard-start.sh").read_text(encoding="utf-8")

    # no shell test for the file: the sync itself decides (missing or stale: fetch; fresh: start)
    assert "python -m jobmarket.dashboard_sync ||" in script and "if [ ! -f" not in script
    assert "--server.fileWatcherType=none" in script


def test_the_workflow_runs_the_full_sweep_nightly_and_the_light_flow_every_hour() -> None:
    workflow = (ROOT / ".github" / "workflows" / "pipeline-daily.yml").read_text(encoding="utf-8")

    assert 'cron: "0 4 * * *"' in workflow and 'cron: "17 * * * *"' in workflow
    assert "github.event.schedule == '17 * * * *'" in workflow  # which schedule fired decides
    assert "'pipeline-fresh' || 'pipeline'" in workflow and 'make "$FLOW_TARGET"' in workflow
    assert "cancel-in-progress: false" in workflow  # runs queue: two would race on bronze


def test_the_image_starts_through_the_script_that_fetches_data_and_honours_port() -> None:
    dockerfile = (ROOT / "Dockerfile.dashboard").read_text(encoding="utf-8")
    script = (ROOT / "scripts" / "dashboard-start.sh").read_text(encoding="utf-8")

    assert "COPY scripts/dashboard-start.sh" in dockerfile
    assert 'CMD ["sh", "scripts/dashboard-start.sh"]' in dockerfile
    assert "jobmarket.dashboard_sync" in script
    assert '--server.port="${PORT:-8501}"' in script  # Render sets $PORT; locally it is 8501


def test_only_the_public_copy_is_published_and_by_a_job_of_its_own() -> None:
    workflow = yaml.safe_load(
        (ROOT / ".github" / "workflows" / "pipeline-daily.yml").read_text(encoding="utf-8")
    )
    publish = workflow["jobs"]["publish-data"]
    text = (ROOT / ".github" / "workflows" / "pipeline-daily.yml").read_text(encoding="utf-8")

    assert workflow["permissions"] == {"contents": "read"}  # the scraper never holds a write token
    assert publish["permissions"] == {"contents": "write"} and publish["needs"] == "scrape"
    downloaded = [
        s["with"]["name"] for s in publish["steps"] if "download-artifact" in s.get("uses", "")
    ]
    assert downloaded == ["gold-export"]  # the artifact is the stripped copy (test_export.py)
    assert not re.search(r"data/export\b(?!_public)", text[text.index("publish-data:") :])


def test_a_merge_can_ask_the_host_to_deploy_without_leaking_the_hook() -> None:
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    job = ci[ci.index("  deploy:") :]

    assert "needs: [checks, dashboard-image]" in job  # never deploy what did not pass
    assert "github.ref == 'refs/heads/main'" in job
    assert "secrets.RENDER_DEPLOY_HOOK_URL" in job and 'echo "$HOOK"' not in job
    assert "-o /dev/null" in job  # the answer names the deploy; keep it out of a public log
