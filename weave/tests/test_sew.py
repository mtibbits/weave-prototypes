"""#16's sew-in: the pure schedule (motion.js), the scene's sew-in calls (scene.js), and the page's sequence and skips
(main.js, whatsnew.js). Expected values are literals, never imported (PUFF and GLOW's peak legs excepted, as noted)."""
import pytest
from playwright.sync_api import Error

import helpers
import test_hover
import test_whatsnew
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


# --- The page: the sequence (AC1-AC4, AC6-AC8) and the skips (AC5), in the release's news window. ---

IN_WINDOW_Q = "?nowatchdog&now=2026-10-10"
SEW_IDS = ["travel", "desks"]
SEW_SLOTS = [5, 10]
PLANNED_IDS = ["promotions", "feedback", "oversight", "access"]

# An init script with its own parse-time weave:mode listener on [data-hero] (attached as MODE_LOG's is; it never uses
# window.__onMode, which test_whatsnew's ENTRY_LOG assigns). On the `sewing` entry it records window.__atSewing =
# { faces (by slot), pins ({id: count}), sim, point } synchronously, point being Travel's corner mean from that
# snapshot, projected; on the next frame it calls window.__onSewing(el) if a test defined it.
SEW_HOOK = r"""
    (() => {
      const attach = (el) => {
        if (el.__sewHook) return;
        el.__sewHook = true;
        el.addEventListener('weave:mode', (event) => {
          if (event.detail.mode !== 'sewing') return;
          const snap = el.__weave.snapshot();
          const pins = {};
          for (const p of snap.pins) pins[p.id] = (pins[p.id] ?? 0) + 1;
          const b = snap.blocks.find((x) => x.id === 'travel');
          const mean = [0, 1, 2].map((k) => [0, 40, 1640, 1680].reduce((s, j) => s + b.positions[3 * j + k], 0) / 4);
          window.__atSewing = { faces: snap.blocks.map((x) => x.face), pins,
                                sim: localStorage.getItem('weave.lastSeenRelease.sim'), point: el.__weave.project(mean) };
          requestAnimationFrame(() => { if (window.__onSewing) window.__onSewing(el); });
        });
      };
      new MutationObserver(() => {
        const el = document.querySelector('[data-hero]');
        if (el) attach(el);
      }).observe(document, { childList: true, subtree: true });
    })();
"""

# The sew-in is over: __weave.mode is quilt and the quilt was entered from sewing. Synchronous (Issue-9).
SEW_DONE = ("() => document.querySelector('[data-hero]')?.__weave?.mode === 'quilt'"
            " && (window.__modes || []).some((m) => m.mode === 'quilt' && m.from === 'sewing')")

# One evaluate (D40: the world -> quilt map is read in the same call as the snapshot, so the sway cannot move between
# reads): every block's corner mean in quilt space against its slot, and each new block's 160 edge vertices against
# its sew curve, with and without the needle's lift subtracted.
QUILT_FRAME = r"""async (el) => {
    const THREE = await import('three');
    const L = await import('/public/js/layout.js');
    const [snap, matrix, travel, desks] = [el.__weave.snapshot(), el.__weave.groupMatrix(), el.__weave.sewCurve('travel'),
                                           el.__weave.sewCurve('desks')];
    const inverse = new THREE.Matrix4().fromArray(matrix).invert();
    const local = (p, j) => new THREE.Vector3(p[3 * j], p[3 * j + 1], p[3 * j + 2]).applyMatrix4(inverse);
    let centre = 0;
    for (const b of snap.blocks) {
      const mean = [0, 40, 1640, 1680].map((j) => local(b.positions, j)).reduce((s, v) => s.add(v), new THREE.Vector3())
        .multiplyScalar(0.25);
      const [cx, cy] = L.slotCentre(b.slot);
      centre = Math.max(centre, Math.abs(mean.x - cx), Math.abs(mean.y - cy));
    }
    const perimeter = [];
    for (let j = 0; j <= 40; j += 1) perimeter.push(j);
    for (let r = 1; r <= 40; r += 1) perimeter.push(41 * r + 40);
    for (let c = 1; c <= 40; c += 1) perimeter.push(1680 - c);
    for (let r = 39; r >= 1; r -= 1) perimeter.push(41 * r);
    let compared = 0; let lifted = 0; let unlifted = 0;
    for (const [id, curve] of [['travel', travel], ['desks', desks]]) {
      const b = snap.blocks.find((x) => x.id === id);
      perimeter.forEach((j, k) => {
        const v = local(b.positions, j);
        const at = curve.at[k];
        compared += 1;
        lifted = Math.max(lifted, Math.hypot(at[0] - v.x, at[1] - v.y, at[2] - 0.01 - v.z));
        unlifted = Math.max(unlifted, Math.hypot(at[0] - v.x, at[1] - v.y, at[2] - v.z));
      });
    }
    return { centre, compared, lifted, unlifted, blocks: snap.blocks.length,
             tilts: ['travel', 'desks'].map((id) => el.__weave.blockBase(id).tilt) };
}"""


