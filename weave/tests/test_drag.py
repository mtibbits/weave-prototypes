"""#9 on the page: drag a tile in settled tiles to rearrange the quilt, and sew it back with the seams meeting."""
import json

import pytest

from helpers import (DEFAULT_IDS, QUILT_HINT, SEAMS, SEW_NAME, UNSTITCH_NAME, assert_tile_geometry, click_world, frames,
                     live_quilt, log_modes, modes, open_live, project, wait_for_data_mode, wait_for_mode, weave)
from test_quilt_panels import SHIPPED, SLOT_BODIES
from test_unstitch import CYCLE, REST, centre, fades, held_for, layout, press, tile_geometry, unstitch

# The issue's order after a drag of slot 0 (manpower) to slot 5: moveItem(DEFAULT_IDS, 0, 5).
EXPECTED = ["hiring", "training", "awards", "promotions", "travel", "manpower", "feedback", "actions",
            "oversight", "access", "desks", "suggest"]
MOVED = ["manpower", "hiring", "training", "awards", "promotions", "travel"]
# A panels.js suffix that ships the panels already in EXPECTED's order (a fresh build of the dragged quilt).
REORDER = f"\nwindow.WEAVE_PANELS.panels.sort((a, b) => {json.dumps(EXPECTED)}.indexOf(a.id) - {json.dumps(EXPECTED)}.indexOf(b.id));\n"
# One window for a press's negative ("nothing happens") and its positive control.
PRESS_WINDOW_MS = 800
LIFT = 0.05  # motion.js's DRAG.lift


def tile_xy(page, slot):
    return project(page, [*layout(page)["tiles"][slot], 0])


def quilt_xy(page, slot):
    return project(page, centre(page, slot))


def drag(page, a, b, release=True, steps=12):
    page.mouse.move(*a)
    page.mouse.down()
    page.mouse.move(*b, steps=steps)
    if release:
        page.mouse.up()


def nudge(page, a, dx):
    page.mouse.move(*a)
    page.mouse.down()
    page.mouse.move(a[0] + dx, a[1])
    page.mouse.up()


def order(page):
    return weave(page, ".order")


def centres(page):
    """Each snapshot block (slot order) as { id, slot, xy }: the corner mean of corners 0, 40, 1640 and 1680."""
    return page.eval_on_selector("[data-hero]", r"""el => el.__weave.snapshot().blocks.map((b) => ({ id: b.id, slot: b.slot,
        xy: [0, 1].map((k) => [0, 40, 1640, 1680].reduce((s, j) => s + b.positions[3 * j + k], 0) / 4) }))""")


def centre_of(page, block_id):
    return next(c["xy"] for c in centres(page) if c["id"] == block_id)


def corners_z(page, block_id):
    return page.eval_on_selector("[data-hero]", "(el, id) => { const b = el.__weave.snapshot().blocks.find((x) => x.id === id);"
                                 " return [0, 40, 1640, 1680].map((j) => b.positions[3 * j + 2]); }", block_id)


def wait_frames(page, n=2):
    """Wait until the live loop has drawn at least n more frames."""
    page.wait_for_function("(want) => Number(document.querySelector('[data-hero]').dataset.heroFrames || 0) >= want",
                           arg=frames(page) + n, timeout=5000)


def close(a, b, eps):
    return all(abs(x - y) <= eps for x, y in zip(a, b))


# Waits (polling every frame) until the tile at tile slot 0 is what a press there would hit while the director is
# still in `mode`; records the mode the next canvas pointerdown sees as window.__pressMode.
PRESS_MODE = r"""([mode, x, y]) => new Promise((resolve) => {
    const el = document.querySelector('[data-hero]');
    el.querySelector('canvas').addEventListener('pointerdown', () => { window.__pressMode = el.__weave.mode; },
                                                { capture: true, once: true });
    const poll = () => {
      if (el.__weave.mode !== mode) { resolve(false); return; }
      if (el.__weave.pick(x, y).part === 'tile') { resolve(true); return; }
      requestAnimationFrame(poll);
    };
    poll();
})"""

