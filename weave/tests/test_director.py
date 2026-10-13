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


# --- Task 3: paths, stagger, fade, settle and snap, stepped at 60 fps. ---

# untilMode(dir, mode) advances 1/60 s at a time (at most 600 frames) until dir.mode is `mode`; returns the
# frames taken, or -1.
STEP_JS = r"""
    const untilMode = (dir, mode) => {
      for (let n = 1; n <= 600; n += 1) { dir.advance(1 / 60); if (dir.mode === mode) return n; }
      return -1;
    };
    const lift = (dir, i) => dir.pose(i).position[2] - quiltPose(i).position[2];
"""


def step(js, body):
    return js(DIRECTOR_JS + STEP_JS + body)


def test_unstitch_settles_in_about_1_6_s(js):
    """U1: the issue's ~1.6 s, from the button (centre), from a corner click, and for the sew-back."""
    r = step(js, r"""
        const a = make(); a.director.start(); a.director.toggle(0);
        const fromButton = untilMode(a.director, 'tiles');
        const back = (a.director.toggle(1), untilMode(a.director, 'quilt'));
        const b = make(); b.director.start(); b.director.click({ part: 'block', slot: 0, point: [-2.2, 1.6] }, 0);
        return { fromButton, back, fromCorner: untilMode(b.director, 'tiles') };
    """)
    print(r)
    for frames in r.values():
        assert 1.3 <= frames / 60 <= 2.1, r


def test_settle_snaps_exactly(js):
    r = step(js, r"""
        d.start(); d.toggle(0);
        const frames = untilMode(d, 'tiles');
        const atTiles = allAt(d, tilePose);
        const still = d.springs.v.every((v) => v.every((x) => x === 0));
        const faded = [d.fade, d.ambient];
        const err = d.lastSettleError;
        const r2 = make(); const e = r2.director;
        e.start(); e.toggle(0);
        for (let n = 0; n < 30; n += 1) e.advance(1 / 60);
        e.toggle(1);
        const reversed = untilMode(e, 'quilt');
        const atQuilt = allAt(e, quiltPose);
        const err2 = e.lastSettleError;
        const held = JSON.stringify(Array.from({ length: 12 }, (_, i) => e.pose(i)));
        for (let n = 0; n < 60; n += 1) e.advance(1 / 60);
        return { frames, atTiles, still, faded, err, reversed, atQuilt, err2,
                 unchanged: held === JSON.stringify(Array.from({ length: 12 }, (_, i) => e.pose(i))) };
    """)
    assert r["frames"] > 0 and r["atTiles"] is True and r["still"] is True
    assert r["faded"] == [0, 0]
    assert 0 < r["err"] <= 1e-3
    assert r["reversed"] > 0 and r["atQuilt"] is True
    assert 0 < r["err2"] <= 1e-3
    assert r["unchanged"] is True


def test_sew_back_snaps_to_the_quilt_pose(js):
    r = step(js, r"""
        d.start(); d.toggle(0); untilMode(d, 'tiles'); d.toggle(1);
        const frames = untilMode(d, 'quilt');
        return { frames, atQuilt: allAt(d, quiltPose), fade: d.fade, ambient: d.ambient };
    """)
    assert r == {"frames": r["frames"], "atQuilt": True, "fade": 1, "ambient": 1} and r["frames"] > 0


def test_stagger_starts_from_the_origin(js):
    r = step(js, r"""
        d.start(); d.toggle(0);
        for (let n = 0; n < 12; n += 1) d.advance(1 / 60);
        const button = [lift(d, 5), lift(d, 0)];
        const c = make().director;
        c.start(); c.click({ part: 'block', slot: 0, point: L.slotCentre(0) }, 0);
        for (let n = 0; n < 12; n += 1) c.advance(1 / 60);
        return { button, click: [lift(c, 5), lift(c, 0)] };
    """)
    centre, corner = r["button"]
    assert centre > corner, r
    centre, corner = r["click"]
    assert corner > centre, r


