import io
import re
from pathlib import Path

import pytest

from jobmarket import dashboard_logo as logo
from jobmarket import dashboard_theme as t


def _lit(svg: str) -> int:
    return len(re.findall(r"h1v1h-1z", svg))


def test_the_wordmark_spells_the_name_in_a_pixel_grid() -> None:
    svg = logo.wordmark_svg()

    assert svg.startswith("<svg") and 'aria-label="Dataward"' in svg
    assert 'shape-rendering="crispEdges"' in svg  # no blurred pixels
    assert t.ACCENT in svg and t.INK in svg  # DATA in the accent, WARD in the text colour


def test_every_letter_is_a_5_by_7_grid_of_pixels() -> None:
    for letter, rows in logo.GLYPHS.items():
        assert len(rows) == logo.HEIGHT and all(len(r) == logo.WIDTH for r in rows), letter
        assert set("".join(rows)) <= {"0", "1"}


def test_the_wordmark_has_a_shadow_pixel_for_every_lit_pixel() -> None:
    svg = logo.wordmark_svg()
    shadow, accent, ink = (
        re.search(rf'fill="{colour}" d="([^"]+)"', svg).group(1)  # type: ignore[union-attr]
        for colour in (logo.SHADOW, t.ACCENT, t.INK)
    )

    assert _lit(shadow) == _lit(accent) + _lit(ink)


def test_the_letters_are_far_enough_apart_for_the_shadow_not_to_close_the_gap() -> None:
    assert logo.GAP >= 2


def test_the_full_stop_is_static_and_uses_the_second_chart_colour() -> None:
    for svg in (logo.wordmark_svg(), logo.icon_svg()):
        assert svg.count(f'fill="{t.SERIES[1]}"') == 1  # one stop ...
        assert "<animate" not in svg  # ... that does not blink


def test_the_emblem_is_three_rising_bars_on_the_bottom_row() -> None:
    cells = logo._emblem()

    assert len(cells) == sum(logo.BARS)
    heights = [sum(1 for x, _ in cells if x == col) for col in (0, 2, 4)]
    assert heights == sorted(heights) and heights[-1] == logo.HEIGHT
    assert all(y <= logo.HEIGHT - 1 for _, y in cells)


def test_a_name_with_a_letter_outside_the_table_is_refused() -> None:
    with pytest.raises(KeyError):
        logo.wordmark_svg("DATAX")


def test_the_committed_assets_are_what_the_generator_writes() -> None:
    assert (logo.STATIC / "logo.svg").read_text(encoding="utf-8") == logo.wordmark_svg()
    assert (logo.STATIC / "icon.svg").read_text(encoding="utf-8") == logo.icon_svg()


def test_the_favicon_is_a_square_png_in_the_dashboard_colours() -> None:
    pil = pytest.importorskip("PIL.Image")
    data = (logo.STATIC / "favicon.png").read_bytes()

    image = pil.open(io.BytesIO(data)).convert("RGB")

    assert image.size == (64, 64)
    colours = {colour for _, colour in image.getcolors()}
    hexes = {f"#{r:02X}{g:02X}{b:02X}" for r, g, b in colours}
    assert hexes == {t.BG, t.ACCENT, logo.DOT_COLOUR}


def test_the_assets_can_be_rewritten(tmp_path: Path) -> None:
    pytest.importorskip("PIL.Image")

    written = logo.write_assets(tmp_path)

    assert sorted(p.name for p in written) == [
        "apple-touch-icon.png", "favicon.png", "icon.svg", "logo.svg",
    ]  # fmt: skip
    assert (tmp_path / "logo.svg").read_text(encoding="utf-8") == logo.wordmark_svg()


def test_the_committed_png_icons_are_what_the_generator_writes() -> None:
    pytest.importorskip("PIL.Image")

    assert (logo.STATIC / "favicon.png").read_bytes() == logo.favicon_png()
    assert (logo.STATIC / "apple-touch-icon.png").read_bytes() == logo.favicon_png(
        logo.APPLE_TOUCH_SIZE
    )