# test_tilted_blocks_sit_above_the_sashing's rule: the sashing triangles whose centroid lies inside quilt slot k.
CELLS_IN = r"""async (el, slots) => {
    const L = await import('/public/js/layout.js');
    const { positions: sp, indices: si } = el.__weave.snapshot().sashing;
    return slots.map((slot) => {
      const [cx, cy] = L.slotCentre(slot);
      let n = 0;
      for (let t = 0; t < si.length; t += 3) {
        const x = (sp[3 * si[t]] + sp[3 * si[t + 1]] + sp[3 * si[t + 2]]) / 3;
        const y = (sp[3 * si[t] + 1] + sp[3 * si[t + 1] + 1] + sp[3 * si[t + 2] + 1]) / 3;
        if (Math.abs(x - cx) < 0.5 && Math.abs(y - cy) < 0.5) n += 1;
      }
      return n;
    });
}"""


def tiles_settled(page):
    """Wait until every block's centre is within 1e-3 of its tile slot (5 s). The predicate is synchronous:
    wait_for_function takes a returned Promise as truthy and would not wait at all."""
    page.wait_for_function(r"""(tiles) => document.querySelector('[data-hero]').__weave.snapshot().blocks.every((b) =>
        [0, 1].every((k) => Math.abs([0, 40, 1640, 1680].reduce((s, j) => s + b.positions[3 * j + k], 0) / 4
          - tiles[b.slot][k]) <= 1e-3))""", arg=layout(page)["tiles"], timeout=5000)


def test_drag_reorders_the_tiles(make_page, base_url):
    page, errors = open_live(make_page, base_url, query=REST)
    unstitch(page)
    drag(page, tile_xy(page, 0), tile_xy(page, 5))
    assert order(page) == EXPECTED
    assert [s["id"] for s in weave(page, ".slots")] == EXPECTED
    assert [(c["id"], c["slot"]) for c in centres(page)] == list(zip(EXPECTED, range(12)))
    tiles_settled(page)
    planned, square = page.eval_on_selector("[data-hero]", CELLS_IN, [3, 4])
    assert planned > 0 and square == 0, (planned, square)  # promotions (planned) now at 3, travel (square) at 4
    assert errors == []
    # A drag that ends well below the stage selects no text on the page.
    box = page.locator("[data-hero]").bounding_box()
    a = tile_xy(page, 0)
    drag(page, a, (a[0], box["y"] + box["height"] + 120))
    assert page.evaluate("getSelection().toString()") == ""
    assert errors == []


def test_small_press_on_a_tile_is_a_click(make_page, base_url):
    page, errors = open_live(make_page, base_url, query=REST, before_goto=log_modes)
    unstitch(page)
    a = tile_xy(page, 0)
    for dx in (3, 6):
        page.mouse.move(*a)
        page.mouse.down()
        page.mouse.move(a[0] + dx, a[1])
        wait_frames(page)
        assert all(abs(z) <= 1e-9 for z in corners_z(page, "manpower")), dx  # no lift
        assert close(centre_of(page, "manpower"), layout(page)["tiles"][0], 1e-9), dx
        page.mouse.up()
        assert order(page) == DEFAULT_IDS
        assert held_for(page, "tiles", PRESS_WINDOW_MS), dx
    # Control: one pixel more is a grab, and the same probe sees the lift.
    page.mouse.move(*a)
    page.mouse.down()
    page.mouse.move(a[0] + 7, a[1])
    wait_frames(page)
    assert all(abs(z - LIFT) <= 1e-6 for z in corners_z(page, "manpower")), corners_z(page, "manpower")
    page.mouse.up()
    assert order(page) == DEFAULT_IDS
    assert modes(page) == CYCLE[:3]
    assert errors == []


