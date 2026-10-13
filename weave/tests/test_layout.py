"""layout.js: the quilt and tile grids, the puff and fold, the shadow plane, and the slot maths #9 builds on."""
import math

import pytest

LAYOUT_JS = "const L = await import('/public/js/layout.js');"


def run(js, body):
    return js(LAYOUT_JS + body)


def test_quilt_and_tile_grid_sizes(js):
    r = run(js, r"""
        const fabric = await import('/public/js/fabric.js');
        const { LAYOUT } = L;
        return {
          quilt: [LAYOUT.quiltW, LAYOUT.quiltH], tiles: [LAYOUT.tilesW, LAYOUT.tilesH],
          five: [LAYOUT.cols, LAYOUT.rows, LAYOUT.block, LAYOUT.sashing, LAYOUT.border],
          pitch: [LAYOUT.pitch, LAYOUT.tilePitch], slots: LAYOUT.slots, segments: LAYOUT.segments,
          frozen: Object.isFrozen(LAYOUT),
          quiltSize: fabric.quiltSize(LAYOUT), sashingSize: fabric.sashingSize(LAYOUT),
        };
    """)
    assert all(abs(a - b) < 1e-9 for a, b in zip(r["quilt"], [4.70, 3.56]))
    assert all(abs(a - b) < 1e-9 for a, b in zip(r["tiles"], [4.72, 3.48]))
    assert r["five"] == [4, 3, 1.0, 0.14, 0.14]
    assert all(abs(a - b) < 1e-9 for a, b in zip(r["pitch"], [1.14, 1.24]))
    assert r["slots"] == 12 and r["segments"] == 40 and r["frozen"] is True
    assert all(abs(a - b) < 1e-9 for a, b in zip(r["quiltSize"], r["quilt"]))
    assert r["sashingSize"] == [1204, 912]


@pytest.mark.parametrize("mode", ["quilt", "tiles"])
def test_slot_centres_match_the_issue_formulas(js, mode):
    centres = run(js, f"return Array.from({{ length: 12 }}, (_, i) => L.slotCentre(i, '{mode}'));")
    x0, y0, p = (-1.71, 1.14, 1.14) if mode == "quilt" else (-1.86, 1.24, 1.24)
    assert len(centres) == 12
    for i, (x, y) in enumerate(centres):
        c, r = i % 4, i // 4
        assert abs(x - (x0 + p * c)) < 1e-9 and abs(y - (y0 - p * r)) < 1e-9, (i, x, y)


def test_puff_is_zero_on_block_edges(js):
    r = run(js, r"""
        const t = Array.from({ length: 41 }, (_, i) => i / 40);
        const edges = [];
        for (const s of t) edges.push(L.puffZ(s, 0), L.puffZ(s, 1), L.puffZ(0, s), L.puffZ(1, s));
        return { edges, centre: L.puffZ(0.5, 0.5), puff: L.LAYOUT.puff };
    """)
    assert len(r["edges"]) == 164 and all(z == 0 for z in r["edges"])
    assert 0 < r["centre"] <= r["puff"]


def test_fold_stays_within_half_a_unit(js):
    r = run(js, r"""
        let worst = 0; let n = 0;
        for (let x = -3; x <= 3.0001; x += 0.02) {
          for (let y = -2.2; y <= 2.2001; y += 0.02) { worst = Math.max(worst, Math.abs(L.foldZ(x, y))); n += 1; }
        }
        const far = [[50, 50], [-50, 50], [50, -50], [-50, -50]].map(([x, y]) => Math.abs(L.foldZ(x, y)));
        return { worst, n, far };
    """)
    assert r["n"] > 60000
    assert r["worst"] <= 0.5 and all(z <= 0.5 for z in r["far"])
    assert r["worst"] > 0.01  # control: the fold is really there


def test_fold_vanishes_at_the_top_edge(js):
    r = run(js, r"""
        const { quiltW: W, quiltH: H } = L.LAYOUT;
        const xs = Array.from({ length: 41 }, (_, i) => -W / 2 + (W * i) / 40);
        return { top: xs.map((x) => Math.abs(L.foldZ(x, H / 2))), middle: xs.map((x) => Math.abs(L.foldZ(x, 0))) };
    """)
    assert len(r["top"]) == 41 and max(r["top"]) <= 1e-9
    assert max(r["middle"]) > 0.01  # control


def rotate(v, axis, angle):
    x, y, z = v
    c, s = math.cos(angle), math.sin(angle)
    if axis == "x":
        return (x, c * y - s * z, s * y + c * z)
    return (c * x + s * z, y, -s * x + c * z)


