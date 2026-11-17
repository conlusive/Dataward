from pathlib import Path

from jobmarket import dashboard_head as head

ROOT = Path(__file__).parent.parent

# the shape of Streamlit's own index.html where it matters here
STREAMLIT_PAGE = """<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <link rel="shortcut icon" href="./favicon.png" />
    <title>Streamlit</title>
  </head>
  <body>
    <noscript>You need to enable JavaScript to run this app.</noscript>
    <div id="root"></div>
  </body>
</html>
"""


def _patched(version: str = "abc12345") -> str:
    return head.patch(STREAMLIT_PAGE, site_url="https://example.org/", version=version)


def test_the_page_says_what_it_is_before_any_script_runs() -> None:
    page = _patched()

    assert '<html lang="uk">' in page and "<title>Streamlit</title>" not in page
    assert f"<title>{head.TITLE}</title>" in page
    assert 'name="description"' in page and 'rel="canonical" href="https://example.org/"' in page
    assert 'property="og:title"' in page and 'name="twitter:card"' in page
    assert '"@type": "WebApplication"' in page and '"inLanguage": "uk"' in page


def test_streamlits_crown_is_gone_and_the_icon_has_an_address_with_a_hash() -> None:
    page = _patched("abc12345")

    assert 'href="./favicon.png"' not in page and "shortcut icon" not in page
    assert 'rel="icon"' in page and "./app/static/favicon.png?v=abc12345" in page
    assert "./app/static/apple-touch-icon.png?v=abc12345" in page
    # a different icon is a different address, which a browser fetches again
    assert "?v=zzz99999" in _patched("zzz99999") and "?v=abc12345" not in _patched("zzz99999")


def test_a_reader_without_javascript_gets_text_and_links_to_the_pages() -> None:
    page = _patched()

    assert "You need to enable JavaScript" not in page
    assert "<noscript><h1>Dataward</h1>" in page
    for _, path in head.PAGES:
        assert f'href="https://example.org/{path}"' in page


def test_patching_twice_changes_nothing_more() -> None:
    once = _patched()

    assert head.patch(once, site_url="https://other.example", version="ffffffff") == once


def test_the_hash_follows_the_committed_icon(tmp_path: Path) -> None:
    (tmp_path / "favicon.png").write_bytes(b"one")
    first = head.icon_version(tmp_path)
    (tmp_path / "favicon.png").write_bytes(b"two")

    assert head.icon_version(tmp_path) != first and len(first) == 8


def test_the_image_build_writes_the_head_and_the_app_uses_the_same_title() -> None:
    dockerfile = (ROOT / "Dockerfile.dashboard").read_text(encoding="utf-8")
    app = (ROOT / "dashboard" / "app.py").read_text(encoding="utf-8")

    assert "RUN python -m jobmarket.dashboard_head" in dockerfile
    assert "page_title=head.TITLE" in app  # one title: the tab, the page and the preview agree
