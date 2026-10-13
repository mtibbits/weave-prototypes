"""#8 on the page: unstitch into tiles and sew back by the toggle and by clicks, weave:mode and data-mode, Pause,
the live hint, and the teardown of a running transition."""
import pytest

from helpers import (QUILT_HINT, SEW_NAME, STILL_HINT, TILE_GEOMETRY_JS, TILES_HINT, UNSTITCH_NAME, assert_tile_geometry,
                     click_world, frames, hero_result, ink_fraction, log_modes, modes, open_live, wait_for_data_mode,
                     wait_for_mode, weave)
from test_hero import assert_still_page
from test_pose import SAME_AS_STORED, STORE
from test_quilt_panels import SLOT_BODIES

REST = "?pose=rest&nowatchdog"
CYCLE = [("quilt", None), ("unstitching", "quilt"), ("tiles", "unstitching"), ("restitching", "tiles"),
         ("quilt", "restitching")]
LAYOUT_JS = "import('/public/js/layout.js').then((L) => ({ LAYOUT: L.LAYOUT, tiles: [...Array(12).keys()].map((i) => L.slotCentre(i, 'tiles')), foldZ00: L.foldZ(0, 0) }))"


def layout(page):
    return page.evaluate(LAYOUT_JS)


def press(page, name):
    page.get_by_role("button", name=name, exact=True).click()


def state(page):
    """[toggle label, __weave.mode, data-mode]."""
    return page.eval_on_selector("[data-hero]", "el => [document.querySelector('[data-toggle]').textContent,"
                                 " el.__weave.mode, el.dataset.mode ?? null]")


def centre(page, slot):
    """Block `slot`'s centre vertex in world space, from the page's snapshot."""
    return page.eval_on_selector("[data-hero]", "(el, slot) => el.__weave.snapshot().blocks[slot].positions"
                                 ".slice(3 * 840, 3 * 841)", slot)


def hint(page):
    return page.locator("[data-hint]").text_content()


def fades(page):
    return weave(page, ".fades()")


def all_faded(f, want):
    return [f["sashing"], f["rod"], f["shadow"]] == [want] * 3 and all(
        {"opacity": x["opacity"], "visible": x["visible"]} == want for x in f["fillers"])


GONE = {"opacity": 0, "visible": False}
SHOWN = {"opacity": 1, "visible": True}


def tile_geometry(page):
    return page.evaluate(f"""async () => {{
        const L = await import('/public/js/layout.js');
        {TILE_GEOMETRY_JS}
        return tileGeometry(document.querySelector('[data-hero]').__weave.snapshot(), (i) => L.slotCentre(i, 'tiles'));
    }}""")


def unstitch(page):
    press(page, UNSTITCH_NAME)
    wait_for_data_mode(page, "tiles")