def test_pause_finishes_a_transition(js):
    r = step(js, r"""
        d.start(); d.toggle(0);
        d.advance(0.3);
        const mid = d.mode;
        d.setPaused(true, 5);
        const after = [d.mode, allAt(d, tilePose), enters.length];
        d.setPaused(true, 6);
        return { mid, after, again: enters.length, click: d.click(HITS.none, 5.3), mode: d.mode,
                 tail: enters.map(([m]) => m) };
    """)
    assert r["mid"] == "unstitching"
    assert r["after"] == ["tiles", True, 3]
    assert r["again"] == 3
    assert r["click"] is False and r["mode"] == "tiles"
    assert r["tail"] == ["quilt", "unstitching", "tiles"]


def test_toggle_reverses_from_the_current_pose(js):
    r = step(js, r"""
        d.start(); d.toggle(0);
        for (let n = 0; n < 30; n += 1) d.advance(1 / 60);
        d.toggle(1);
        let move = 0; let turn = 0;
        let prev = Array.from({ length: 12 }, (_, i) => d.pose(i));
        for (let n = 0; n < 30; n += 1) {
          d.advance(1 / 60);
          const now = Array.from({ length: 12 }, (_, i) => d.pose(i));
          now.forEach((p, i) => {
            move = Math.max(move, Math.hypot(...p.position.map((v, k) => v - prev[i].position[k])));
            turn = Math.max(turn, Math.abs(p.rotY - prev[i].rotY));
          });
          prev = now;
        }
        untilMode(d, 'quilt');
        return { move, turn, modes: enters.map(([m]) => m) };
    """)
    assert r["move"] < 0.05 and r["turn"] < 0.15, r
    assert r["modes"] == ["quilt", "unstitching", "restitching", "quilt"]


def test_fillers_only_fade(js):
    r = step(js, r"""
        const { director: f } = make({ isTile: (i) => i < 10 });
        f.start(); f.toggle(0);
        let moved = 0;
        const check = () => { if (![10, 11].every((i) => same(f.pose(i), quiltPose(i)))) moved += 1; };
        for (let n = 0; n < 600 && f.mode !== 'tiles'; n += 1) { f.advance(1 / 60); check(); }
        const fadeAtTiles = [f.mode, f.fade];
        f.toggle(1);
        for (let n = 0; n < 600 && f.mode !== 'quilt'; n += 1) { f.advance(1 / 60); check(); }
        return { moved, fadeAtTiles, end: f.mode };
    """)
    assert r == {"moved": 0, "fadeAtTiles": ["tiles", 0], "end": "quilt"}


def test_ambient_eases_to_zero_and_back(js):
    r = step(js, r"""
        d.start(); d.toggle(0);
        const seen = [d.ambient];
        let at04 = null;
        for (let n = 1; n <= 600 && d.mode === 'unstitching'; n += 1) {
          d.advance(1 / 60);
          if (d.mode === 'unstitching') seen.push(d.ambient);
          if (n === 24) at04 = d.ambient;
        }
        const tiles = [d.mode, d.ambient];
        d.toggle(1); untilMode(d, 'quilt');
        return { monotone: seen.every((v, k) => k === 0 || v <= seen[k - 1]), at04, tiles, quilt: [d.mode, d.ambient] };
    """)
    assert r["monotone"] is True
    assert r["at04"] < 1
    assert r["tiles"] == ["tiles", 0] and r["quilt"] == ["quilt", 1]


def test_reversal_before_the_stagger_turns_back_without_a_lift(js):
    """A Sew it back one frame into an Unstitch (a double-press): blocks still waiting on their stagger have not
    moved, so turning back must not lift them on a fresh arc; a full unstitch still lifts (control)."""
    r = step(js, r"""
        const peak = (dir, mode) => {
          let top = 0;
          for (let n = 0; n < 600 && dir.mode !== mode; n += 1) {
            dir.advance(1 / 60);
            for (let i = 0; i < 12; i += 1) top = Math.max(top, lift(dir, i));
          }
          return top;
        };
        d.start(); d.toggle(0); d.advance(1 / 60); d.toggle(1);
        const reversed = peak(d, 'quilt');
        const c = make().director;
        c.start(); c.toggle(0);
        return { reversed, full: peak(c, 'tiles'), mode: d.mode };
    """)
    assert r["mode"] == "quilt"
    assert r["full"] > 0.1, r
    assert r["reversed"] < 0.02, r
