import re
import shutil
import subprocess
from pathlib import Path

import pytest

from jobmarket import dashboard_icon as icon
from jobmarket import dashboard_logo as logo

ROOT = Path(__file__).resolve().parent.parent


def test_the_script_replaces_every_icon_link_that_is_not_its_own() -> None:
    code = icon.script()

    assert (
        f"{icon.STATIC_URL}/" in code and "favicon.png" in code and "apple-touch-icon.png" in code
    )
    assert "link.remove()" in code and "dwIcon" in code  # Streamlit's links go, ours stay
    assert "MutationObserver" in code  # Streamlit adds its own link again after a rerun
    assert "window.__dwIcon" in code  # once per page load


def test_a_changed_icon_is_a_new_address(tmp_path: Path) -> None:
    (tmp_path / "favicon.png").write_bytes(b"one")
    first = icon.version(tmp_path)
    (tmp_path / "favicon.png").write_bytes(b"two")

    assert icon.version(tmp_path) != first and re.fullmatch(r"[0-9a-f]{8}", first)
    assert f"?v={icon.version()}" in icon.script()  # the real icon's hash is in the script


def test_the_apple_touch_icon_has_the_size_the_script_announces() -> None:
    pil = pytest.importorskip("PIL.Image")

    image = pil.open(logo.STATIC / "apple-touch-icon.png")

    assert image.size == (logo.APPLE_TOUCH_SIZE, logo.APPLE_TOUCH_SIZE)
    assert f"{logo.APPLE_TOUCH_SIZE}x{logo.APPLE_TOUCH_SIZE}" in icon.script()
    assert f"{logo.FAVICON_SIZE}x{logo.FAVICON_SIZE}" in icon.script()  # a multiple of 48


def test_streamlit_serves_the_static_folder_and_no_longer_swaps_the_icon_itself() -> None:
    config = (ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8")
    app = (ROOT / "dashboard" / "app.py").read_text(encoding="utf-8")

    assert re.search(r"\[server\][^\[]*enableStaticServing = true", config)
    assert "page_icon" not in app  # its swap is a JPEG, and Safari ignores it anyway


def test_the_image_puts_our_icon_where_streamlits_own_favicon_is() -> None:
    dockerfile = (ROOT / "Dockerfile.dashboard").read_text(encoding="utf-8")

    assert "cp dashboard/static/favicon.png dashboard/static/favicon.ico" in dockerfile
    assert "apple-touch-icon.png" in dockerfile  # and the other names a browser asks for
    assert dockerfile.index("COPY dashboard ./dashboard") < dockerfile.index("cp dashboard/static")
    assert dockerfile.index("cp dashboard/static") < dockerfile.index(
        "USER app"
    )  # root can write it


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_the_icon_script_is_valid_javascript(tmp_path: Path) -> None:
    body = icon.script().removeprefix("<script>").removesuffix("</script>")
    source = tmp_path / "icon.js"
    source.write_text(body, encoding="utf-8")

    result = subprocess.run(["node", "--check", str(source)], capture_output=True, text=True)

    assert result.returncode == 0, result.stderr
