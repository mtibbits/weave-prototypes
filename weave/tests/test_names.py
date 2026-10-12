"""fitName: the one rule that sets a panel name on a face (within 60 % of the block) or a tile (its text column)."""
import json

SETUP = r"""
    const T = await import('/public/js/tiles.js');
    const F = await import('/public/js/fabric.js');
    const ctx = F.contextOf(F.makeCanvas(8));
    const w = (text, px) => { ctx.font = T.nameFont(px); return ctx.measureText(text).width; };
"""
FACE_MAX = 0.6 * 512
BASE = 48


def fit(run, name, max_width=FACE_MAX, base=BASE):
    return run(SETUP + f"return T.fitName(ctx, {json.dumps(name)}, {max_width}, {base});")


def width(run, text, px):
    return run(SETUP + f"return w({json.dumps(text)}, {px});")


def check_layout(run, result, name, max_width, base):
    """Properties only, measured in the page with nameFont: never a hard-coded line break or size."""
    lines, px = result["lines"], result["px"]
    floor = max(8, round(base / 4))
    assert " ".join(lines) == " ".join(name.split()) and 1 <= len(lines) <= 2, result
    assert floor <= px <= base, result
    if px > floor:
        assert all(width(run, line, px) <= max_width for line in lines), result
    assert px == base or any(width(run, line, px + 1) > max_width for line in lines), "not the tightest fit"
    if len(lines) == 2:
        words = name.split()
        assert width(run, " ".join(words), base) > max_width, "wrapped a name that fits"
        n = len(lines[0].split())
        assert width(run, " ".join(words[:n + 1]), base) > max_width, "line 1 is not greedy"


def test_name_that_fits_stays_on_one_line(paint_js):
    assert width(paint_js, "Manpower", BASE) <= FACE_MAX
    result = fit(paint_js, "Manpower")
    check_layout(paint_js, result, "Manpower", FACE_MAX, BASE)
    assert result == {"lines": ["Manpower"], "px": 48}


def test_long_name_wraps_at_a_space_within_sixty_percent(paint_js):
    assert width(paint_js, "Action Tracking", BASE) > FACE_MAX
    assert width(paint_js, "Tracking", BASE) <= FACE_MAX
    result = fit(paint_js, "Action Tracking")
    check_layout(paint_js, result, "Action Tracking", FACE_MAX, BASE)
    assert result == {"lines": ["Action", "Tracking"], "px": 48}


def test_runs_of_spaces_count_as_one(paint_js):
    result = fit(paint_js, "Action  Tracking")
    check_layout(paint_js, result, "Action  Tracking", FACE_MAX, BASE)
    assert result == {"lines": ["Action", "Tracking"], "px": 48}


def test_three_word_name_fills_line_one_then_shrinks_together(paint_js):
    name = "Building Access Requests"
    assert width(paint_js, "Building Access", BASE) > FACE_MAX
    assert width(paint_js, "Access Requests", BASE) > FACE_MAX
    result = fit(paint_js, name)
    check_layout(paint_js, result, name, FACE_MAX, BASE)
    assert result["lines"] == ["Building", "Access Requests"] and result["px"] < 48


def test_single_too_wide_word_shrinks_to_fit(paint_js):
    name = "Accountabilityassurance"
    assert width(paint_js, name, BASE) > FACE_MAX
    result = fit(paint_js, name)
    check_layout(paint_js, result, name, FACE_MAX, BASE)
    assert result["lines"] == [name] and 12 < result["px"] < 48


def test_a_word_too_wide_even_at_the_floor_stops_at_the_floor(paint_js):
    name = "W" * 60
    assert width(paint_js, name, 12) > FACE_MAX
    result = fit(paint_js, name)
    check_layout(paint_js, result, name, FACE_MAX, BASE)
    assert result == {"lines": [name], "px": 12}


def test_tile_name_follows_the_rule_within_its_width(paint_js):
    pad, share, base = paint_js(SETUP + "return [T.TILE_PAD, T.TILE_NAME_MAX, T.TILE_NAME_PX];")
    assert (pad, share, base) == (40, 0.8, 40)
    max_width = share * (512 - 2 * pad)
    for name in ("Building Access", "Desk Allocation", "Suggest a panel and more"):
        check_layout(paint_js, fit(paint_js, name, max_width, base), name, max_width, base)
    assert len(fit(paint_js, "Suggest a panel and more", max_width, base)["lines"]) == 2


def test_fit_name_leaves_the_context_font_alone(paint_js):
    assert paint_js(SETUP + r"""
        ctx.font = '13px serif';
        const before = ctx.font;
        T.fitName(ctx, 'Action Tracking', 307.2, 48);
        return ctx.font === before;
    """) is True
