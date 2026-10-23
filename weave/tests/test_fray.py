"""fray.js: the Help corner's loose threads (#18), a pure simulation: shape, determinism, the stir, the clamp, the rest
pose and the header #19 builds on."""
import re
from pathlib import Path

import pytest

from helpers import header_lines, header_prose

FRAY = Path(__file__).resolve().parents[1] / "public" / "js" / "fray.js"

# Ten pins 0.16 apart along a flat edge, as help.js spaces them, and a sim factory. sum(a, b) is the summed point
# distance between two pose snapshots, per strand.
FRAY_JS = r"""
const F = await import('/public/js/fray.js');
const pins = Array.from({ length: 10 }, (_, k) => [0.08 + 0.16 * k, 0, 0.014]);
const make = (opts = {}) => F.createFray({ pins, length: 0.6, seed: 12345, ...opts });
const pose = (f) => f.strands.map((s) => s.points.map((p) => [...p]));
const run = (f, seconds, each) => { for (let i = 0; i < Math.round(seconds * 60); i += 1) { if (each) each(i); f.advance(1 / 60); } };
const dist = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]);
const moved = (a, b) => a.map((s, i) => s.reduce((t, p, j) => t + dist(p, b[i][j]), 0));
"""


def run(js, body):
    return js(FRAY_JS + body)


def test_fray_shape(js):
    r = run(js, r"""
        const f = make();
        return { strands: f.strands.length, points: f.strands.map((s) => s.points.length),
                 sizes: [...new Set(f.strands.flatMap((s) => s.points.map((p) => p.length)))],
                 pinned: f.strands.every((s, k) => dist(s.points[0], pins[k]) === 0),
                 state: f.state, frayAmount: f.frayAmount, hanging: f.strands.map((s) => s.hanging),
                 stir: f.stir, clock: f.clock, consts: [F.STRANDS, F.POINTS, F.STEP, F.MAX_DT, F.STIR_RADIUS] };
    """)
    assert r["strands"] == 10 and r["points"] == [16] * 10 and r["sizes"] == [3]
    assert r["pinned"] is True
    assert r["state"] == "frayed" and r["frayAmount"] == 1 and r["hanging"] == [1] * 10
    assert r["stir"] is None and r["clock"] == 0
    assert r["consts"] == [10, 16, 1 / 120, 0.05, 0.4]


def test_strands_move_and_repeat_for_a_seed(js):
    """AC 3: the points change over 1 s of sim time, and the same seed gives the same points."""
    r = run(js, r"""
        const a = make(); const start = pose(a); run(a, 1);
        const b = make(); run(b, 1);
        const c = make({ seed: 12346 }); run(c, 1);
        return { start, a: pose(a), b: pose(b), c: pose(c), clock: a.clock };
    """)
    assert r["a"] != r["start"]
    assert r["a"] == r["b"]
    assert r["c"] != r["a"]  # control: the seed really feeds the sim
    assert abs(r["clock"] - 1) < 1e-9


def test_stir_moves_near_points_more_than_far_ones(js):
    """AC 4: a stir at strand 4's point 8 moves the points that started within STIR_RADIUS of it more than the rest."""
    r = run(js, r"""
        const control = make(); const stirred = make();
        const at = [...stirred.strands[4].points[8]];
        const start = pose(stirred);
        stirred.setStir(at);
        run(stirred, 0.5); run(control, 0.5);
        const a = pose(stirred); const b = pose(control);
        const near = []; const far = [];
        start.forEach((s, i) => s.forEach((p, j) => (dist(p, at) < F.STIR_RADIUS ? near : far).push(dist(a[i][j], b[i][j]))));
        const mean = (xs) => xs.reduce((t, x) => t + x, 0) / xs.length;
        return { near: near.length, far: far.length, nearMean: mean(near), farMean: mean(far) };
    """)
    assert r["near"] >= 10 and r["far"] >= 10, r
    assert r["nearMean"] > r["farMean"], r
    assert r["nearMean"] > 1e-3, r  # the stir really moved something


