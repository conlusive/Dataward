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


def test_the_favicon_is_a_round_badge_a_multiple_of_48_px_in_the_brand_colours() -> None:
    pil = pytest.importorskip("PIL.Image")
    image = pil.open(io.BytesIO((logo.STATIC / "favicon.png").read_bytes())).convert("RGBA")

    assert image.size == (logo.FAVICON_SIZE,) * 2 and logo.FAVICON_SIZE % 48 == 0
    assert image.getpixel((0, 0))[3] == 0  # a corner is transparent: a circle in a tab
    centre = image.getpixel((logo.FAVICON_SIZE // 2, 6))[:3]  # on the disc, above the bars
    assert f"#{centre[0]:02X}{centre[1]:02X}{centre[2]:02X}" == t.ACCENT
    wanted = {t.BG, logo.DOT_COLOUR}
    found = {
        f"#{r:02X}{g:02X}{b:02X}" for n, (r, g, b, a) in image.getcolors(100000) if a and n > 50
    }
    assert wanted <= found  # the bars and the dot are drawn


def test_the_touch_icon_is_a_full_square_and_the_ico_has_three_sizes() -> None:
    pil = pytest.importorskip("PIL.Image")
    touch = pil.open(io.BytesIO((logo.STATIC / "apple-touch-icon.png").read_bytes())).convert(
        "RGBA"
    )
    ico = pil.open(io.BytesIO((logo.STATIC / "favicon.ico").read_bytes()))

    assert touch.getpixel((0, 0))[3] == 255  # no transparent corner: the system rounds it
    assert set(ico.info["sizes"]) == set(logo.ICO_SIZES)


def test_the_assets_can_be_rewritten(tmp_path: Path) -> None:
    pytest.importorskip("PIL.Image")

    written = logo.write_assets(tmp_path)

    assert sorted(p.name for p in written) == [
        "apple-touch-icon.png", "favicon.ico", "favicon.png", "icon.svg", "logo.svg",
        "wordmark.svg",
    ]  # fmt: skip
    assert (tmp_path / "logo.svg").read_text(encoding="utf-8") == logo.wordmark_svg()


def _pixels(data: bytes) -> tuple[tuple[int, int], bytes]:
    from PIL import Image

    image = Image.open(io.BytesIO(data)).convert("RGB")
    return image.size, image.tobytes()


def test_the_committed_png_icons_are_what_the_generator_draws() -> None:
    pytest.importorskip("PIL.Image")

    # the pixels, not the bytes: the compression of a PNG differs between machines
    drawn = {
        "favicon.png": logo.favicon_png(),
        "apple-touch-icon.png": logo.favicon_png(logo.APPLE_TOUCH_SIZE, round_badge=False),
    }
    for name, png in drawn.items():
        assert _pixels((logo.STATIC / name).read_bytes()) == _pixels(png), name


def test_the_calm_wordmark_is_real_text_with_the_rising_bars_and_is_committed() -> None:
    svg = logo.calm_wordmark_svg()

    assert svg.count("<rect") == len(logo.BARS) and ">Dataward</text>" in svg
    assert 'aria-label="Dataward"' in svg and t.ACCENT in svg and logo.DOT_COLOUR in svg
    assert "&lt;b&gt;" in logo.calm_wordmark_svg("<b>")  # a name is escaped
    assert (logo.STATIC / "wordmark.svg").read_text(encoding="utf-8") == svg
