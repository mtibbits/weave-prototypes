"""#16's sew-in: the pure schedule (motion.js), the scene's sew-in calls (scene.js), and the page's sequence and skips
(main.js, whatsnew.js). Expected values are literals, never imported (PUFF and GLOW's peak legs excepted, as noted)."""
import pytest

from helpers import SEAMS_JS
from test_scene import BUILD_JS

# --- The pure schedule (motion.js). ---

SCHEDULE_JS = "const M = await import('/public/js/motion.js');"

class TestSchedule:
    def test_two_blocks_keep_the_nominal_steps(self, js):
        r = js(SCHEDULE_JS + "return M.sewSchedule(2);")
        assert r["scale"] == 1
        assert abs(r["total"] - 3.15) <= 1e-9
        assert len(r["blocks"]) == 2
        want = {"start": 0, "pins": [0, 0.3], "square": [0.3, 0.7], "puff": [0.7, 0.95], "needle": [0.95, 2.15],
                "glow": [2.15, 2.55]}
        for k, block in enumerate(r["blocks"]):
            shift = 0.6 * k
            assert abs(block["start"] - (want["start"] + shift)) <= 1e-9, (k, block)
            for name in ("pins", "square", "puff", "needle", "glow"):
                assert len(block[name]) == 2, (k, name, block)
                for got, nominal in zip(block[name], want[name]):
                    assert abs(got - (nominal + shift)) <= 1e-9, (k, name, block)

    @pytest.mark.parametrize("n", range(1, 13))
    def test_schedule_ends_within_5_s(self, js, n):
        r = js(SCHEDULE_JS + f"return M.sewSchedule({n});")
        steps = {"pins": 0.3, "square": 0.4, "puff": 0.25, "needle": 1.2, "glow": 0.4}
        raw = 0.6 * (n - 1) + 2.55
        assert r["total"] <= 5 + 1e-9, r
        if n <= 5:
            assert r["scale"] == 1
            assert abs(r["total"] - raw) <= 1e-9
        else:
            assert abs(r["total"] - 5) <= 1e-9
            assert abs(r["scale"] - 5 / raw) <= 1e-12
        scale = r["scale"]
        assert len(r["blocks"]) == n
        for k, block in enumerate(r["blocks"]):
            assert abs(block["start"] - 0.6 * scale * k) <= 1e-9, (k, block)
            at = block["start"]
            for name in ("pins", "square", "puff", "needle", "glow"):
                t0, t1 = block[name]
                assert abs(t0 - at) <= 1e-9 and abs((t1 - t0) - steps[name] * scale) <= 1e-9, (k, name, block)
                at = t1
        assert abs(r["blocks"][-1]["glow"][1] - r["total"]) <= 1e-9
        # At most two needle windows overlap at any time: the third's start is past the first's end.
        needles = [b["needle"] for b in r["blocks"]]
        for k in range(len(needles) - 2):
            assert needles[k + 2][0] >= needles[k][1] - 1e-9, (k, needles)

    def test_no_blocks_is_an_empty_schedule(self, js):
        assert js(SCHEDULE_JS + "return M.sewSchedule(0);") == {"scale": 1, "total": 0, "blocks": []}

    @pytest.mark.parametrize("count", ["-1", "1.5", "'2'", "true", "NaN", "null", "[2]", "2n"])
    def test_bad_counts_throw(self, js, count):
        r = js(SCHEDULE_JS + f"""
            try {{ M.sewSchedule({count}); return null; }}
            catch (err) {{ return [err.constructor.name, err.message]; }}
        """)
        assert r == ["RangeError", "WEAVE: sewSchedule needs a whole number of blocks."]

    def test_schedule_is_pure(self, js):
        """Behavioural (seed Issue-565): every clock and timer throws around the calls, as test_director_reads_no_clock
        does; the same count gives the same schedule."""
        r = js(SCHEDULE_JS + r"""
            const names = [[Date, 'now'], [performance, 'now'], [window, 'setTimeout'], [window, 'requestAnimationFrame']];
            const saved = names.map(([o, k]) => o[k]);
            const SavedDate = window.Date;
            const boom = () => { throw new Error('sewSchedule read a clock'); };
            const out = [];
            try {
              names.forEach(([o, k]) => { o[k] = boom; });
              window.Date = function () { throw new Error('sewSchedule built a Date'); };
              for (let n = 1; n <= 12; n += 1) out.push(JSON.stringify(M.sewSchedule(n)));
              out.push(JSON.stringify(M.sewSchedule(7)));
            } finally {
              window.Date = SavedDate;
              names.forEach(([o, k], i) => { o[k] = saved[i]; });
            }
            return out;
        """)
        assert len(r) == 13
        assert r[6] == r[12]

