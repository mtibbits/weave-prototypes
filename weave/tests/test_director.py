"""motion.js's director: the state table, the one state-change path, the paused click guard, and (Task 3) the
paths, stagger, settle and snap. Pure JS on a blank page: no Three, no DOM, no clock."""
import json

import pytest

from helpers import DEFAULT_IDS

# Builds a director over 12 blocks like scene.js's build: quilt poses at slotCentre with the planned blocks 4-7
# lifted 0.01 and tilted 0.03, tile poses per the contract. The centre comes from the slot (#9: slot = i until a
# drag moves block i), the lift and tilt from the block. `enters` records [mode, from, director.mode] per entry.
# make({ isTile, intro }) builds a fresh one (intro: true gives INTRO_TABLE, a fixed table that never shares
# introScatter's seed, or a function is passed as introFrom); `d` is the default. allAtSlots(dir, poseOf) checks every
# block against poseOf(i, dir.slotOf(i)). IDS is the shipped panels' ids, for the real seeded scatter.
DIRECTOR_JS = r"""
    const M = await import('/public/js/motion.js');
    const L = await import('/public/js/layout.js');
    const planned = (i) => i >= 4 && i <= 7;
    const quiltPose = (i, slot = i) => ({ position: [...L.slotCentre(slot), planned(i) ? 0.01 : 0], rotY: 0,
                                          rotZ: planned(i) ? 0.03 : 0, morph: 0 });
    const tilePose = (i, slot = i) => ({ position: [...L.slotCentre(slot, 'tiles'), 0], rotY: Math.PI, rotZ: 0,
                                         morph: 1 });
    const INTRO_TABLE = (i) => ({ offset: [0.5 * ((i % 3) - 1), 0.4, 0.8], wait: 0.05 * i });
    const IDS = """ + json.dumps(DEFAULT_IDS) + r""";
    const make = ({ isTile = () => true, intro = null } = {}) => {
      const enters = [];
      const introFrom = intro === true ? INTRO_TABLE : intro ?? undefined;
      const director = new M.Director({ count: 12, quiltPose, tilePose, isTile, introFrom,
        onEnter: (mode, from) => enters.push([mode, from, director.mode]) });
      return { director, enters };
    };
    const { director: d, enters } = make();
    const same = (a, b) => a.position.every((v, k) => v === b.position[k]) && a.rotY === b.rotY && a.rotZ === b.rotZ
      && a.morph === b.morph;
    const allAt = (dir, poseOf) => Array.from({ length: 12 }, (_, i) => same(dir.pose(i), poseOf(i))).every(Boolean);
    const allAtSlots = (dir, poseOf) => Array.from({ length: 12 },
      (_, i) => same(dir.pose(i), poseOf(i, dir.slotOf(i)))).every(Boolean);
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
          d.grab(0, L.slotCentre(0, 'tiles')); d.dragTo(L.slotCentre(5, 'tiles')); d.drop();
          for (let i = 0; i < 60; i += 1) d.advance(1 / 60);
          d.toggle(1);
          for (let i = 0; i < 200; i += 1) d.advance(1 / 60);
          const { director: e } = make({ intro: (i) => M.introScatter(IDS[i]) });
          e.start('intro');
          for (let i = 0; i < 200; i += 1) e.advance(1 / 60);
          if (e.mode !== 'quilt') return e.mode;
        } finally {
          [Date.now, performance.now, Math.random] = saved;
        }
        return d.mode;
    """)
    assert r == "quilt"


def test_toggle_inside_the_tiles_entry_sews_back(js):
    """verify.py's window presses the toggle from its weave:mode handler on tiles: the settle has already cleared
    the leg, so this is a fresh sew-back (not a reversal) that settles on the quilt pose."""
    r = run(js, r"""
        const log = [];
        const dir = new M.Director({ count: 12, quiltPose, tilePose, isTile: () => true,
          onEnter: (mode, from) => { log.push([mode, from, dir.mode]); if (mode === 'tiles') dir.toggle(0); } });
        dir.start(); dir.toggle(0);
        for (let i = 0; i < 400; i += 1) dir.advance(1 / 60);
        return { log, home: allAt(dir, quiltPose) };
    """)
    assert r["log"] == [["quilt", None, "quilt"], ["unstitching", "quilt", "unstitching"], ["tiles", "unstitching", "tiles"],
                        ["restitching", "tiles", "restitching"], ["quilt", "restitching", "quilt"]]
    assert r["home"] is True


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


