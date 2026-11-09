import re

import pytest

from jobmarket import dashboard_mascot as m


def test_every_character_row_is_the_same_width_and_uses_only_known_colours() -> None:
    for grid, width in ((m.FROG, 16), (m.TADPOLE, 16)):
        assert all(len(row) == width for row in grid)
        assert set("".join(grid)) <= set(m.PALETTE) | {"."}


def test_every_stage_and_mood_draws() -> None:
    for stage in m.STAGES:
        for mood in m.MOODS:
            svg = m.frog_svg(stage, mood)
            assert svg.startswith("<svg") and f"dw-frog-{mood}" in svg and "<path" in svg


def test_an_unknown_stage_or_mood_is_refused() -> None:
    with pytest.raises(ValueError, match="stage"):
        m.frog_svg("dragon")
    with pytest.raises(ValueError, match="mood"):
        m.frog_svg("frog", "furious")


def test_the_picture_fits_the_canvas() -> None:
    for stage in m.STAGES:
        for mood in m.MOODS:
            svg = m.frog_svg(stage, mood)
            for x, y in re.findall(r"M(\d+) (\d+)h1v1h-1z", svg):
                assert 0 <= int(x) < m.WIDTH and 0 <= int(y) < m.HEIGHT, (stage, mood, x, y)


def test_only_the_king_wears_a_crown() -> None:
    crown = m.PALETTE["y"]

    assert crown in m.frog_svg("king", "idle") and crown not in m.frog_svg("frog", "idle")
    assert crown not in m.frog_svg("tadpole", "idle")


def test_moods_have_their_signs() -> None:
    assert m.PALETTE["z"] in m.frog_svg("frog", "sleepy")  # a Z
    assert m.PALETTE["b"] in m.frog_svg("frog", "sad")  # a tear
    assert m.PALETTE["r"] in m.frog_svg("frog", "happy")  # a heart (and cheeks)
    assert m.PALETTE["z"] not in m.frog_svg("frog", "idle")


def test_each_mood_looks_different() -> None:
    drawn = {mood: m.frog_svg("frog", mood) for mood in m.MOODS}

    assert len(set(drawn.values())) == len(m.MOODS)


def test_a_frog_that_looks_ahead_blinks_and_one_with_closed_eyes_does_not() -> None:
    assert 'class="dw-lid"' in m.frog_svg("frog", "idle")
    assert 'class="dw-lid" opacity="0"' in m.frog_svg(
        "frog", "think"
    )  # hidden until CSS flashes it
    assert "dw-lid" not in m.frog_svg("frog", "sleepy") and "dw-lid" not in m.frog_svg(
        "frog", "happy"
    )


def test_the_pixels_are_crisp_and_there_is_no_scripted_animation() -> None:
    svg = m.frog_svg("frog", "idle")

    assert 'shape-rendering="crispEdges"' in svg and "<animate" not in svg and "<script" not in svg


def test_the_scale_changes_the_size_only() -> None:
    small, big = m.frog_svg("frog", "idle"), m.frog_svg("frog", "idle", scale=2)

    assert 'width="80"' in small and 'width="160"' in big
    assert re.findall(r"d=\"[^\"]+\"", small) == re.findall(r"d=\"[^\"]+\"", big)


def test_a_label_is_escaped() -> None:
    assert "&lt;b&gt;" in m.frog_svg("frog", "idle", label="<b>")


def test_the_froglet_is_drawn_smaller_than_the_frog() -> None:
    froglet = int(re.search(r'width="(\d+)"', m.frog_svg("froglet", "idle")).group(1))  # type: ignore[union-attr]
    frog = int(re.search(r'width="(\d+)"', m.frog_svg("frog", "idle")).group(1))  # type: ignore[union-attr]

    assert froglet < frog