# --- The scene's sew-in calls (scene.js), on blank.html. ---

# test_scene's build(slots, options) and slotsOf(), plus: SEW_BUILD() is the start-planned build (Travel and Desk
# Allocation, slots 5 and 10, built planned); PERIMETER is the 161 vertex indices of a block's edge, from the top left,
# clockwise from +z; needles(q) is the quilt group's needle children; seams() is helpers' SEAMS_JS.
SCENE_SEW_JS = BUILD_JS + SEAMS_JS + r"""
    const SEW_BUILD = () => build(slotsOf(), { startPlanned: ['travel', 'desks'] });
    const PERIMETER = [];
    for (let j = 0; j <= 40; j += 1) PERIMETER.push(j);
    for (let r = 1; r <= 40; r += 1) PERIMETER.push(41 * r + 40);
    for (let c = 1; c <= 40; c += 1) PERIMETER.push(1680 - c);
    for (let r = 39; r >= 0; r -= 1) PERIMETER.push(41 * r);
    const needles = (q) => q.group.children.filter((c) => c.userData.part === 'needle');
    const travelStitches = (q) => q.snapshot().stitches.filter((s) => s.id === 'travel');
"""

def scene_sew(paint_js, body):
    return paint_js(SCENE_SEW_JS + body)

class TestScene:
    def test_start_planned_builds_a_live_block_planned(self, paint_js):
        r = scene_sew(paint_js, r"""
            const plain = JSON.stringify(build().snapshot());
            const q = SEW_BUILD();
            const snap = q.snapshot();
            const b = q.blocks[5];
            const out = { userData: { ...b.userData }, tilt: b.rotation.z, baseTilt: q.blockBase(5).tilt, z: b.position.z,
                          pins: snap.pins.length, stitches: snap.stitches.length,
                          needles: needles(q).map((n) => [n.userData.id, n.visible]) };
            q.restorePins('travel', { animate: false });
            out.travelPins = q.snapshot().pins.filter((p) => p.id === 'travel').length;
            out.promotions = JSON.stringify(build(slotsOf(), { startPlanned: ['promotions'] }).snapshot()) === plain;
            out.notArray = JSON.stringify(build(slotsOf(), { startPlanned: 'travel' }).snapshot()) === plain;
            out.plainNeedles = needles(build()).length;
            return out;
        """)
        assert r["userData"] == {"slot": 5, "id": "travel", "status": "live", "face": "planned"}
        assert r["tilt"] != 0 and abs(r["tilt"]) <= 2.5 * 3.141592653589793 / 180, r["tilt"]
        assert r["baseTilt"] == r["tilt"]
        assert abs(r["z"] - 0.01) <= 1e-9
        assert r["pins"] == 0 and r["stitches"] == 0
        assert r["travelPins"] in (3, 4)
        assert sorted(r["needles"]) == [["desks", False], ["travel", False]]
        assert r["promotions"] is True and r["notArray"] is True
        assert r["plainNeedles"] == 0

    def test_set_tilt_refolds_like_a_fresh_build(self, paint_js):
        r = scene_sew(paint_js, r"""
            const plain = build();
            const q = SEW_BUILD();
            const before = seams(q.snapshot(), L);
            const indices0 = q.sashing.geometry.index.count;
            q.setTilt('travel', 0);
            const base = q.blockBase(5).positions;
            const want = plain.blockBase(5).positions;
            const diff = Math.max(...base.map((v, k) => Math.abs(v - want[k])));
            const tilt = q.blockBase(5).tilt;
            const rotZ = q.blocks[5].rotation.z;
            q.setFace('travel', 'sewn');
            q.reseam();
            const control = seams(q.snapshot(), L);
            const [cx, cy] = L.slotCentre(5);
            q.setBlockPose(5, { position: [cx, cy, 0], rotY: 0, rotZ: 0, morph: 0 });
            const after = seams(q.snapshot(), L);
            return { before, diff, tilt, rotZ, control, after, dropped: indices0 - q.sashing.geometry.index.count,
                     seeded: plain.blockBase(5).tilt };
        """)
        assert [r["before"]["checked"], r["before"]["missing"]] == [960, 0]
        assert r["diff"] <= 1e-6 and r["tilt"] == 0
        assert r["rotZ"] != 0  # setTilt never touches rotation.z: the pose is setBlockPose's
        assert r["control"]["checked"] == 1120 and r["control"]["missing"] > 0  # U2's planted control
        assert [r["after"]["checked"], r["after"]["missing"]] == [1120, 0]
        assert r["dropped"] == 9600

    def test_curve_points_and_u(self, paint_js):
        r = scene_sew(paint_js, r"""
            const q = SEW_BUILD();
            q.setTilt('travel', 0);
            const c = q.sewCurve('travel');
            const flat = q.blocks[5].geometry.morphAttributes.position[0];
            const [cx, cy] = L.slotCentre(5);
            let points = 0;
            PERIMETER.forEach((j, k) => {
              const x = cx + flat.getX(j); const y = cy + flat.getY(j);
              const want = [x, y, L.foldZ(x, y) + 0.01];
              points = Math.max(points, ...want.map((w, d) => Math.abs(w - c.at[k][d])));
            });
            const curve = new S.PerimeterCurve(c.at.map((p) => new THREE.Vector3(...p)));
            const sameU = curve.vertexU.every((u, k) => u === c.vertexU[k]);
            let mid = 0; let chord = 0;
            const tangents = {};
            for (const k of [0, 10, 39, 40, 50, 79, 80, 100, 120, 159]) {
              const u = (c.vertexU[k] + c.vertexU[k + 1]) / 2;
              const target = new THREE.Vector3();
              const p = curve.getPointAt(u, target);
              const a = new THREE.Vector3(...c.at[k]); const b = new THREE.Vector3(...c.at[k + 1]);
              mid = Math.max(mid, p.distanceTo(a.clone().lerp(b, 0.5)), p === target ? 0 : 1);
              const t = curve.getTangentAt(u, new THREE.Vector3());
              chord = Math.max(chord, t.distanceTo(b.clone().sub(a).normalize()));
              tangents[k] = t.toArray();
            }
            const end = curve.getTangentAt(1, new THREE.Vector3()).toArray();
            const last = new THREE.Vector3(...c.at[160]).sub(new THREE.Vector3(...c.at[159])).normalize().toArray();
            return { count: c.at.length, closed: c.at[0].every((v, d) => v === c.at[160][d]), u0: c.vertexU[0],
                     u1: c.vertexU[160], rising: c.vertexU.every((u, k) => k === 0 || u > c.vertexU[k - 1]),
                     points, sameU, mid, chord, tangents, end, last, unknown: q.sewCurve('nope'), filler: q.sewCurve(null) };
        """)
        assert r["count"] == 161 and r["closed"] is True
        assert r["u0"] == 0 and r["u1"] == 1 and r["rising"] is True
        assert r["points"] <= 1e-9, r["points"]
        assert r["sameU"] is True
        assert r["mid"] <= 1e-9 and r["chord"] <= 1e-9, r
        top, right = r["tangents"]["10"], r["tangents"]["50"]
        assert abs(top[1]) <= 1e-9 and top[0] > 0, top
        assert abs(right[0]) <= 1e-9 and right[1] < 0, right
        assert max(abs(a - b) for a, b in zip(r["end"], r["last"])) <= 1e-9
        assert r["unknown"] is None and r["filler"] is None

    def test_stitch_u_orders_the_dashes(self, paint_js):
        r = scene_sew(paint_js, r"""
            const q = SEW_BUILD();
            q.setTilt('travel', 0);
            const [cx, cy] = L.slotCentre(5);
            q.setBlockPose(5, { position: [cx, cy, 0], rotY: 0, rotZ: 0, morph: 0 });
            const c = q.sewCurve('travel');
            const curve = new S.PerimeterCurve(c.at.map((p) => new THREE.Vector3(...p)));
            q.revealStitches('travel', { animate: false });
            const dashes = travelStitches(q);
            const gaps = c.stitchU.map((u, k) => {
              const p = curve.getPointAt(u, new THREE.Vector3());
              return Math.hypot(p.x - dashes[k].position[0], p.y - dashes[k].position[1]);
            });
            return { stitchU: c.stitchU, dashes: dashes.length, gap: Math.max(...gaps) };
        """)
        u = r["stitchU"]
        assert len(u) == 48 and r["dashes"] == 48
        assert all(0 < x < 1 for x in u) and all(b > a for a, b in zip(u, u[1:])), u
        assert r["gap"] <= 1e-4, r["gap"]

    @pytest.mark.parametrize("u, count", [("0", 0), ("c.stitchU[0] - 1e-9", 0), ("c.stitchU[0]", 1),
                                          ("c.stitchU[23]", 24), ("0.5", None), ("1", 48)],
                             ids=["0", "s0-eps", "s0", "s23", "0.5", "1"])
    def test_reveal_to_u_shows_exactly_those_at_or_before(self, paint_js, u, count):
        r = scene_sew(paint_js, f"""
            const q = build();
            const c = q.sewCurve('travel');
            const u = {u};
            q.revealStitchesTo('travel', u);
            const drawn = travelStitches(q).map((s) => s.position);
            const rest = build();
            rest.revealStitches('travel', {{ animate: false }});
            const full = travelStitches(rest).map((s) => s.position);
            const want = full.filter((_, k) => c.stitchU[k] <= u);
            const unmatched = drawn.filter((p) => !want.some((w) => Math.max(...w.map((v, d) => Math.abs(v - p[d]))) <= 1e-6));
            q.revealStitches('travel', {{ animate: false }});
            return {{ drawn: drawn.length, want: want.length, expected: c.stitchU.filter((s) => s <= u).length,
                      unmatched: unmatched.length, after: travelStitches(q).length }};
        """)
        assert r["drawn"] == r["want"] == r["expected"], r
        assert r["unmatched"] == 0
        assert r["after"] == 48
        if count is not None:
            assert r["expected"] == count
        else:
            assert 0 < r["expected"] < 48

    def test_puff_and_glow_rest_exactly(self, paint_js):
        """A recorded exception to "literals, never imported": PUFF and GLOW are tuned at the demo, so the peak legs
        read the exported constants; the rest legs use literals."""
        r = scene_sew(paint_js, r"""
            const q = build();
            const b = q.blocks[5];
            const pose0 = [b.position.toArray(), b.scale.toArray()];
            q.setPuff('travel', 1);
            const peak = [b.position.toArray(), b.scale.toArray()];
            q.setPuff('travel', 0);
            const rest = [b.position.toArray(), b.scale.toArray()];
            const programs = [q.renderer.info.programs.length];
            q.setGlow('travel', 1);
            q.render();
            programs.push(q.renderer.info.programs.length);
            const glow = b.material.emissive.toArray();
            const look = q.sewLook('travel').emissive;
            const want = new THREE.Color(S.GLOW.color).multiplyScalar(S.GLOW.intensity).toArray();
            q.setGlow('travel', 0);
            q.render();
            programs.push(q.renderer.info.programs.length);
            return { pose0, peak, rest, glow, look, want, off: b.material.emissive.toArray(),
                     lookOff: q.sewLook('travel').emissive, programs, PUFF: S.PUFF, puffLook: q.sewLook('travel').puff };
        """)
        (p0, s0), (p1, s1) = r["pose0"], r["peak"]
        assert all(abs(s - (1 + r["PUFF"]["scale"])) <= 1e-12 for s in s1), s1
        assert abs(p1[2] - (p0[2] + r["PUFF"]["lift"])) <= 1e-12 and p1[:2] == p0[:2]
        assert r["rest"] == r["pose0"] and s0 == [1, 1, 1]
        assert max(abs(a - b) for a, b in zip(r["glow"], r["want"])) <= 1e-6
        assert max(abs(a - b) for a, b in zip(r["look"], r["want"])) <= 1e-6
        assert r["off"] == [0, 0, 0] and r["lookOff"] == [0, 0, 0]
        assert r["puffLook"] == 0
        assert len(set(r["programs"])) == 1, r["programs"]

    def test_needle_rides_the_curve(self, paint_js):
        r = scene_sew(paint_js, r"""
            const q = SEW_BUILD();
            const before = q.sewLook('travel').needle;
            q.startNeedle('travel');
            q.poseNeedle('travel', 0.3);
            q.poseNeedles();
            const n = needles(q).find((x) => x.userData.id === 'travel');
            const curve = new S.PerimeterCurve(q.sewCurve('travel').at.map((p) => new THREE.Vector3(...p)));
            const want = curve.getPointAt(0.3, new THREE.Vector3());
            const out = { before, visible: n.visible, parent: n.parent === q.group, gap: n.position.distanceTo(want),
                          look: q.sewLook('travel').needle };
            const owned = new Set();
            n.traverse((o) => { if (o.isMesh) { owned.add(o.geometry); owned.add(o.material); } });
            const disposed = new Set();
            owned.forEach((x) => { const own = x.dispose.bind(x); x.dispose = () => { disposed.add(x); own(); }; });
            q.endNeedle('travel');
            out.left = needles(q).map((x) => x.userData.id);
            out.owned = owned.size;
            out.disposed = [...owned].every((x) => disposed.has(x));
            out.lookAfter = q.sewLook('travel').needle;
            q.endNeedle('travel');
            q.poseNeedle('travel', 0.5);
            q.startNeedle('nope'); q.poseNeedle('nope', 0.5); q.endNeedle('nope');
            q.poseNeedles();
            out.again = needles(q).map((x) => x.userData.id);
            return out;
        """)
        assert r["before"] is False
        assert r["visible"] is True and r["parent"] is True and r["look"] is True
        assert r["gap"] <= 1e-6, r["gap"]
        assert r["left"] == ["desks"] and r["again"] == ["desks"]
        assert r["owned"] >= 3 and r["disposed"] is True
        assert r["lookAfter"] is False