def test_shadow_clears_the_deepest_excursion(js):
    r = run(js, r"""
        const { LAYOUT } = L;
        return { max: L.maxExcursion(), shadowZ: LAYOUT.shadowZ, amp: LAYOUT.ambientMax, rodY: LAYOUT.rod.y,
                 W: LAYOUT.quiltW, H: LAYOUT.quiltH };
    """)
    amp = r["amp"]
    worst = 0.0
    for cx in (-r["W"] / 2, r["W"] / 2):
        for cy in (-r["H"] / 2, r["H"] / 2):
            v0 = (cx, cy - r["rodY"], 0.0)
            for sway in (-amp["sway"], 0, amp["sway"]):
                for tx in (-amp["tiltX"], 0, amp["tiltX"]):
                    for ty in (-amp["tiltY"], 0, amp["tiltY"]):
                        v = rotate(rotate(rotate(v0, "x", sway), "x", tx), "y", ty)
                        worst = max(worst, abs(v[2]))
    assert worst > 0.05  # the ambient motion really moves the corners
    assert abs(r["max"] - worst) < 1e-9
    assert r["shadowZ"] <= -0.6
    assert abs(r["shadowZ"] - -(0.5 + worst + 0.1)) < 1e-9


# The one continuity predicate, for the real fold and the planted step alike.
JUMP_JS = r"""
    const { LAYOUT } = L;
    const jump = (f, e, t, axis) => (axis === 'x'
      ? Math.abs(f(e - 1e-7, t) - f(e + 1e-7, t)) : Math.abs(f(t, e - 1e-7) - f(t, e + 1e-7)));
    const xs = []; const ys = [];
    for (let i = 0; i < 4; i += 1) { const [x] = L.slotCentre(i); xs.push(x - 0.5, x + 0.5); }
    for (let i = 0; i < 12; i += 4) { const [, y] = L.slotCentre(i); ys.push(y - 0.5, y + 0.5); }
    const samples = (half) => Array.from({ length: 41 }, (_, i) => -half + (2 * half * i) / 40);
    const worst = (f) => {
      let max = 0; let n = 0;
      for (const e of xs) for (const t of samples(LAYOUT.quiltH / 2)) { max = Math.max(max, jump(f, e, t, 'x')); n += 1; }
      for (const e of ys) for (const t of samples(LAYOUT.quiltW / 2)) { max = Math.max(max, jump(f, e, t, 'y')); n += 1; }
      return [max, n];
    };
"""


def test_fold_is_continuous_across_block_edges(js):
    r = run(js, JUMP_JS + r"""
        const step = (x, y) => (x > xs[2] ? 0.2 : 0) + L.foldZ(x, y);
        return { fold: worst(L.foldZ), step: worst(step) };
    """)
    worst, count = r["fold"]
    assert count == (8 + 6) * 41
    assert worst < 1e-5
    assert r["step"][0] >= 1e-5  # planted control: the same predicate catches a step


def test_move_item_worked_example(js):
    r = run(js, r"""
        const order = Array.from({ length: 12 }, (_, i) => i + 1);
        const moved = L.moveItem(order, 0, 5);
        const same = L.moveItem(order, 3, 3);
        return { moved, back: L.moveItem(moved, 5, 0), order, same, fresh: same !== order };
    """)
    assert r["moved"] == [2, 3, 4, 5, 6, 1, 7, 8, 9, 10, 11, 12]
    assert r["back"] == list(range(1, 13)) and r["order"] == list(range(1, 13))
    assert r["same"] == list(range(1, 13)) and r["fresh"] is True


@pytest.mark.parametrize("mode", ["quilt", "tiles"])
def test_nearest_slot_returns_each_centres_own_slot(js, mode):
    found = run(js, f"return Array.from({{ length: 12 }}, (_, i) => L.nearestSlot(...L.slotCentre(i, '{mode}'), '{mode}'));")
    assert found == list(range(12))


def test_nearest_slot_is_always_a_slot(js):
    found = run(js, r"""
        return [L.nearestSlot(1e6, 1e6), L.nearestSlot(-1e6, -1e6, 'tiles'), L.nearestSlot(NaN, 0),
                L.nearestSlot(0, NaN, 'tiles'), L.nearestSlot(Infinity, 0), L.nearestSlot(-Infinity, Infinity),
                L.nearestSlot(0.5, 0.2, 'nope')];
    """)
    assert len(found) == 7
    assert all(isinstance(i, int) and 0 <= i <= 11 for i in found), found
    assert found[2] == 0 and found[3] == 0