# --- #9: the slot map, the drag and the reflow. ---

# c(k) is tile slot k's centre; tiles(dir) brings a director to settled tiles; slotsOf(dir) is blockAt over slots
# 0-11; near(a, b, eps) compares two poses to eps, and allNear(dir, poseOf, eps) every block against its slot's.
DRAG_JS = r"""
    const c = (k) => L.slotCentre(k, 'tiles');
    const tiles = (dir) => { dir.start(); dir.toggle(0); dir.finish(); return dir; };
    const slotsOf = (dir) => Array.from({ length: 12 }, (_, k) => dir.blockAt(k));
    const near = (a, b, eps) => a.position.every((v, k) => Math.abs(v - b.position[k]) <= eps)
      && [a.rotY - b.rotY, a.rotZ - b.rotZ, a.morph - b.morph].every((x) => Math.abs(x) <= eps);
    const allNear = (dir, poseOf, eps) => Array.from({ length: 12 },
      (_, i) => near(dir.pose(i), poseOf(i, dir.slotOf(i)), eps)).every(Boolean);
    const MOVED = [1, 2, 3, 4, 5, 0, 6, 7, 8, 9, 10, 11];
"""

MOVED = [1, 2, 3, 4, 5, 0, 6, 7, 8, 9, 10, 11]


def drag(js, body):
    return js(DIRECTOR_JS + STEP_JS + DRAG_JS + body)


def test_grab_only_in_settled_tiles(js):
    states = ", ".join(f"(() => {{ const {{ director: d }} = make(); d.start(); {REACH[s]} return d.grab(0, c(0)); }})()"
                       for s in ("quilt", "unstitching", "tiles", "restitching"))
    r = drag(js, f"""
        const byState = [{states}];
        const t = tiles(make().director);
        const first = t.grab(0, c(0));
        const second = t.grab(1, c(1));
        const f = tiles(make({{ isTile: (i) => i < 10 }}).director);
        return {{ byState, first, second, filler: f.grab(10, c(10)), dragging: [t.dragging, f.dragging] }};
    """)
    assert r["byState"] == [False, False, True, False]
    assert r["first"] is True and r["second"] is False
    assert r["filler"] is False
    assert r["dragging"] == [True, False]


def test_drag_reflows_by_move_and_shift(js):
    r = drag(js, r"""
        const t = tiles(make().director);
        t.grab(0, c(0));
        const firstMoves = t.dragTo(c(2));
        const lastMoves = t.dragTo(c(5));
        const direct = tiles(make().director);
        direct.grab(0, c(0)); direct.dragTo(c(5));
        const targets = [1, 2, 3, 4, 5].every((b) => t.springs.target[b]
          .every((v, k) => v === tilePose(b, t.slotOf(b)).position[k]));
        return { order: slotsOf(t), direct: slotsOf(direct), dragged: t.pose(0).position, want: [...c(5), M.DRAG.lift],
                 targets, firstMoves, lastMoves, slotOf: Array.from({ length: 12 }, (_, i) => t.slotOf(i)) };
    """)
    assert r["order"] == MOVED
    assert r["direct"] == MOVED
    assert [r["slotOf"][b] for b in r["order"]] == list(range(12))
    assert r["targets"] is True
    assert r["dragged"] == r["want"]
    assert sorted(r["firstMoves"]) == [[0, 2], [1, 0], [2, 1]]
    assert sorted(r["lastMoves"]) == [[0, 5], [3, 2], [4, 3], [5, 4]]


def test_drag_keeps_the_grab_offset(js):
    r = drag(js, r"""
        const t = tiles(make().director);
        t.grab(0, [c(0)[0] + 0.1, c(0)[1]]);
        t.dragTo([c(5)[0] + 0.1, c(5)[1]]);
        return { at: t.pose(0).position, want: c(5) };
    """)
    assert abs(r["at"][0] - r["want"][0]) <= 1e-12 and abs(r["at"][1] - r["want"][1]) <= 1e-12, r