def test_a_stir_across_one_strand_beats_the_breeze(js):
    """U1 (the page AC's bet): with the breeze on, a back-and-forth stir across strand 4 moves it more over 1 s than
    the far strand 9 moves on its own."""
    r = run(js, r"""
        const f = make(); run(f, 0.5);
        const at = f.strands[4].points[8];
        const centre = [...at];
        const sums = new Array(10).fill(0);
        let prev = pose(f);
        run(f, 1, (i) => {
          f.setStir([centre[0] + 0.15 * Math.sin(2 * Math.PI * 5 * i / 60), centre[1], centre[2]]);
          const now = pose(f); moved(now, prev).forEach((m, k) => { sums[k] += m; }); prev = now;
        });
        return sums;
    """)
    assert r[4] > r[9] and r[9] > 0, r


@pytest.mark.parametrize("bad", ["NaN", "'0.016'", "true", "[0.016]", "1n", "-1", "null", "undefined", "0"])
def test_advance_ignores_a_bad_dt_and_still_steps_after(js, bad):
    """A dt that is not a positive number steps nothing, and leaves the sim able to step: a NaN accumulator would
    freeze it for good, and Math.min/max would coerce a string, a boolean or a one-element array."""
    r = run(js, f"""
        const f = make(); f.advance(1 / 60); const c0 = f.clock;
        let error = null;
        try {{ f.advance({bad}); }} catch (e) {{ error = String(e); }}
        const c1 = f.clock;
        f.advance(1 / 60);
        return {{ error, c0, c1, c2: f.clock }};
    """)
    assert r["error"] is None, r
    assert r["c1"] == r["c0"], r
    assert r["c2"] > r["c1"], r


def test_advance_clamps_dt_and_steps_fixed(js):
    r = run(js, r"""
        const big = make(); big.advance(1.0);
        const inf = make(); inf.advance(Infinity);
        const fine = make(); for (let i = 0; i < 120; i += 1) fine.advance(1 / 120);
        return { big: big.clock, inf: inf.clock, fine: fine.clock };
    """)
    step = 1 / 120
    assert 0 < r["big"] <= 0.05 + step and abs(r["big"] - 0.05) <= step, r
    assert abs(r["inf"] - r["big"]) < 1e-12, r
    assert abs(r["fine"] - 1) < 1e-9, r


def test_rest_holds_the_pose_and_ignores_stir(js):
    """?pose=rest: the clock runs, nothing integrates, and the stir is ignored."""
    r = run(js, r"""
        const f = make({ rest: true }); const start = pose(f);
        f.setStir(f.strands[4].points[8]);
        run(f, 1);
        const moving = make(); run(moving, 1);
        return { same: JSON.stringify(pose(f)) === JSON.stringify(start), stir: f.stir, clock: f.clock,
                 restStart: JSON.stringify(start) === JSON.stringify(pose(make())) , controlMoved: JSON.stringify(pose(moving)) !== JSON.stringify(start) };
    """)
    assert r["same"] is True and r["stir"] is None and r["clock"] > 0.9, r
    assert r["restStart"] is True  # the rest pose is the seeded start pose
    assert r["controlMoved"] is True, r  # control: without rest the same second moves the points


def test_pins_hold_under_stir(js):
    r = run(js, r"""
        const f = make();
        run(f, 1, (i) => f.setStir([0.08 + 0.16 * (i % 10), -0.1, 0.014]));
        return f.strands.map((s, k) => dist(s.points[0], pins[k]));
    """)
    assert max(r) == 0, r


def test_points_stay_in_the_strand_plane_and_keep_their_arrays(js):
    """Each point keeps its pin's z, so the pointer cast onto that plane is exact; the arrays are mutated in place."""
    r = run(js, r"""
        const f = make();
        const arrays = f.strands.map((s) => s.points);
        const first = f.strands[3].points[5];
        run(f, 1, () => f.setStir([0.56, -0.3, 0.014]));
        return { z: [...new Set(f.strands.flatMap((s) => s.points.map((p) => p[2])))],
                 same: f.strands.every((s, i) => s.points === arrays[i]) && f.strands[3].points[5] === first };
    """)
    assert r["z"] == [0.014] and r["same"] is True, r


