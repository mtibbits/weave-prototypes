"""#10's seam stitches and pins on the page: where they lie, how #8's transitions hide and return them, and the five
per-block calls E2's #16 drives (at ?pose=rest, where world space is quilt space)."""
import json

import pytest

from helpers import SEW_NAME, SNAP_JSON, frames, open_live, wait_for_data_mode, wait_for_decor, weave
from test_drag import EXPECTED, drag, order, tile_xy
from test_intro import LIVE_IDS, PLANNED_IDS, decor_counts
from test_unstitch import REST, press, unstitch

# Every shown stitch against its slot from one snapshot: the gap to its slot's nearest edge, |z - foldZ| and the
# cross-seam component of its +X; the per-id counts; stitchDash against scene.js's exports.
STITCH_CHECK = r"""async (el) => {
    const THREE = await import('three');
    const L = await import('/public/js/layout.js');
    const S = await import('/public/js/scene.js');
    const snap = el.__weave.snapshot();
    const slotOf = Object.fromEntries(snap.blocks.map((b) => [b.id, b.slot]));
    let edge = 0; let z = 0; let cross = 0;
    const perId = {};
    for (const s of snap.stitches) {
      perId[s.id] = (perId[s.id] ?? 0) + 1;
      const [x, y, zz] = s.position;
      const [cx, cy] = L.slotCentre(slotOf[s.id]);
      const gx = Math.abs(Math.abs(x - cx) - 0.5); const gy = Math.abs(Math.abs(y - cy) - 0.5);
      edge = Math.max(edge, Math.min(gx, gy));
      z = Math.max(z, Math.abs(zz - L.foldZ(x, y)));
      const X = new THREE.Vector3(1, 0, 0).applyQuaternion(new THREE.Quaternion(...s.quaternion));
      cross = Math.max(cross, Math.abs(gx < gy ? X.x : X.y));
    }
    return { edge, z, cross, count: snap.stitches.length, perId,
             dash: [snap.stitchDash, { length: S.STITCH_DASH_LENGTH, radius: S.STITCH_DASH_RADIUS }] };
}"""

# Every pin against its block's mesh from one snapshot (Task 2's rule): the tip's |z| gap to the surface, bilinear in
# the block's grid at the tip's inverse-tilted local xy; the angle (degrees) from that cell's mesh normal; the scale.
PIN_CHECK = r"""async (el) => {
    const THREE = await import('three');
    const L = await import('/public/js/layout.js');
    const { rngFor } = await import('/public/js/random.js');
    const snap = el.__weave.snapshot();
    let gap = 0; let angle = 0; let scale = 0;
    const perId = {};
    for (const pin of snap.pins) {
      perId[pin.id] = (perId[pin.id] ?? 0) + 1;
      const b = snap.blocks.find((x) => x.id === pin.id);
      const t = b.face === 'planned' ? (rngFor(b.id, 'tilt')() * 2 - 1) * (2.5 * Math.PI / 180) : 0;
      const [cx, cy] = L.slotCentre(b.slot);
      const dx = pin.position[0] - cx; const dy = pin.position[1] - cy;
      const lx = Math.cos(-t) * dx - Math.sin(-t) * dy; const ly = Math.sin(-t) * dx + Math.cos(-t) * dy;
      const fc = (lx + 0.5) * 40; const fr = (0.5 - ly) * 40;
      const c0 = Math.min(39, Math.floor(fc)); const r0 = Math.min(39, Math.floor(fr));
      const u = fc - c0; const v = fr - r0;
      const P = (r, c) => b.positions.slice(3 * (r * 41 + c), 3 * (r * 41 + c) + 3);
      const [p00, p01, p10, p11] = [P(r0, c0), P(r0, c0 + 1), P(r0 + 1, c0), P(r0 + 1, c0 + 1)];
      const z = (1 - u) * (1 - v) * p00[2] + u * (1 - v) * p01[2] + (1 - u) * v * p10[2] + u * v * p11[2];
      gap = Math.max(gap, Math.abs(z - pin.position[2]));
      const n = new THREE.Vector3(...p11).sub(new THREE.Vector3(...p00))
        .cross(new THREE.Vector3(...p01).sub(new THREE.Vector3(...p10))).normalize();
      if (n.z < 0) n.negate();
      const up = new THREE.Vector3(0, 1, 0).applyQuaternion(new THREE.Quaternion(...pin.quaternion));
      angle = Math.max(angle, (up.angleTo(n) * 180) / Math.PI);
      scale = Math.max(scale, ...pin.scale.map((s) => Math.abs(s - 1)));
    }
    return { gap, angle, scale, perId };
}"""

LISTS = "el => { const s = el.__weave.snapshot(); return JSON.stringify([s.stitches, s.pins]); }"


def call(page, js):
    """Run `js` with w = the stage's __weave."""
    return page.eval_on_selector("[data-hero]", f"el => {{ const w = el.__weave; {js} }}")


def reorder_and_sew_back(page):
    unstitch(page)
    drag(page, tile_xy(page, 0), tile_xy(page, 5))
    assert order(page) == EXPECTED  # precondition: the drag reordered the quilt
    press(page, SEW_NAME)
    wait_for_data_mode(page, "quilt")