def open_sew(make_page, base_url, query=IN_WINDOW_Q, on_sewing=None, before_goto=None, **kw):
    """open_live with MODE_LOG, RELEASE_LOG and SEW_HOOK, then `on_sewing` (a JS body run with `el` on the frame after
    the sewing entry) and `before_goto`; returns (page, errors)."""
    def setup(page):
        helpers.log_modes(page)
        page.add_init_script(test_whatsnew.RELEASE_LOG)
        page.add_init_script(SEW_HOOK)
        if on_sewing is not None:
            page.add_init_script(f"window.__onSewing = (el) => {{ {on_sewing} }};")
        if before_goto is not None:
            before_goto(page)

    return helpers.open_live(make_page, base_url, query=query, before_goto=setup, **kw)


def wait_sew_done(page, timeout=15000):
    page.wait_for_function(SEW_DONE, timeout=timeout)


def faces(page):
    return [s["face"] for s in helpers.weave(page, ".slots")]


def decor_of(page, ids=SEW_IDS):
    """{id: [pins, stitches]} from one snapshot."""
    return page.eval_on_selector("[data-hero]", """(el, ids) => { const s = el.__weave.snapshot();
        return Object.fromEntries(ids.map((id) => [id, [s.pins.filter((p) => p.id === id).length,
                                                        s.stitches.filter((p) => p.id === id).length]])); }""", ids)


def looks(page, ids=SEW_IDS):
    return page.eval_on_selector("[data-hero]", "(el, ids) => ids.map((id) => el.__weave.sewLook(id))", ids)


def assert_sewn(page):
    """Both new blocks sewn: the sewn face, no pins, 48 stitches, no puff, glow or needle, untilted."""
    got = faces(page)
    assert [got[s] for s in SEW_SLOTS] == ["sewn", "sewn"], got
    assert decor_of(page) == {"travel": [0, 48], "desks": [0, 48]}
    for look in looks(page):
        assert look == {"puff": 0, "emissive": [0, 0, 0], "needle": False, "tilt": 0}, look