def test_drop_lands_in_the_current_slot(js):
    r = drag(js, r"""
        const t = tiles(make().director);
        t.grab(0, c(0)); t.dragTo(c(5));
        const dropped = t.drop();
        for (let n = 0; n < 300; n += 1) t.advance(1 / 60);
        const unpaused = allNear(t, tilePose, 1e-3);
        const z = Math.max(...Array.from({ length: 12 }, (_, i) => Math.abs(t.pose(i).position[2])));
        const p = make().director;
        p.start(); p.setPaused(true, 0); p.toggle(0);
        p.grab(0, c(0)); p.dragTo(c(5));
        const others = Array.from({ length: 11 }, (_, k) => k + 1).every((i) => same(p.pose(i), tilePose(i, p.slotOf(i))));
        p.drop();
        return { dropped, unpaused, z, mode: p.mode, moved: slotsOf(p), others, all: allAtSlots(p, tilePose) };
    """)
    assert r["dropped"] is True
    assert r["unpaused"] is True and r["z"] <= 1e-3, r
    assert r["mode"] == "tiles" and r["moved"] == MOVED
    assert r["others"] is True and r["all"] is True


def test_drop_reports_once(js):
    r = drag(js, r"""
        const t = tiles(make().director);
        t.grab(0, c(0)); t.dragTo(c(5));
        const first = t.drop();
        const held = JSON.stringify(Array.from({ length: 12 }, (_, i) => t.pose(i)));
        const second = t.drop();
        const unchanged = held === JSON.stringify(Array.from({ length: 12 }, (_, i) => t.pose(i)));
        return { first, second, unchanged, after: t.dragTo(c(7)), dragging: t.dragging, order: slotsOf(t) };
    """)
    assert r["first"] is True and r["second"] is False and r["unchanged"] is True
    assert r["after"] == [] and r["dragging"] is False
    assert r["order"] == MOVED


def test_drag_past_the_last_tile_clamps(js):
    r = drag(js, r"""
        const f = tiles(make({ isTile: (i) => i < 10 }).director);
        const built = [10, 11].map((i) => f.pose(i));
        f.grab(0, c(0)); f.dragTo(c(11));
        return { slot0: f.slotOf(0), fillers: [f.slotOf(10), f.slotOf(11)], blockAt: [f.blockAt(10), f.blockAt(11)],
                 still: [10, 11].every((i, k) => same(f.pose(i), built[k]) && same(f.pose(i), quiltPose(i))) };
    """)
    assert r["slot0"] == 9
    assert r["fillers"] == [10, 11] and r["blockAt"] == [10, 11]
    assert r["still"] is True


def test_toggle_mid_drag_drops_then_sews_back(js):
    r = drag(js, r"""
        const { director: e, enters: log } = make();
        tiles(e); e.grab(0, c(0)); e.dragTo(c(5));
        const k = log.length;
        e.toggle(100);
        const dragging = e.dragging;
        const tail = log.slice(k).map(([m, f]) => [m, f]);
        const frames = untilMode(e, 'quilt');
        return { dragging, tail, frames, home: allAtSlots(e, quiltPose), block0: e.pose(0).position,
                 want: quiltPose(0, 5).position, slot0: e.slotOf(0) };
    """)
    assert r["dragging"] is False
    assert r["tail"] == [["restitching", "tiles"]]
    assert r["frames"] > 0
    assert r["home"] is True and r["slot0"] == 5
    assert r["block0"] == r["want"]


def test_reorder_survives_a_cycle(js):
    r = drag(js, r"""
        const t = tiles(make().director);
        t.grab(0, c(0)); t.dragTo(c(5)); t.drop();
        t.toggle(1); const back = untilMode(t, 'quilt');
        const home = allAtSlots(t, quiltPose);
        t.toggle(2); const out = untilMode(t, 'tiles');
        return { back, out, home, at: allAtSlots(t, tilePose), order: slotsOf(t) };
    """)
    assert r["back"] > 0 and r["out"] > 0
    assert r["home"] is True and r["at"] is True
    assert r["order"] == MOVED


