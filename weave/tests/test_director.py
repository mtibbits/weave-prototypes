"""motion.js's director: the state table, the one state-change path, the paused click guard, and (Task 3) the
paths, stagger, settle and snap. Pure JS on a blank page: no Three, no DOM, no clock."""
import pytest

# Builds a director over 12 blocks like scene.js's build: quilt poses at slotCentre with the planned slots 4-7
# lifted 0.01 and tilted 0.03, tile poses per the contract. `enters` records [mode, from, director.mode] per entry.
# make({ isTile }) builds a fresh one; `d` is the default.
DIRECTOR_JS = r"""
    const M = await import('/public/js/motion.js');
    const L = await import('/public/js/layout.js');
    const planned = (i) => i >= 4 && i <= 7;
    const quiltPose = (i) => ({ position: [...L.slotCentre(i), planned(i) ? 0.01 : 0], rotY: 0,
                                rotZ: planned(i) ? 0.03 : 0, morph: 0 });
    const tilePose = (i) => ({ position: [...L.slotCentre(i, 'tiles'), 0], rotY: Math.PI, rotZ: 0, morph: 1 });
    const make = ({ isTile = () => true } = {}) => {
      const enters = [];
      const director = new M.Director({ count: 12, quiltPose, tilePose, isTile,
        onEnter: (mode, from) => enters.push([mode, from, director.mode]) });
      return { director, enters };
    };
    const { director: d, enters } = make();
    const same = (a, b) => a.position.every((v, k) => v === b.position[k]) && a.rotY === b.rotY && a.rotZ === b.rotZ
      && a.morph === b.morph;
    const allAt = (dir, poseOf) => Array.from({ length: 12 }, (_, i) => same(dir.pose(i), poseOf(i))).every(Boolean);
    const HITS = { block: { part: 'block', slot: 5, point: [-0.57, 0] }, sashing: { part: 'sashing', slot: null, point: [0, 0] },
                   tile: { part: 'tile', slot: 5, point: [-0.62, 0] }, none: { part: 'none', slot: null, point: [0, 0] } };
"""


def run(js, body):
    return js(DIRECTOR_JS + body)


def test_first_state_enters_from_null(js):
    r = run(js, "const before = d.mode; d.start(); return { before, enters };")
    assert r["before"] is None
    assert r["enters"] == [["quilt", None, "quilt"]]


def test_start_seeds_the_quilt_pose(js):
    r = run(js, "const built = allAt(d, quiltPose); d.start(); return [built, allAt(d, quiltPose)];")
    assert r == [True, True]


def test_on_enter_sees_the_new_mode(js):
    r = run(js, r"""
        d.start(); d.setPaused(true, 0); d.toggle(10); d.toggle(500); d.click(HITS.block, 1000);
        return enters;
    """)
    assert len(r) == 7
    assert all(mode == hook for mode, _, hook in r)


# (start state, action, expected enters after it, expected return). Every non-empty table cell, plus a quilt +
# none-click and a tiles + tile-click no-op. The start states are reached unpaused with toggles; mid-transition
# states stay mid-transition because nothing advances.
TABLE = [
    ("quilt", "toggle", [["unstitching", "quilt"]], True),
    ("quilt", "block", [["unstitching", "quilt"]], True),
    ("quilt", "sashing", [["unstitching", "quilt"]], True),
    ("quilt", "none", [], False),
    ("unstitching", "toggle", [["restitching", "unstitching"]], True),
    ("tiles", "toggle", [["restitching", "tiles"]], True),
    ("tiles", "tile", [], False),
    ("tiles", "none", [["restitching", "tiles"]], True),
    ("restitching", "toggle", [["unstitching", "restitching"]], True),
]

REACH = {
    "quilt": "",
    "unstitching": "d.toggle(0);",
    "tiles": "d.toggle(0); d.finish();",
    "restitching": "d.toggle(0); d.finish(); d.toggle(1);",
}


@pytest.mark.parametrize("start,action,expected,acted", TABLE,
                         ids=[f"{s}-{a}" for s, a, _, _ in TABLE])
def test_state_table(js, start, action, expected, acted):
    act = "d.toggle(5000)" if action == "toggle" else f"d.click(HITS.{action}, 5000)"
    r = run(js, f"""
        d.start(); {REACH[start]}
        const n = enters.length;
        const before = d.mode;
        const result = {act};
        return {{ before, result, tail: enters.slice(n).map(([m, f]) => [m, f]) }};
    """)
    assert r["before"] == start
    assert r["tail"] == expected
    assert r["result"] is acted


@pytest.mark.parametrize("mid", ["unstitching", "restitching"])
def test_clicks_mid_transition_are_ignored(js, mid):
    r = run(js, f"""
        d.start(); {REACH[mid]}
        const n = enters.length;
        const results = ['block', 'sashing', 'tile', 'none'].map((k) => d.click(HITS[k], 5000));
        return {{ mode: d.mode, results, added: enters.length - n }};
    """)
    assert r == {"mode": mid, "results": [False] * 4, "added": 0}


def test_paused_toggle_passes_through_both_states(js):
    r = run(js, r"""
        d.start(); d.setPaused(true, 0);
        d.toggle(10);
        const first = enters.map(([m, f]) => [m, f]);
        d.toggle(20);
        return { first, all: enters.map(([m, f]) => [m, f]) };
    """)
    assert r["first"] == [["quilt", None], ["unstitching", "quilt"], ["tiles", "unstitching"]]
    assert r["all"][3:] == [["restitching", "tiles"], ["quilt", "restitching"]]


def test_paused_click_guard_is_400_ms(js):
    r = run(js, r"""
        d.start(); d.setPaused(true, 0);
        const out = [];
        out.push([d.click(HITS.none, 100), d.mode]);
        out.push([d.click(HITS.sashing, 150), d.mode]);
        out.push([d.click(HITS.none, 300), d.mode]);
        out.push([d.click(HITS.none, 549.9), d.mode]);
        out.push([d.click(HITS.none, 550), d.mode]);
        return out;
    """)
    assert r == [[False, "quilt"], [True, "tiles"], [False, "tiles"], [False, "tiles"], [True, "quilt"]]


def test_guard_is_paused_only(js):
    r = run(js, r"""
        d.start(); d.setPaused(true, 0);
        d.toggle(10);
        const paused = d.mode;
        d.setPaused(false, 20);
        return [paused, d.click(HITS.none, 30), d.mode];
    """)
    assert r == ["tiles", True, "restitching"]


def test_director_reads_no_clock(js):
    r = run(js, r"""
        const saved = [Date.now, performance.now, Math.random];
        const boom = () => { throw new Error('the director read a clock'); };
        try {
          Date.now = boom; performance.now = boom; Math.random = boom;
          d.start(); d.toggle(0);
          for (let i = 0; i < 200; i += 1) d.advance(1 / 60);
          d.toggle(1);
          for (let i = 0; i < 200; i += 1) d.advance(1 / 60);
        } finally {
          [Date.now, performance.now, Math.random] = saved;
        }
        return d.mode;
    """)
    assert r in ("quilt", "restitching")