class TestSequence:
    def test_full_sequence(self, make_page, base_url):
        page, errors = open_sew(make_page, base_url)
        wait_sew_done(page)
        page.wait_for_selector(test_whatsnew.CARD)
        assert test_whatsnew.states(page) == ["pending", "sewing", "card"]
        assert helpers.modes(page)[:3] == [("intro", None), ("sewing", "intro"), ("quilt", "sewing")]
        at = page.evaluate("window.__atSewing")
        assert [at["faces"][s] for s in SEW_SLOTS] == ["planned", "planned"]
        assert all(at["pins"].get(i) in (3, 4) for i in SEW_IDS), at["pins"]
        assert_sewn(page)
        seams = page.eval_on_selector("[data-hero]", helpers.SEAMS)
        assert [seams["checked"], seams["missing"]] == [1280, 0]
        assert test_whatsnew.card(page)[1]["names"] == ["Travel", "Desk Allocation"]
        assert test_whatsnew.seen(page) == ["1.1", None]
        assert errors == []

    @pytest.mark.parametrize("path", ["natural", "pause-intro", "pause-sewing"])
    def test_each_sew_step_runs_once(self, make_page, base_url, path):
        pause = "document.querySelector('[data-pause]').click();"
        kw = {"natural": {}, "pause-intro": {"before_goto": test_whatsnew.entry_log(pause)},
              "pause-sewing": {"on_sewing": pause}}[path]
        page, errors = open_sew(make_page, base_url, **kw)
        page.wait_for_selector(test_whatsnew.CARD)
        calls = helpers.weave(page, ".sewCalls")
        names = ["popPins", "tilt0", "puff0", "face", "needleStart", "needleEnd", "reveal", "glow0"]
        if path != "natural":
            names = [n for n in names if not n.startswith("needle")]
        want = {f"{n} {i}": 1 for n in names for i in SEW_IDS}
        want["reseam"] = 2 if path == "natural" else 1
        assert calls == want
        assert errors == []

    def test_no_hover_during_sewing(self, make_page, base_url):
        page, errors = open_sew(make_page, base_url)
        helpers.wait_for_mode(page, "sewing")
        page.mouse.move(*page.evaluate("window.__atSewing.point"))
        r = page.evaluate("""async (ms) => {
            const el = document.querySelector('[data-hero]');
            const tip = document.querySelector('[data-tooltip]');
            const end = performance.now() + ms;
            let frames = 0; let shown = 0; let lifted = 0;
            while (performance.now() < end && el.__weave.mode === 'sewing') {
              frames += 1;
              if (tip && tip.hidden === false) shown += 1;
              if (el.__weave.hover.amount !== 0) lifted += 1;
              await new Promise((r) => requestAnimationFrame(r));
            }
            return { frames, shown, lifted };
        }""", helpers.HOVER_WINDOW_MS)
        assert r["frames"] > 5 and r["shown"] == 0 and r["lifted"] == 0, r
        wait_sew_done(page)
        test_hover.wait_tip_shown(page)
        test_hover.wait_hover(page, "h.id === 'travel'", timeout=helpers.HOVER_WINDOW_MS)
        assert errors == []

    def test_sew_in_within_5_s(self, make_page, base_url):
        page, errors = open_sew(make_page, base_url, clock=None)
        wait_sew_done(page)
        log = page.evaluate("window.__modes")
        start = next(e["t"] for e in log if (e["mode"], e["from"]) == ("sewing", "intro"))
        end = next(e["t"] for e in log if (e["mode"], e["from"]) == ("quilt", "sewing"))
        print(f"sew-in wall time: {end - start:.0f} ms")
        assert end - start <= 5000
        assert errors == []

    def test_curve_follows_the_mesh(self, make_page, base_url):
        page, errors = open_sew(make_page, base_url)
        wait_sew_done(page)
        page.mouse.move(2, 2)
        r = page.eval_on_selector("[data-hero]", QUILT_FRAME)
        assert r["blocks"] == 12 and r["centre"] <= 1e-6, r
        assert r["tilts"] == [0, 0]
        assert r["compared"] == 320
        assert r["lifted"] <= 1e-4, r
        assert r["unlifted"] >= 0.009, r  # planted control: without the lift subtracted
        assert errors == []

    def test_needles_join_the_group_and_leave(self, make_page, base_url):
        sampler = ("window.__needle = []; const look = () => { window.__needle.push(el.__weave.sewLook('travel').needle);"
                   " if (el.__weave.mode === 'sewing') requestAnimationFrame(look); }; look();")
        page, errors = open_sew(make_page, base_url, on_sewing=sampler)
        wait_sew_done(page)
        assert True in page.evaluate("window.__needle")
        assert [look["needle"] for look in looks(page)] == [False, False]
        assert errors == []

    def test_hidden_tab_waits(self, make_page, base_url):
        hide = ("Object.defineProperty(document, 'hidden', { configurable: true, get: () => true });"
                " Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => 'hidden' });"
                " document.dispatchEvent(new Event('visibilitychange')); window.__hidden = true;")
        page, errors = open_sew(make_page, base_url, on_sewing=hide)
        page.wait_for_function("() => window.__hidden === true")
        before = helpers.frames(page)
        for _ in range(6):
            page.wait_for_timeout(500)
            assert helpers.weave(page, ".mode") == "sewing"
            assert test_whatsnew.stage_data(page, "releaseState") == "sewing"
        assert helpers.frames(page) == before
        assert test_whatsnew.stored(page) == [None, None]
        page.evaluate("() => { delete document.hidden; delete document.visibilityState;"
                      " document.dispatchEvent(new Event('visibilitychange')); }")
        page.wait_for_function("() => document.querySelector('[data-hero]').dataset.releaseState === 'card'",
                               timeout=10000)
        assert test_whatsnew.seen(page)[0] == "1.1"
        assert errors == []

    def test_reload_during_sewing_replays(self, make_page, base_url):
        # open_sew installs on_sewing with add_init_script, so it reruns on every navigation: the reload is one-shot.
        once = ("const n = Number(sessionStorage.getItem('sew16.sewings') || 0) + 1;"
                " sessionStorage.setItem('sew16.sewings', String(n));"
                " if (!sessionStorage.getItem('sew16.reloaded')) { sessionStorage.setItem('sew16.reloaded', '1');"
                " location.reload(); }")
        page, errors = open_sew(make_page, base_url, on_sewing=once)
        # The pinned test clock empties the performance timeline, so the sessionStorage counter tells the loads apart.
        reloaded = ("() => sessionStorage.getItem('sew16.sewings') === '2'"
                    " && (window.__modes || []).some((m) => m.mode === 'quilt' && m.from === 'sewing')")
        for _ in range(200):
            try:
                if page.evaluate(reloaded):
                    break
            except Error:
                pass  # the reload replaced the document mid-evaluate
            page.wait_for_timeout(100)
        else:
            raise AssertionError("the reloaded page never finished its sew-in")
        assert ("sewing", "intro") in helpers.modes(page)
        assert page.evaluate("window.__atSewing.sim") is None
        page.wait_for_selector(test_whatsnew.CARD)
        page.wait_for_timeout(1000)
        assert page.evaluate("() => sessionStorage.getItem('sew16.sewings')") == "2"  # one reload, never a second
        assert [e for e in errors if "Execution context" not in e] == []

    def test_only_an_undrawn_panel_is_new(self, make_page, base_url):
        body = test_whatsnew.mutated("""for (const id of ['travel', 'desks']) {
  window.WEAVE_PANELS.panels.find((p) => p.id === id).since = '1.0';
}
window.WEAVE_PANELS.panels.push({ id: 'payroll', name: 'Payroll', status: 'live', since: '1.1', sample: null,
  blurb: 'Pay.' });""")
        page, errors = open_sew(make_page, base_url, panels_body=body)
        helpers.wait_for_quilt(page)
        page.wait_for_selector(test_whatsnew.CARD)
        assert test_whatsnew.states(page) == ["pending", "card"]
        got = helpers.modes(page)
        assert got[:2] == helpers.PLAIN_START and "sewing" not in [m for m, _ in got]
        assert test_whatsnew.card(page)[1]["names"] == ["Payroll"]
        assert page.evaluate("() => [...document.querySelectorAll('li.panel.is-new .panel-name')]"
                             ".map((e) => e.textContent)") == ["Payroll"]
        slots = helpers.weave(page, ".slots")
        assert sorted(s["id"] for s in slots if s["face"] == "planned") == sorted(PLANNED_IDS)
        assert errors == []

    def test_live_path_requests_needle(self, make_page, base_url):
        requested = []
        page, errors = open_sew(make_page, base_url,
                                before_goto=lambda p: p.on("request", lambda r: requested.append(r.url)))
        wait_sew_done(page)
        assert len([u for u in requested if u.endswith("/js/needle.js")]) == 1, requested
        assert errors == []