def test_pause_after_drop_snaps_the_tiles(js):
    r = drag(js, r"""
        const t = tiles(make().director);
        t.grab(0, c(0)); t.dragTo(c(5)); t.drop();
        t.advance(1 / 60);
        const moving = !allNear(t, tilePose, 1e-9);
        t.setPaused(true, 50);
        const landed = allNear(t, tilePose, 1e-9);
        const m = tiles(make().director);
        m.grab(0, c(0)); m.dragTo(c(5));
        m.setPaused(true, 60);
        const others = Array.from({ length: 11 }, (_, k) => k + 1).every((i) => near(m.pose(i), tilePose(i, m.slotOf(i)), 1e-9));
        return { moving, landed, others, modes: [t.mode, m.mode], dragging: m.dragging };
    """)
    assert r["moving"] is True  # the control: one frame after an unpaused drop the tiles are still travelling
    assert r["landed"] is True
    assert r["others"] is True
    assert r["modes"] == ["tiles", "tiles"] and r["dragging"] is True


def test_click_mid_drag_drops_then_sews_back(js):
    r = drag(js, r"""
        const t = tiles(make().director);
        t.grab(0, c(0)); t.dragTo(c(5));
        const acted = t.click(HITS.none, 100);
        const dragging = t.dragging;
        const frames = untilMode(t, 'quilt');
        return { acted, dragging, frames, home: allAtSlots(t, quiltPose), order: slotsOf(t) };
    """)
    assert r["acted"] is True and r["dragging"] is False
    assert r["frames"] > 0 and r["home"] is True and r["order"] == MOVED


# --- #10: the intro leg. ---

def test_intro_is_the_first_state(js):
    r = step(js, r"""
        const { director: e, enters: log } = make({ intro: true });
        e.start('intro');
        const fade0 = e.fade;
        const seated = Array.from({ length: 12 }, (_, i) => {
          const p = e.pose(i); const q = quiltPose(i); const o = INTRO_TABLE(i).offset;
          return p.position.every((v, k) => v === q.position[k] + o[k]) && p.rotZ === q.rotZ;
        });
        for (let n = 0; n < 10; n += 1) e.advance(1 / 60);
        return { log, fade0, seated, fade: e.fade, mode: e.mode };
    """)
    assert r["log"] == [["intro", None, "intro"]]
    assert r["fade0"] == 0
    assert r["seated"] == [True] * 12
    assert r["fade"] is not None and 0 < r["fade"] < 1, r
    assert r["mode"] == "intro"


@pytest.mark.parametrize("rate", [60, 20])
@pytest.mark.parametrize("scatter", ["table", "seeded"])
def test_intro_settles_in_under_3_s(js, scatter, rate):
    """U1: the intro settles (D40) inside 3 s of scene time, on the fixed table and on the real seeded scatter."""
    intro = "true" if scatter == "table" else "(i) => M.introScatter(IDS[i])"
    r = step(js, f"""
        const {{ director: e, enters: log }} = make({{ intro: {intro} }});
        e.start('intro');
        let frames = -1;
        for (let n = 1; n <= 600; n += 1) {{ e.advance(1 / {rate}); if (e.mode === 'quilt') {{ frames = n; break; }} }}
        return {{ frames, tail: log.slice(1), home: allAt(e, quiltPose), fade: e.fade }};
    """)
    print(scatter, rate, r["frames"] / rate)
    assert r["frames"] > 0 and r["frames"] / rate <= 3.0, r
    assert r["tail"] == [["quilt", "intro", "quilt"]]
    assert r["home"] is True
    assert r["fade"] == 1


def test_intro_without_tiles_only_fades(js):
    r = step(js, r"""
        const { director: e } = make({ isTile: () => false, intro: true });
        e.start('intro');
        let moved = 0; let time = null;
        for (let n = 1; n <= 600; n += 1) {
          e.advance(1 / 60);
          if (!allAt(e, quiltPose)) moved += 1;
          if (e.mode === 'quilt') { time = e.time; break; }
        }
        return { moved, time, fadeDur: M.INTRO.fadeDur, fade: e.fade };
    """)
    assert r["moved"] == 0
    assert r["time"] is not None and abs(r["time"] - r["fadeDur"]) <= 1 / 60 + 1e-9, r
    assert r["fade"] == 1


def test_pause_during_intro_jumps_to_the_quilt(js):
    r = step(js, r"""
        const { director: e, enters: log } = make({ intro: true });
        e.start('intro');
        for (let n = 0; n < 10; n += 1) e.advance(1 / 60);
        const mid = e.mode;
        e.setPaused(true, 5);
        return { mid, log: log.map(([m, f]) => [m, f]), home: allAt(e, quiltPose), fade: e.fade, snapAt: e.lastSnapAt };
    """)
    assert r["mid"] == "intro"
    assert r["log"] == [["intro", None], ["quilt", "intro"]]
    assert r["home"] is True and r["fade"] == 1 and r["snapAt"] == 5