@pytest.mark.parametrize("case", ["load", "reorder"])
def test_stitches_on_the_fabric(make_page, base_url, case):
    page, errors = open_live(make_page, base_url, query=REST)
    if case == "reorder":
        reorder_and_sew_back(page)
    r = page.eval_on_selector("[data-hero]", STITCH_CHECK)
    assert r["count"] == 336 and r["perId"] == {i: 48 for i in LIVE_IDS}, r["perId"]
    assert r["edge"] <= 1e-6 and r["z"] <= 1e-3 and r["cross"] < 1e-3, r
    assert r["dash"][0] == r["dash"][1]
    assert errors == []


@pytest.mark.parametrize("case", ["load", "reorder"])
def test_pins_on_their_blocks(make_page, base_url, case):
    page, errors = open_live(make_page, base_url, query=REST)
    if case == "reorder":
        reorder_and_sew_back(page)
    r = page.eval_on_selector("[data-hero]", PIN_CHECK)
    assert sorted(r["perId"]) == sorted(PLANNED_IDS) and all(n in (3, 4) for n in r["perId"].values()), r["perId"]
    assert r["gap"] <= 1e-3 and r["angle"] <= 20 and r["scale"] <= 1e-6, r
    assert errors == []


def test_unstitch_hides_and_sew_back_returns_the_decor(make_page, base_url):
    page, errors = open_live(make_page, base_url, query=REST)
    load = page.eval_on_selector("[data-hero]", LISTS)
    assert json.loads(load)[0] and json.loads(load)[1]  # precondition: both lists are drawn at load
    unstitch(page)
    assert json.loads(page.eval_on_selector("[data-hero]", LISTS)) == [[], []]
    press(page, SEW_NAME)
    wait_for_data_mode(page, "quilt")
    assert page.eval_on_selector("[data-hero]", LISTS) == load
    assert errors == []


def test_popping_one_block_leaves_the_others(make_page, base_url):
    page, errors = open_live(make_page, base_url, query=REST)
    call(page, "w.popStitches('manpower');")
    wait_for_decor(page)
    c = decor_counts(page)["stitches"]
    assert "manpower" not in c and c == {i: 48 for i in LIVE_IDS if i != "manpower"}, c
    assert errors == []


# (call, setup, the id, the list it changes, the count at its end)
END_CALLS = {
    "popStitches": ("", "manpower", "stitches", {0}),
    "revealStitches": ("w.popStitches('manpower', { animate: false });", "manpower", "stitches", {48}),
    "popPins": ("", "promotions", "pins", {0}),
    "restorePins": ("w.popPins('promotions', { animate: false });", "promotions", "pins", {3, 4}),
}


@pytest.mark.parametrize("name", list(END_CALLS))
def test_calls_end_at_once_when_paused_or_unanimated(make_page, base_url, name):
    setup, block, key, want = END_CALLS[name]
    run = (f"{setup} w.{name}('{block}', OPTIONS); return {{ n: w.snapshot().{key}.filter((e) => e.id === '{block}').length,"
           " idle: w.decorIdle };")
    page, errors = open_live(make_page, base_url, query=REST)
    unanimated = call(page, run.replace("OPTIONS", "{ animate: false }"))
    paused_page, _ = open_live(make_page, base_url, query=REST)
    paused_page.locator("[data-pause]").click()
    held = frames(paused_page)
    paused = call(paused_page, run.replace("OPTIONS", "undefined"))
    assert unanimated["n"] in want and unanimated["idle"] is True, unanimated
    assert paused["n"] in want and paused["idle"] is True, paused
    paused_page.wait_for_timeout(300)
    assert frames(paused_page) == held
    assert errors == []


def test_absent_decor_calls_change_nothing(make_page, base_url):
    page, errors = open_live(make_page, base_url, query=REST)
    before = page.eval_on_selector("[data-hero]", SNAP_JSON)
    call(page, "w.popPins('manpower'); w.popStitches('promotions');")
    page.wait_for_timeout(100)
    assert page.eval_on_selector("[data-hero]", SNAP_JSON) == before
    call(page, "w.popStitches('manpower');")  # control: a call that has decor does change it
    page.wait_for_timeout(100)
    assert page.eval_on_selector("[data-hero]", SNAP_JSON) != before
    assert errors == []


def test_start_planned_round_trip(make_page, base_url):
    """#16's "start planned" on a sewn block and back, each step read once its animation has ended."""
    page, errors = open_live(make_page, base_url, query=REST)

    def step(js):
        call(page, js)
        wait_for_decor(page)
        c = decor_counts(page)
        return c["stitches"].get("manpower", 0), c["pins"].get("manpower", 0)

    assert step("w.restorePins('manpower');")[1] in (3, 4)
    assert step("w.popStitches('manpower');")[0] == 0
    assert step("w.popPins('manpower'); w.setFace('manpower', 'sewn'); w.revealStitches('manpower');") == (48, 0)
    assert weave(page, ".slots")[0]["face"] == "sewn"
    assert errors == []


def test_set_face_updates_the_slot(make_page, base_url):
    page, errors = open_live(make_page, base_url, query=REST)
    assert weave(page, ".slots")[4]["face"] == "planned"  # precondition
    call(page, "w.setFace('promotions', 'sewn');")
    assert weave(page, ".slots")[4]["face"] == "sewn"
    assert call(page, "return w.snapshot().blocks[4].face;") == "sewn"
    assert errors == []
