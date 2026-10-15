"""#10's intro on the page: a plain load flies the blocks in and settles into quilt (D12, D40), ?pose=rest skips it,
and Pause or Unstitch during it finishes it first."""
import inspect

import pytest
from playwright.sync_api import TimeoutError as PWTimeout

from helpers import (PLAIN_START, SEAMS, SEAMS_OF, UNSTITCH_NAME, frames, live_quilt, log_modes, modes, open_live,
                     project, wait_for_data_mode, wait_for_quilt, weave)
from test_unstitch import CYCLE, REST, fades, layout, press, state

LIVE_IDS = ["manpower", "hiring", "training", "awards", "travel", "actions", "desks"]
PLANNED_IDS = ["promotions", "feedback", "oversight", "access"]

# Per-id stitch and pin counts from one snapshot.
DECOR_COUNTS = r"""el => {
    const snap = el.__weave.snapshot();
    const count = (list) => list.reduce((o, e) => ({ ...o, [e.id]: (o[e.id] ?? 0) + 1 }), {});
    return { stitches: count(snap.stitches), pins: count(snap.pins) };
}"""


def decor_counts(page):
    return page.eval_on_selector("[data-hero]", DECOR_COUNTS)


def assert_load_decor(counts):
    """At load: 48 stitches on each live block and 3-4 pins on each planned one, nothing else."""
    assert counts["stitches"] == {i: 48 for i in LIVE_IDS}, counts
    assert sorted(counts["pins"]) == sorted(PLANNED_IDS) and all(n in (3, 4) for n in counts["pins"].values()), counts


def test_wait_for_quilt_defaults_to_15_s():
    assert inspect.signature(wait_for_quilt).parameters["timeout"].default == 15000


def test_wait_for_quilt_waits_for_the_settle(make_page, base_url):
    page, errors = live_quilt(make_page, base_url, before_goto=log_modes)
    assert modes(page)[:2] == PLAIN_START and weave(page, ".mode") == "quilt"
    # Control: it must time out (Playwright's TimeoutError) when the quilt is not settled.
    press(page, UNSTITCH_NAME)
    wait_for_data_mode(page, "tiles")
    with pytest.raises(PWTimeout):
        wait_for_quilt(page, timeout=500)
    assert errors == []


def test_intro_leaves_within_4_s(make_page, base_url):
    """U1, D12: on the wall clock, the intro enters quilt within 4 s; data-mode reads quilt throughout."""
    page, errors = live_quilt(make_page, base_url, before_goto=log_modes)
    log = page.evaluate("window.__modes")
    assert [(e["mode"], e["from"]) for e in log[:2]] == PLAIN_START
    assert [e["data"] for e in log[:2]] == ["quilt", "quilt"]
    print(f"intro took {log[1]['t'] - log[0]['t']:.0f} ms")
    assert log[1]["t"] - log[0]["t"] <= 4000, log[:2]
    assert set(page.evaluate("window.__dataModes")) <= {"quilt", None}
    assert errors == []


# One evaluate: the snapshot (stored as window.__settled for SEAMS_OF) and the group matrix, so the sway cannot move
# between the two reads; each planned block's tilt is the angle of its top edge (v0 -> v40) in the group's space,
# against random.js's seeded tilt computed here.
SETTLED_TILTS = r"""async (el) => {
    const THREE = await import('three');
    const { rngFor } = await import('/public/js/random.js');
    const snap = el.__weave.snapshot();
    const inverse = new THREE.Matrix4().fromArray(el.__weave.groupMatrix()).invert();
    window.__settled = snap;
    return snap.blocks.filter((b) => b.face === 'planned').map((b) => {
      const v = (j) => new THREE.Vector3(...b.positions.slice(3 * j, 3 * j + 3)).applyMatrix4(inverse);
      const d = v(40).sub(v(0));
      return { id: b.id, got: Math.atan2(d.y, d.x), want: (rngFor(b.id, 'tilt')() * 2 - 1) * (2.5 * Math.PI / 180) };
    });
}"""


def test_intro_settles_onto_the_slots(make_page, base_url):
    """D40: the settled intro is the quilt: seams meet, the decor is at rest and the planned tilts are the seeded ones.
    The pointer never enters the stage."""
    page, errors = live_quilt(make_page, base_url)
    tilts = page.eval_on_selector("[data-hero]", SETTLED_TILTS)
    seams = page.eval_on_selector("[data-hero]", SEAMS_OF, ["__settled", 0])
    nudged = page.eval_on_selector("[data-hero]", SEAMS_OF, ["__settled", 1e-3])
    assert (seams["checked"], seams["missing"]) == (1280, 0), seams
    assert nudged["missing"] >= 40, nudged  # the control: the same snapshot with slot 0 nudged
    assert [t["id"] for t in tilts] == PLANNED_IDS
    assert all(abs(t["got"] - t["want"]) <= 1e-5 for t in tilts), tilts
    assert_load_decor(decor_counts(page))
    assert errors == []


def test_rest_skips_the_intro(make_page, base_url):
    page, errors = open_live(make_page, base_url, query=REST, before_goto=log_modes)
    assert modes(page)[0] == ("quilt", None)
    assert "intro" not in [m for m, _ in modes(page)]
    assert_load_decor(decor_counts(page))
    assert errors == []


def test_pause_during_intro_jumps_to_the_settled_quilt(make_page, base_url):
    page, errors = open_live(make_page, base_url, before_goto=log_modes)
    assert weave(page, ".mode") == "intro"  # precondition: still flying in
    page.locator("[data-pause]").click()
    assert state(page)[1:] == ["quilt", "quilt"]
    assert modes(page) == PLAIN_START
    r = page.eval_on_selector("[data-hero]", SEAMS)
    assert (r["checked"], r["missing"]) == (1280, 0), r
    assert_load_decor(decor_counts(page))
    assert weave(page, ".decorIdle") is True
    held = frames(page)
    page.wait_for_timeout(500)
    assert frames(page) == held
    assert errors == []


# Stores the snapshot the unstitching entry's handler sees.
AT_LIFT = r"""
    window.__onMode = (event, el) => { if (event.detail.mode === 'unstitching') window.__atLift = el.__weave.snapshot(); };
"""


@pytest.mark.parametrize("action", ["toggle", "click"])
def test_unstitch_during_intro_completes_it_first(make_page, base_url, action):
    def before(page):
        log_modes(page)
        page.add_init_script(AT_LIFT)
    page, errors = open_live(make_page, base_url, before_goto=before)
    if action == "toggle":
        assert weave(page, ".mode") == "intro"
        press(page, UNSTITCH_NAME)
    else:
        # The sashing is a click target once it has faded in; the intro is still running then.
        page.wait_for_function("() => document.querySelector('[data-hero]').__weave.fades().sashing.opacity === 1",
                               timeout=5000)
        assert weave(page, ".mode") == "intro"
        page.mouse.click(*project(page, [0, 0, layout(page)["foldZ00"]]))
    wait_for_data_mode(page, "tiles")
    assert modes(page)[:3] == PLAIN_START + [("unstitching", "quilt")]
    r = page.eval_on_selector("[data-hero]", SEAMS_OF, ["__atLift", 0])
    assert (r["checked"], r["missing"]) == (1280, 0), r
    assert modes(page) == PLAIN_START + CYCLE[1:3]
    assert fades(page)["sashing"]["opacity"] == 0
    assert errors == []