def test_set_stir_copies_and_clears(js):
    """fray.stir is an [x, y, z] copy or null: it never aliases the caller's object, and a reader's edit never reaches
    the sim."""
    r = run(js, r"""
        const f = make();
        const p = [0.5, -0.2, 0.014];
        f.setStir(p);
        p[0] = 9;
        const read = f.stir; read[1] = 9;
        const after = f.stir;
        f.setStir(null);
        return { after, aliased: read === p, cleared: f.stir };
    """)
    assert r["after"] == [0.5, -0.2, 0.014] and r["aliased"] is False and r["cleared"] is None, r


@pytest.mark.parametrize("seed", ["'help-fray'", "-1", "1.5", "2 ** 32", "NaN", "undefined"])
def test_create_fray_wants_a_uint32_seed(js, seed):
    """A string seed would collapse to stream 0 through mulberry32's `>>> 0`, silently; it throws instead."""
    r = run(js, f"""
        try {{ F.createFray({{ pins, length: 0.6, seed: {seed} }}); return null; }}
        catch (e) {{ return [e.name, e.message]; }}
    """)
    assert r == ["TypeError", "createFray: seed must be a uint32"]


def test_pins_are_copied(js):
    r = run(js, r"""
        const mine = pins.map((p) => [...p]);
        const f = F.createFray({ pins: mine, length: 0.6, seed: 7 });
        mine[0][0] = 9;
        return f.strands[0].points[0][0];
    """)
    assert r == pytest.approx(0.08)


def test_fray_js_has_no_imports_but_random():
    code = re.sub(r"(?m)^\s*//[^\n]*", " ", FRAY.read_text(encoding="utf-8"))
    specifiers = re.findall(r"""(?:\bfrom\s*|\bimport\s*\(?\s*)['"]([^'"]+)['"]""", code)
    assert specifiers == ["./random.js"]


# --- The header: the model, the clock rule and the hook #19 builds on. ---

HEADER_PHRASES = ("10 strands", "16 points", "1/120", "mulberry32", "advance(dt)", "requestAnimationFrame", "Date",
                  "frayAmount", "hanging", "stir", "?pose=rest", "stage.__weaveHelp", "no Three")


def header_claims(text):
    prose = header_prose(text)
    return all(phrase in prose for phrase in HEADER_PHRASES)


def test_fray_js_header_states_the_model():
    """AC 16. Planted controls: the header trimmed to one line, and the header without its 16-points claim."""
    text = FRAY.read_text(encoding="utf-8")
    assert header_claims(text) is True
    rest = "\n".join(text.splitlines()[len(header_lines(text)):])
    assert header_claims("// Threads.\n" + rest) is False
    lines = text.splitlines()
    claim = [i for i, line in enumerate(header_lines(text)) if "16 points" in line]
    assert len(claim) == 1, claim
    assert header_claims("\n".join(lines[:claim[0]] + lines[claim[0] + 1:])) is False


@pytest.mark.parametrize("bad", ["NaN", "Infinity", "-Infinity", "'1'", "undefined", "null", "''", "false", "[]"])
def test_a_bad_hanging_never_breaks_a_strand(js, bad):
    """hanging is #19's to write: a value that is not a finite number must not poison the strand's points for good."""
    r = run(js, f"""
        const f = make();
        const tip = () => {{ const p = f.strands[3].points; return Math.hypot(p[15][0] - p[0][0], p[15][1] - p[0][1]); }};
        f.strands[3].hanging = {bad}; run(f, 1);
        const held = tip();
        f.strands[3].hanging = 1; run(f, 1);
        return {{ finite: f.strands.flatMap((s) => s.points.flat()).every(Number.isFinite), held }};
    """)
    # Not a number counts as 1: the strand keeps its full length (0.6), never collapsing to its pin.
    assert r["finite"] is True and r["held"] > 0.4, r


@pytest.mark.parametrize("bad", ["5", "'abc'", "{}", "[1, 2]", "[NaN, 0, 0]", "[0, Infinity, 0]", "[null, null, null]",
                                 "['', 0, 0]", "['0.5', 0, 0]"])
def test_set_stir_ignores_a_malformed_point(js, bad):
    """A point that is not three finite numbers clears the stir, so fray.stir never reads non-null and meaningless."""
    r = run(js, f"const f = make(); f.setStir([0.5, -0.2, 0.014]); f.setStir({bad}); return f.stir;")
    assert r is None
