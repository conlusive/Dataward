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