@pytest.mark.parametrize("action", ["toggle", "click"])
def test_unstitch_during_intro_finishes_it_first(js, action):
    act = "e.toggle(1)" if action == "toggle" else "e.click(HITS.block, 1)"
    r = step(js, f"""
        const log = [];
        let atLift = null;
        const e = new M.Director({{ count: 12, quiltPose, tilePose, isTile: () => true, introFrom: INTRO_TABLE,
          onEnter: (mode, from) => {{ log.push([mode, from]); if (mode === 'unstitching') atLift = allAt(e, quiltPose); }} }});
        e.start('intro');
        for (let n = 0; n < 10; n += 1) e.advance(1 / 60);
        const acted = {act};
        const reached = untilMode(e, 'tiles');
        const c = make({{ intro: true }}).director;
        c.start('intro'); c.advance(1 / 60);
        const none = c.click(HITS.none, 1);
        return {{ acted, log, atLift, reached, tiles: allAtSlots(e, tilePose), none, noneMode: c.mode }};
    """)
    assert r["acted"] is True
    assert r["log"][:3] == [["intro", None], ["quilt", "intro"], ["unstitching", "quilt"]]
    assert r["atLift"] is True
    assert r["reached"] > 0 and r["tiles"] is True
    assert r["none"] is False and r["noneMode"] == "intro"


def test_toggle_inside_the_intro_settle_does_not_double(js):
    r = step(js, r"""
        const log = [];
        let toggled = false;
        const e = new M.Director({ count: 12, quiltPose, tilePose, isTile: () => true, introFrom: INTRO_TABLE,
          onEnter: (mode, from) => {
            log.push([mode, from]);
            if (mode === 'quilt' && !toggled) { toggled = true; e.toggle(2); }
          } });
        e.start('intro');
        for (let n = 0; n < 10; n += 1) e.advance(1 / 60);
        e.toggle(1);
        return { log, mode: e.mode };
    """)
    assert [m for m, _ in r["log"]].count("unstitching") == 1, r
    assert r["log"] == [["intro", None], ["quilt", "intro"], ["unstitching", "quilt"]]
    assert r["mode"] == "unstitching"


def test_progress_follows_each_flight(js):
    r = step(js, r"""
        const fresh = make({ intro: true }).director;
        const unstarted = fresh.progress(11);
        const { director: e } = make({ intro: true });
        e.start('intro');
        const seen = [];
        for (let n = 0; n < 600 && e.mode === 'intro'; n += 1) { seen.push([e.time, e.progress(11)]); e.advance(1 / 60); }
        return { unstarted, seen, wait: INTRO_TABLE(11).wait, pathDur: M.INTRO.pathDur, after: e.progress(11), mode: e.mode };
    """)
    assert r["unstarted"] == 1 and r["mode"] == "quilt" and r["after"] == 1
    wait, dur = r["wait"], r["pathDur"]
    before = [p for t, p in r["seen"] if t <= wait]
    flying = [p for t, p in r["seen"] if wait + 1e-9 < t < wait + dur - 1e-9]
    done = [p for t, p in r["seen"] if t >= wait + dur + 1e-9]
    assert before and all(p == 0 for p in before)
    assert flying and all(0 < p < 1 for p in flying) and flying == sorted(flying)
    assert done and all(p == 1 for p in done)


def test_intro_scatter_is_seeded_and_bounded(js):
    r = step(js, r"""
        return { a: M.introScatter('manpower'), b: M.introScatter('manpower'), other: M.introScatter('hiring'),
                 all: IDS.map((id) => M.introScatter(id)), INTRO: M.INTRO };
    """)
    assert r["a"] == r["b"] and r["a"] != r["other"]
    lim = r["INTRO"]
    for s in r["all"]:
        dx, dy, dz = s["offset"]
        assert abs(dx) <= lim["scatter"] and abs(dy) <= lim["scatter"], s
        assert lim["rise"][0] <= dz <= lim["rise"][1], s
        assert 0 <= s["wait"] <= lim["spread"], s
    assert r["INTRO"] == {"pathDur": 1.2, "spread": 0.6, "fadeDur": 0.8, "scatter": 1.2, "rise": [0.6, 1.2]}