def held_for(page, mode, ms=800):
    """Whether __weave.mode stays `mode` and no weave:mode fires for `ms`."""
    before = len(modes(page))
    for _ in range(ms // 100):
        page.wait_for_timeout(100)
        if weave(page, ".mode") != mode:
            return False
    return len(modes(page)) == before


@pytest.mark.parametrize("query", [REST, "?nowatchdog"], ids=["rest", "plain"])
def test_toggle_unstitches_and_sews_back(make_page, base_url, query):
    page, errors = open_live(make_page, base_url, query=query, before_goto=log_modes)
    press(page, UNSTITCH_NAME)
    assert state(page) == [SEW_NAME, "unstitching", "quilt"]
    wait_for_data_mode(page, "tiles")
    press(page, SEW_NAME)
    assert state(page) == [UNSTITCH_NAME, "restitching", "tiles"]
    wait_for_data_mode(page, "quilt")
    log = page.evaluate("window.__modes")
    assert [(e["mode"], e["from"]) for e in log] == CYCLE
    assert all(e["hook"] == e["mode"] for e in log), log
    assert [e["data"] for e in log if e["mode"] in ("quilt", "tiles")] == ["quilt", "tiles", "quilt"], log
    assert errors == []


def test_pause_holds_its_place_when_the_label_changes(make_page, base_url):
    page, _ = open_live(make_page, base_url, query=REST)
    pause = page.locator("[data-pause]")
    before = pause.bounding_box()["x"]
    press(page, UNSTITCH_NAME)
    assert pause.bounding_box()["x"] == before


def test_toggle_sits_outside_the_stage(make_page, base_url):
    page, _ = open_live(make_page, base_url)
    toggle = page.get_by_role("button", name=UNSTITCH_NAME, exact=True)
    assert toggle.count() == 1 and toggle.is_visible()
    assert toggle.evaluate("el => el.closest('[data-hero]') === null") is True
    assert toggle.evaluate("el => el.closest('[data-controls]') !== null") is True


def test_quilt_click_unstitches(make_page, base_url):
    page, errors = open_live(make_page, base_url, query=REST, before_goto=log_modes)
    click_world(page, centre(page, 5))
    wait_for_mode(page, "unstitching", timeout=200)
    wait_for_data_mode(page, "tiles")
    assert modes(page) == CYCLE[:3]
    assert errors == []


def test_tiles_mode_is_flat_flipped_square_and_still(make_page, base_url):
    """Plain load: in tiles mode the sway and tilt are exactly zero, so snapshot()'s world space is quilt space."""
    page, errors = open_live(make_page, base_url)
    box = page.locator("[data-hero]").bounding_box()
    page.mouse.move(box["x"] + 5, box["y"] + 5)  # the pointer tilt is live, and must not move the tiles
    unstitch(page)
    assert_tile_geometry(tile_geometry(page))
    assert all_faded(fades(page), GONE), fades(page)
    page.eval_on_selector("[data-hero]", STORE)
    page.wait_for_timeout(1000)
    assert page.eval_on_selector("[data-hero]", SAME_AS_STORED) is True
    assert errors == []


def test_fillers_fade_and_return(make_page, base_url):
    page, errors = open_live(make_page, base_url, panels_body=SLOT_BODIES["ten"])
    unstitch(page)
    f = fades(page)
    assert [(x["slot"], x["opacity"], x["visible"]) for x in f["fillers"]] == [(10, 0, False), (11, 0, False)]
    press(page, SEW_NAME)
    wait_for_data_mode(page, "quilt")
    f = fades(page)
    assert [(x["slot"], x["opacity"], x["visible"]) for x in f["fillers"]] == [(10, 1, True), (11, 1, True)]
    assert errors == []


# The largest difference between the stored load-time snapshot and a fresh one, number by number (-1 when their
# shapes differ).
SNAPSHOT_DRIFT = r"""el => {
    const a = window.__load; const b = el.__weave.snapshot();
    let worst = 0; let shape = true;
    const walk = (x, y) => {
      if (typeof x === 'number') { if (typeof y !== 'number') shape = false; else worst = Math.max(worst, Math.abs(x - y)); return; }
      if (x && typeof x === 'object') {
        const kx = Object.keys(x); const ky = Object.keys(y ?? {});
        if (kx.length !== ky.length) { shape = false; return; }
        kx.forEach((k) => walk(x[k], y[k]));
      } else if (x !== y) shape = false;
    };
    walk(a, b);
    return shape ? worst : -1;
}"""


def test_sew_back_restores_the_rest_quilt(make_page, base_url):
    page, errors = open_live(make_page, base_url, query=REST)
    page.eval_on_selector("[data-hero]", "el => { window.__load = el.__weave.snapshot(); }")
    unstitch(page)
    assert page.eval_on_selector("[data-hero]", SNAPSHOT_DRIFT) > 0.1  # the cycle really moved the blocks
    press(page, SEW_NAME)
    wait_for_data_mode(page, "quilt")
    drift = page.eval_on_selector("[data-hero]", SNAPSHOT_DRIFT)
    assert 0 <= drift <= 1e-6, drift
    assert all_faded(fades(page), SHOWN), fades(page)
    assert errors == []


# Records block 0's corner mean from snapshot() inside the handler for the tiles entry.
SETTLED_POSE = r"""
    window.__onMode = (event, el) => {
      if (event.detail.mode !== 'tiles') return;
      const p = el.__weave.snapshot().blocks[0].positions;
      window.__tileMean = [0, 1, 2].map((k) => [0, 40, 1640, 1680].reduce((s, j) => s + p[3 * j + k], 0) / 4);
    };
"""


def test_handler_sees_the_settled_pose(make_page, base_url):
    def before(page):
        log_modes(page)
        page.add_init_script(SETTLED_POSE)
    page, errors = open_live(make_page, base_url, before_goto=before)
    unstitch(page)
    mean = page.evaluate("window.__tileMean")
    want = [*layout(page)["tiles"][0], 0]
    assert max(abs(a - b) for a, b in zip(mean, want)) <= 1e-6, (mean, want)
    assert errors == []


def test_clicks_outside_a_transition(make_page, base_url):
    page, errors = open_live(make_page, base_url, query=REST, before_goto=log_modes)
    geo = layout(page)
    slot5 = centre(page, 5)
    # Control, first: a quilt click through the same click_world path does reach the director.
    click_world(page, slot5)
    wait_for_mode(page, "unstitching", timeout=500)
    wait_for_data_mode(page, "tiles")
    click_world(page, [*geo["tiles"][5], 0])  # a tile
    assert held_for(page, "tiles")
    click_world(page, [0, 0, 0])  # the gutter between tiles: the background
    wait_for_mode(page, "restitching", timeout=500)
    wait_for_data_mode(page, "quilt")
    click_world(page, [-(geo["LAYOUT"]["quiltW"] / 2 + 0.3), 0, 0])  # the empty canvas beside the quilt
    assert held_for(page, "quilt")
    click_world(page, [0, geo["LAYOUT"]["rod"]["y"], 0])  # the rod
    assert held_for(page, "quilt")
    assert modes(page) == CYCLE
    assert errors == []


def test_toggle_reverses_mid_unstitch(make_page, base_url):
    page, errors = open_live(make_page, base_url, query=REST, before_goto=log_modes)
    press(page, UNSTITCH_NAME)
    page.wait_for_timeout(300)
    press(page, SEW_NAME)
    wait_for_mode(page, "quilt")
    assert modes(page) == [("quilt", None), ("unstitching", "quilt"), ("restitching", "unstitching"),
                           ("quilt", "restitching")]
    assert "tiles" not in page.evaluate("window.__dataModes")
    assert errors == []


def test_double_click_on_the_quilt_ends_in_tiles(make_page, base_url):
    page, errors = open_live(make_page, base_url, query=REST, before_goto=log_modes)
    x, y = page.eval_on_selector("[data-hero]", "(el, p) => el.__weave.project(p)", centre(page, 5))
    page.mouse.click(x, y)
    page.wait_for_timeout(150)
    page.mouse.click(x, y)
    wait_for_data_mode(page, "tiles")
    assert [m for m, _ in modes(page)].count("unstitching") == 1
    assert modes(page) == CYCLE[:3]
    assert errors == []


def test_canvas_click_mid_sew_back_does_not_reverse(make_page, base_url):
    page, errors = open_live(make_page, base_url, query=REST, before_goto=log_modes)
    slot5 = centre(page, 5)
    unstitch(page)
    press(page, SEW_NAME)
    page.wait_for_timeout(300)
    click_world(page, slot5)
    wait_for_data_mode(page, "quilt")
    assert modes(page) == CYCLE
    # Control: the same click on the settled quilt does unstitch, so the mid-transition ignore is what held it.
    click_world(page, slot5)
    wait_for_mode(page, "unstitching", timeout=500)
    assert errors == []


def test_paused_double_click_on_the_sashing_ends_in_tiles(make_page, base_url):
    page, errors = open_live(make_page, base_url, query=REST, before_goto=log_modes)
    sashing = [0, 0, layout(page)["foldZ00"]]
    page.locator("[data-pause]").click()
    x, y = page.eval_on_selector("[data-hero]", "(el, p) => el.__weave.project(p)", sashing)
    page.mouse.click(x, y)  # straight after Pause: the Pause press itself must not arm the guard
    page.wait_for_timeout(150)
    page.mouse.click(x, y)
    assert state(page)[1:] == ["tiles", "tiles"]
    assert modes(page) == CYCLE[:3]
    # Control: once the guard has passed, the same spot (a gutter in tiles mode) does sew back.
    page.wait_for_timeout(600)
    page.mouse.click(x, y)
    assert state(page)[1:] == ["quilt", "quilt"]
    assert modes(page) == CYCLE
    assert errors == []


def test_paused_toggle_and_click_snap_within_one_frame(make_page, base_url):
    page, errors = open_live(make_page, base_url, query=REST, before_goto=log_modes)
    slot5 = centre(page, 5)
    page.locator("[data-pause]").click()
    held = frames(page)
    click_world(page, slot5)
    assert state(page)[1:] == ["tiles", "tiles"] and modes(page) == CYCLE[:3]
    page.wait_for_timeout(500)
    stage = page.locator("[data-hero]")
    before = ink_fraction(stage.screenshot())
    press(page, SEW_NAME)
    assert state(page)[1:] == ["quilt", "quilt"] and modes(page) == CYCLE
    assert frames(page) == held
    after = ink_fraction(stage.screenshot())
    assert abs(after - before) > 0.02, (before, after)
    page.wait_for_timeout(500)
    press(page, UNSTITCH_NAME)
    assert state(page)[1:] == ["tiles", "tiles"]
    assert frames(page) == held
    assert errors == []


def test_pause_mid_transition_jumps_to_the_end(make_page, base_url):
    page, errors = open_live(make_page, base_url, query=REST, before_goto=log_modes)
    press(page, UNSTITCH_NAME)
    page.wait_for_timeout(300)
    assert weave(page, ".mode") == "unstitching"
    page.locator("[data-pause]").click()
    assert state(page)[1:] == ["tiles", "tiles"]
    assert modes(page) == CYCLE[:3]
    assert_tile_geometry(tile_geometry(page))
    assert errors == []


# All 48 block corners from one snapshot, projected; those outside the canvas rect.
TILE_CORNERS = r"""el => {
    const w = el.__weave;
    const snap = w.snapshot();
    const r = el.querySelector('canvas').getBoundingClientRect();
    const points = [];
    for (const b of snap.blocks) for (const j of [0, 40, 1640, 1680]) points.push(b.positions.slice(3 * j, 3 * j + 3));
    return { count: points.length,
             outside: points.map((p) => w.project(p)).filter(([x, y]) => !(x >= r.left && x <= r.right && y >= r.top && y <= r.bottom)) };
}"""


@pytest.mark.parametrize("size", [(1440, 900), (1024, 768)], ids=["1440x900", "1024x768"])
def test_tile_corners_stay_in_the_canvas(make_page, base_url, size):
    page, errors = open_live(make_page, base_url, viewport={"width": size[0], "height": size[1]})
    unstitch(page)
    r = page.eval_on_selector("[data-hero]", TILE_CORNERS)
    assert r == {"count": 48, "outside": []}
    assert errors == []


def test_live_hint_follows_the_toggle(make_page, base_url):
    page, errors = open_live(make_page, base_url, query=REST)
    assert hint(page) == QUILT_HINT
    press(page, UNSTITCH_NAME)
    assert hint(page) == TILES_HINT and state(page)[2] == "quilt"
    wait_for_data_mode(page, "tiles")
    assert hint(page) == TILES_HINT
    press(page, SEW_NAME)
    assert hint(page) == QUILT_HINT
    wait_for_data_mode(page, "quilt")
    press(page, UNSTITCH_NAME)
    page.wait_for_timeout(300)
    press(page, SEW_NAME)
    assert hint(page) == QUILT_HINT
    wait_for_mode(page, "quilt")
    assert hint(page) == QUILT_HINT
    assert errors == []


# The stopped page's watch and the no-stop control share one window, so the control proves the window long enough
# (generous: capDt slows the scene clock against the wall clock on a loaded machine).
STOP_WINDOW_MS = 5000


def test_stop_mid_transition_tears_down_the_mode(make_page, base_url):
    page, errors = open_live(make_page, base_url, before_goto=log_modes)
    press(page, UNSTITCH_NAME)
    page.eval_on_selector("[data-hero]", "el => { el.__weave.stop('context-lost'); el.__weave.stop('too-slow'); }")
    assert_still_page(page)
    logged = len(modes(page))
    page.wait_for_timeout(STOP_WINDOW_MS)
    assert len(modes(page)) == logged == 2
    assert hero_result(page) == ["still", "context-lost"]
    assert weave(page, ".mode") == "unstitching"
    assert errors == []
    # Control: without the stop, the same press reaches tiles inside the same window.
    control, _ = open_live(make_page, base_url, before_goto=log_modes)
    press(control, UNSTITCH_NAME)
    wait_for_data_mode(control, "tiles", timeout=STOP_WINDOW_MS)
    assert ("tiles", "unstitching") in modes(control)


# A weave:mode handler that tears the scene down on the unstitching entry.
STOP_IN_HANDLER = r"""
    window.__onMode = (event, el) => { if (event.detail.mode === 'unstitching') el.__weave.stop('context-lost'); };
"""


# A weave:mode handler that tears the scene down on the tiles entry (an unpaused settle, inside the frame's advance),
# recording the frame count it saw.
STOP_ON_TILES = r"""
    window.__onMode = (event, el) => {
      if (event.detail.mode !== 'tiles') return;
      window.__framesAtStop = el.dataset.heroFrames;
      el.__weave.stop('context-lost');
    };
"""


def test_a_settle_that_stops_counts_no_frame(make_page, base_url):
    def before(page):
        log_modes(page)
        page.add_init_script(STOP_ON_TILES)
    page, errors = open_live(make_page, base_url, before_goto=before)
    press(page, UNSTITCH_NAME)
    page.wait_for_function("() => window.__framesAtStop !== undefined", timeout=5000)
    page.wait_for_timeout(300)
    assert hero_result(page) == ["still", "context-lost"]
    assert page.eval_on_selector("[data-hero]", "el => el.dataset.heroFrames") == page.evaluate("window.__framesAtStop")
    assert errors == []


def test_stop_inside_a_mode_handler_halts_the_cycle(make_page, base_url):
    def before(page):
        log_modes(page)
        page.add_init_script(STOP_IN_HANDLER)
    page, errors = open_live(make_page, base_url, before_goto=before)
    page.locator("[data-pause]").click()
    press(page, UNSTITCH_NAME)
    assert page.eval_on_selector("[data-hero]", "el => el.hasAttribute('data-mode')") is False
    assert hint(page) == STILL_HINT
    assert modes(page) == CYCLE[:2]
    page.wait_for_timeout(500)
    assert modes(page) == CYCLE[:2]
    assert weave(page, ".mode") == "unstitching"
    assert errors == []