def test_quilt_press_threshold_is_6_px(make_page, base_url):
    page, errors = open_live(make_page, base_url, query=REST, before_goto=log_modes)
    nudge(page, quilt_xy(page, 5), 7)
    assert held_for(page, "quilt", PRESS_WINDOW_MS)
    assert order(page) == DEFAULT_IDS
    # Control: a 6 px press is a click, and unstitches inside the same window.
    nudge(page, quilt_xy(page, 5), 6)
    wait_for_mode(page, "unstitching", timeout=PRESS_WINDOW_MS * 5 // 8)
    assert errors == []


def test_no_drag_outside_settled_tiles(make_page, base_url):
    page, errors = open_live(make_page, base_url, query=REST, before_goto=log_modes)
    # The quilt: a drag across it neither drags nor clicks.
    drag(page, quilt_xy(page, 0), quilt_xy(page, 5))
    assert held_for(page, "quilt", PRESS_WINDOW_MS)
    assert order(page) == DEFAULT_IDS and modes(page) == CYCLE[:1]
    # Unstitching: a press on a tile that has already turned over, before the settle.
    a, b = tile_xy(page, 0), tile_xy(page, 5)
    press(page, UNSTITCH_NAME)
    assert page.evaluate(PRESS_MODE, ["unstitching", *a]) is True
    drag(page, a, b, steps=40)
    assert page.evaluate("window.__pressMode") == "unstitching"
    wait_for_data_mode(page, "tiles")
    assert order(page) == DEFAULT_IDS
    # Restitching: a press on a tile that has not left yet.
    press(page, SEW_NAME)
    assert page.evaluate(PRESS_MODE, ["restitching", *a]) is True
    drag(page, a, b, steps=40)
    assert page.evaluate("window.__pressMode") == "restitching"
    wait_for_data_mode(page, "quilt")
    assert order(page) == DEFAULT_IDS
    assert modes(page) == CYCLE
    assert errors == []


def test_drag_while_paused(make_page, base_url):
    page, errors = open_live(make_page, base_url, query=REST)
    page.locator("[data-pause]").click()
    press(page, UNSTITCH_NAME)
    assert weave(page, ".mode") == "tiles"
    held = frames(page)
    tiles = layout(page)["tiles"]
    drag(page, tile_xy(page, 0), tile_xy(page, 5), release=False)
    assert close(centre_of(page, "manpower"), tiles[5], 0.02)
    reflowed = {c["id"]: c["xy"] for c in centres(page)}
    for slot, block_id in enumerate(EXPECTED[:5]):
        assert close(reflowed[block_id], tiles[slot], 1e-6), (block_id, reflowed[block_id], tiles[slot])
    page.mouse.up()
    assert order(page) == EXPECTED
    assert_tile_geometry(tile_geometry(page))
    assert frames(page) == held
    assert errors == []


def test_fillers_stay_put_and_a_drop_clamps(make_page, base_url):
    page, errors = open_live(make_page, base_url, query=REST, panels_body=SLOT_BODIES["ten"])
    unstitch(page)
    stored = page.eval_on_selector("[data-hero]", "el => el.__weave.snapshot().blocks.slice(10).map((b) => b.positions)")
    drag(page, tile_xy(page, 0), tile_xy(page, 11))
    now = order(page)
    assert now[:10] == DEFAULT_IDS[1:10] + ["manpower"] and now[10:] == [None, None]
    assert sum(x is not None for x in now) == 10
    assert [f["slot"] for f in fades(page)["fillers"]] == [10, 11]
    assert page.eval_on_selector("[data-hero]", "el => el.__weave.snapshot().blocks.slice(10).map((b) => b.positions)") == stored
    press(page, SEW_NAME)
    wait_for_data_mode(page, "quilt")
    assert [f["slot"] for f in fades(page)["fillers"]] == [10, 11]
    assert order(page)[10:] == [None, None]
    assert errors == []


def test_pointercancel_drops_into_the_current_slot(make_page, base_url):
    page, errors = open_live(make_page, base_url, query=REST, before_goto=log_modes)
    unstitch(page)
    page.evaluate("() => document.querySelector('[data-hero] canvas').addEventListener('pointerdown',"
                  " (e) => { window.__pointerId = e.pointerId; }, { once: true })")
    drag(page, tile_xy(page, 0), tile_xy(page, 5), release=False)
    page.evaluate("() => document.querySelector('[data-hero] canvas').dispatchEvent(new PointerEvent('pointercancel',"
                  " { pointerId: window.__pointerId, isPrimary: true, bubbles: true }))")
    assert order(page) == EXPECTED
    tiles_settled(page)
    assert close(centre_of(page, "manpower"), layout(page)["tiles"][5], 1e-3)
    page.mouse.up()
    assert held_for(page, "tiles", PRESS_WINDOW_MS)
    assert order(page) == EXPECTED
    assert errors == []


def test_toggle_mid_drag_drops_then_sews_back(make_page, base_url):
    page, errors = open_live(make_page, base_url, query=REST, before_goto=log_modes)
    unstitch(page)
    drag(page, tile_xy(page, 0), tile_xy(page, 5), release=False)
    page.locator("[data-toggle]").focus()
    page.keyboard.press("Enter")
    wait_for_data_mode(page, "quilt")
    assert weave(page, ".mode") == "quilt"
    assert order(page) == EXPECTED
    from_layout = page.evaluate("import('/public/js/layout.js').then((L) => L.slotCentre(5))")
    assert close(centre_of(page, "manpower"), from_layout, 1e-6)
    page.mouse.up()
    assert held_for(page, "quilt", PRESS_WINDOW_MS)  # the release is not a click
    assert modes(page) == CYCLE
    assert errors == []


@pytest.mark.parametrize("query", [REST, "?nowatchdog"], ids=["rest", "plain"])
def test_seams_meet_after_reorder_and_sew_back(make_page, base_url, query):
    page, errors = live_quilt(make_page, base_url, query=query)
    unstitch(page)
    drag(page, tile_xy(page, 0), tile_xy(page, 5))
    assert order(page) == EXPECTED  # the precondition: the drag reordered the quilt
    press(page, SEW_NAME)
    wait_for_data_mode(page, "quilt")
    r = page.eval_on_selector("[data-hero]", SEAMS)
    assert (r["checked"], r["missing"]) == (1280, 0), r
    if query == REST:
        assert r["off"] <= 1e-6, r
    assert errors == []


# Per id: the base's slot, tilt and the worst |z - (puffZ + foldZ)| over the flat grid, sampled at the tilt-rotated
# point (#7's build; for a square block t = 0 gives the AC's (cx + lx, cy + ly) verbatim).
FOLD_ORACLE = r"""async (el, ids) => {
    const L = await import('/public/js/layout.js');
    return ids.map((id) => {
      const b = el.__weave.blockBase(id);
      const [cx, cy] = L.slotCentre(b.slot);
      const cos = Math.cos(b.tilt); const sin = Math.sin(b.tilt);
      let worst = 0;
      for (let r = 0; r <= 40; r += 1) {
        for (let c = 0; c <= 40; c += 1) {
          const j = r * 41 + c;
          const lx = c / 40 - 0.5; const ly = 0.5 - r / 40;
          const want = L.puffZ(lx + 0.5, ly + 0.5) + L.foldZ(cx + cos * lx - sin * ly, cy + sin * lx + cos * ly);
          worst = Math.max(worst, Math.abs(b.positions[3 * j + 2] - want));
        }
      }
      return { id, slot: b.slot, tilt: b.tilt, worst, normals: b.normals };
    });
}"""


def test_drag_rebuilds_the_fold(make_page, base_url):
    page, errors = open_live(make_page, base_url, query=REST)
    unstitch(page)
    drag(page, tile_xy(page, 0), tile_xy(page, 5))
    bases = page.eval_on_selector("[data-hero]", FOLD_ORACLE, MOVED)
    assert len(bases) == 6
    for b in bases:
        assert b["slot"] == EXPECTED.index(b["id"]), b["id"]
        assert b["worst"] <= 1e-4, (b["id"], b["worst"])
    promotions = next(b for b in bases if b["id"] == "promotions")
    assert promotions["slot"] == 3 and promotions["tilt"] != 0
    fresh, _ = open_live(make_page, base_url, query=REST, panels_body=SHIPPED + REORDER)
    assert order(fresh) == EXPECTED
    for b, f in zip(bases, fresh.eval_on_selector("[data-hero]", FOLD_ORACLE, MOVED)):
        assert f["slot"] == b["slot"]
        assert max(abs(x - y) for x, y in zip(b["normals"], f["normals"])) <= 1e-3, b["id"]
    assert errors == []


def test_live_hint_mentions_dragging(make_page, base_url):
    page, errors = open_live(make_page, base_url, query=REST)
    text = page.locator("[data-hint]").text_content()
    assert text == QUILT_HINT and "drag a tile" in text
    assert errors == []


def test_pause_after_drop_lands_the_tiles(make_page, base_url):
    page, errors = open_live(make_page, base_url, query=REST)
    unstitch(page)
    drag(page, tile_xy(page, 0), tile_xy(page, 5))
    page.locator("[data-pause]").click()
    assert order(page) == EXPECTED
    assert_tile_geometry(tile_geometry(page))
    held = frames(page)
    page.wait_for_timeout(300)
    assert frames(page) == held
    assert errors == []


def sashing_follows_the_faces(page):
    """After a sew-back: no sashing under a square block's slot, and some under every planned block's."""
    snap = page.eval_on_selector("[data-hero]", "el => el.__weave.snapshot().blocks.map((b) => [b.slot, b.face])")
    cells = page.eval_on_selector("[data-hero]", CELLS_IN, [slot for slot, _ in snap])
    return all((n > 0) == (face == "planned") for (_, face), n in zip(snap, cells)), list(zip(snap, cells))


def settled_drop(page):
    """The dropped tile lands: every block back at its tile slot and flat at z = 0."""
    tiles_settled(page)
    page.wait_for_function("() => { const b = document.querySelector('[data-hero]').__weave.snapshot().blocks"
                           ".find((x) => x.id === 'manpower');"
                           " return [0, 40, 1640, 1680].every((j) => Math.abs(b.positions[3 * j + 2]) <= 1e-3); }",
                           timeout=5000)


def drag_again_then_sew_back_by_click(page):
    """A later drag still works, and a background click sews back with the sashing re-cut for the new order."""
    drag(page, tile_xy(page, 6), tile_xy(page, 8))
    want = EXPECTED[:6] + EXPECTED[7:9] + [EXPECTED[6]] + EXPECTED[9:]
    assert order(page) == want
    tiles_settled(page)
    click_world(page, [0, 0, 0])  # the gutter between tiles: the background
    wait_for_data_mode(page, "quilt")
    ok, cells = sashing_follows_the_faces(page)
    assert ok, cells


def test_a_second_primary_press_drops_the_drag(make_page, base_url):
    """A touch tap during a mouse drag (isPrimary is per pointer type) ends the drag; nothing stays lifted."""
    page, errors = open_live(make_page, base_url, query=REST)
    unstitch(page)
    drag(page, tile_xy(page, 0), tile_xy(page, 5), release=False)
    x, y = project(page, [0, 0, 0])
    page.evaluate("""([x, y]) => { const c = document.querySelector('[data-hero] canvas');
        for (const type of ['pointerdown', 'pointerup']) c.dispatchEvent(new PointerEvent(type, { pointerId: 7,
          pointerType: 'touch', isPrimary: true, button: 0, clientX: x, clientY: y, bubbles: true })); }""", [x, y])
    page.mouse.up()
    assert order(page) == EXPECTED
    settled_drop(page)
    drag_again_then_sew_back_by_click(page)
    assert errors == []


def test_lost_capture_drops_the_drag(make_page, base_url):
    """Capture lost mid-drag (no pointercancel) drops the tile; a buttonless hover never drags it."""
    page, errors = open_live(make_page, base_url, query=REST)
    unstitch(page)
    page.evaluate("() => document.querySelector('[data-hero] canvas').addEventListener('pointerdown',"
                  " (e) => { window.__pointerId = e.pointerId; }, { once: true })")
    drag(page, tile_xy(page, 0), tile_xy(page, 5), release=False)
    page.evaluate("() => document.querySelector('[data-hero] canvas').releasePointerCapture(window.__pointerId)")
    box = page.locator("[data-hero]").bounding_box()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] + 60, steps=5)
    page.mouse.up()
    page.mouse.move(*tile_xy(page, 9), steps=10)
    assert order(page) == EXPECTED
    settled_drop(page)
    drag_again_then_sew_back_by_click(page)
    assert errors == []