class TestSkips:
    def test_pause_during_intro_sews_at_once(self, make_page, base_url):
        page, errors = open_sew(make_page, base_url, before_goto=test_whatsnew.entry_log(
            "document.querySelector('[data-pause]').click();"))
        page.wait_for_selector(test_whatsnew.CARD)
        assert helpers.modes(page) == helpers.PLAIN_START
        assert_sewn(page)
        assert test_whatsnew.states(page) == ["pending", "card"]
        assert test_whatsnew.seen(page)[0] == "1.1"
        assert errors == []

    def test_pause_during_sewing_then_play_no_replay(self, make_page, base_url):
        page, errors = open_sew(make_page, base_url, on_sewing="document.querySelector('[data-pause]').click();")
        page.wait_for_selector(test_whatsnew.CARD)
        assert helpers.modes(page)[1:] == [("sewing", "intro"), ("quilt", "sewing")]
        assert_sewn(page)
        page.click("[data-pause]")
        page.wait_for_timeout(1000)
        assert helpers.modes(page)[1:] == [("sewing", "intro"), ("quilt", "sewing")]
        assert helpers.rising(page)
        assert_sewn(page)
        assert test_whatsnew.seen(page)[0] == "1.1"
        assert errors == []

    @pytest.mark.parametrize("path", ["reduced-motion", "no-webgl"])
    def test_still_paths_never_sew(self, make_page, base_url, browser_no_webgl, path):
        requested = []
        options = {} if path == "reduced-motion" else {"target_browser": browser_no_webgl,
                                                       "reduced_motion": "no-preference"}
        page, errors = test_whatsnew.open_still(make_page, base_url, "?now=2026-10-10",
                                                before_goto=lambda p: p.on("request", lambda r: requested.append(r.url)),
                                                **options)
        assert helpers.hero_result(page) == ["still", path]
        page.wait_for_load_state("networkidle")
        assert page.eval_on_selector("[data-hero]", "el => el.dataset.mode ?? null") is None
        assert test_whatsnew.stage_data(page, "releaseState") == "card"
        assert any(u.endswith("/public/js/main.js") for u in requested), requested
        assert not [u for u in requested if u.endswith("/js/needle.js") or "three.module" in u], requested
        assert test_whatsnew.seen(page)[0] == "1.1"
        assert errors == []

    @pytest.mark.parametrize("act", ["toggle-intro", "click-sewing"])
    def test_toggle_during_intro_and_click_during_sewing(self, make_page, base_url, act):
        toggle = "document.querySelector('[data-toggle]').click();" if act == "toggle-intro" else None
        page, errors = open_sew(make_page, base_url, before_goto=test_whatsnew.entry_log(toggle))
        if act == "click-sewing":
            helpers.wait_for_mode(page, "sewing")
            page.evaluate("() => document.addEventListener('pointerdown', () => { window.__pressMode ="
                          " document.querySelector('[data-hero]').__weave.mode; }, { capture: true, once: true })")
            page.mouse.click(*page.evaluate("window.__atSewing.point"))
            assert page.evaluate("window.__pressMode") == "sewing"
        helpers.wait_for_data_mode(page, "tiles")
        got = faces(page)
        assert [got[s] for s in SEW_SLOTS] == ["sewn", "sewn"]
        assert helpers.weave(page, ".blockBase('travel').tilt") == 0
        page.wait_for_selector(test_whatsnew.CARD)
        entries = [e[:2] for e in page.evaluate("window.__entries")]
        i = entries.index(["quilt", "card"])
        assert entries[i:i + 2] == [["quilt", "card"], ["unstitching", "card"]]
        modes = helpers.modes(page)
        if act == "toggle-intro":
            assert "sewing" not in [m for m, _ in modes]
        else:
            assert modes[1:4] == [("sewing", "intro"), ("quilt", "sewing"), ("unstitching", "quilt")]
        assert test_whatsnew.seen(page)[0] == "1.1"
        assert errors == []

    def test_context_loss_during_sewing(self, make_page, base_url):
        lose = "el.querySelector('canvas').getContext('webgl2').getExtension('WEBGL_lose_context').loseContext();"
        page, _ = open_sew(make_page, base_url, on_sewing=lose)
        helpers.wait_for_reason(page, "context-lost")
        page.wait_for_selector(test_whatsnew.CARD)
        # The loss lands one frame into a ~3 s sew-in, so the teardown mode is `sewing`.
        assert helpers.weave(page, ".mode") == "sewing"
        assert test_whatsnew.states(page) == ["pending", "sewing", "card"]
        assert test_whatsnew.seen(page)[0] == "1.1"

    def test_pose_rest_on_the_window_clock(self, make_page, base_url):
        page, errors = open_sew(make_page, base_url, query="?nowatchdog&pose=rest", clock="2026-10-10T09:00:00")
        page.wait_for_selector(test_whatsnew.CARD)
        assert helpers.modes(page) == [("quilt", None)]
        got = faces(page)
        assert [got[s] for s in SEW_SLOTS] == ["sewn", "sewn"]
        assert {i: v[0] for i, v in decor_of(page).items()} == {"travel": 0, "desks": 0}
        assert helpers.rising(page)
        assert test_whatsnew.seen(page) == ["1.1", None]
        assert errors == []