def test_a_buttonless_move_drops_the_drag(make_page, base_url):
    """A drag whose release was lost (Alt+Tab, a dialog): the next move with no button held drops the tile."""
    page, errors = open_live(make_page, base_url, query=REST)
    unstitch(page)
    drag(page, tile_xy(page, 0), tile_xy(page, 5), release=False)
    x, y = tile_xy(page, 9)
    page.evaluate("""([x, y]) => document.querySelector('[data-hero] canvas').dispatchEvent(new PointerEvent('pointermove',
        { pointerId: 1, pointerType: 'mouse', isPrimary: true, buttons: 0, clientX: x, clientY: y, bubbles: true }))""", [x, y])
    assert order(page) == EXPECTED
    settled_drop(page)
    page.mouse.up()
    drag_again_then_sew_back_by_click(page)
    assert errors == []


# The quilt group's ambient rotation from one snapshot: tiltY from the rod's axis, and the x rotation (sway + tiltX)
# from block 0's top-left corner, whose quilt-space position is known (an untilted block, puff 0 on its edge).
AMBIENT = r"""async (el) => {
    const L = await import('/public/js/layout.js');
    const snap = el.__weave.snapshot();
    const [s, e] = [snap.rod.start, snap.rod.end];
    const tiltY = Math.atan2(-(e[2] - s[2]), e[0] - s[0]);
    const P = [0, L.LAYOUT.rod.y, 0];
    const [cx, cy] = L.slotCentre(snap.blocks[0].slot);
    const local = [cx - 0.5, cy + 0.5, L.foldZ(cx - 0.5, cy + 0.5)];
    const w = snap.blocks[0].positions.slice(0, 3).map((v, k) => v - P[k]);
    const u = local.map((v, k) => v - P[k]);
    const back = [Math.cos(-tiltY) * w[0] + Math.sin(-tiltY) * w[2], w[1], -Math.sin(-tiltY) * w[0] + Math.cos(-tiltY) * w[2]];
    const turn = Math.atan2(back[2], back[1]) - Math.atan2(u[2], u[1]);
    const aboutX = Math.atan2(Math.sin(turn), Math.cos(turn));
    return { tiltY, aboutX, max: L.LAYOUT.ambientMax };
}"""


def test_quilt_press_off_stage_keeps_the_tilt_bounded(make_page, base_url):
    """A quilt press is never captured, so moving it off the stage leaves the tilt bounded. This guards the capture
    scope: main.js's tilt clamp alone cannot redden it (its planted control also captured every press)."""
    page, errors = live_quilt(make_page, base_url)
    box = page.locator("[data-hero]").bounding_box()
    viewport = page.viewport_size
    start = (box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    end = (min(box["x"] + box["width"] + 200, viewport["width"] - 1), box["y"] + box["height"] + 200)
    page.mouse.move(*start)
    page.mouse.down()
    page.mouse.move(*end, steps=20)
    page.wait_for_timeout(1000)
    r = page.eval_on_selector("[data-hero]", AMBIENT)
    page.mouse.up()
    assert abs(r["tiltY"]) <= r["max"]["tiltY"] + 1e-6, r
    assert abs(r["aboutX"]) <= r["max"]["sway"] + r["max"]["tiltX"] + 1e-6, r
    assert weave(page, ".mode") == "quilt"
    assert errors == []
