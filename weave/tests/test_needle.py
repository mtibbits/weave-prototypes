"""needle.js: the shared needle (#13): its frame, body, tail, posing on a curve and the clamp."""
import math

import pytest

EPS = 1e-6                        # positions and unit lengths; float32 geometry readback (pothole Issue-10)
ANTI = -0.999                     # +X . tangent must be at most this
COS_1_DEG = math.cos(math.radians(1))
TAIL_REL = 0.01                   # tail arc length within 1 %

# The curves, frames and readers every contract test shares. The tail's centre line is read back from the rendered
# TubeGeometry's rings, never from the module's own arc, so the length check cannot share production's maths.
NEEDLE_JS = r"""
const THREE = await import('three'); const N = await import('/public/js/needle.js');
class Circle extends THREE.Curve {
  constructor(r, clockwise, cx = 0, cy = 0, a0 = 0) {
    super(); this.r = r; this.cw = clockwise; this.cx = cx; this.cy = cy; this.a0 = a0;
  }
  getPoint(t, o = new THREE.Vector3()) {
    const a = this.a0 + (this.cw ? -1 : 1) * 2 * Math.PI * t;
    return o.set(this.cx + this.r * Math.cos(a), this.cy + this.r * Math.sin(a), 0);
  }
}
const V = (x, y, z) => new THREE.Vector3(x, y, z);
const curves = () => ({
  line: new THREE.LineCurve3(V(-0.3, -0.1, 0), V(0.4, 0.25, 0)),
  circle: new Circle(0.5, true),
  catmull: new THREE.CatmullRomCurve3([V(-0.4, 0, 0), V(-0.1, 0.3, 0), V(0.2, -0.1, 0), V(0.5, 0.2, 0)]),
});
const axis = (obj, i) => new THREE.Vector3().setFromMatrixColumn(obj.matrixWorld, i).normalize();
const poseOf = (n) => [...n.position.toArray(), ...n.quaternion.toArray()];
const centreLine = (n) => {
  const tails = n.children.filter((c) => c.name === 'tail');
  const tail = tails[0];
  if (tails.length !== 1 || !tail.isMesh || tail.geometry.type !== 'TubeGeometry') {
    throw new Error('contract: a needle has one child Mesh named tail, built on a TubeGeometry');
  }
  const { tubularSegments, radialSegments } = tail.geometry.parameters;
  const pos = tail.geometry.attributes.position;
  tail.updateMatrix();
  const points = [];
  for (let i = 0; i <= tubularSegments; i += 1) {
    const c = new THREE.Vector3();
    for (let j = 0; j < radialSegments; j += 1) {
      c.add(new THREE.Vector3().fromBufferAttribute(pos, i * (radialSegments + 1) + j));
    }
    points.push(c.divideScalar(radialSegments).applyMatrix4(tail.matrix));
  }
  return points;
};
const boxOf = (obj) => {
  let root = obj;
  while (root.parent) root = root.parent;
  root.updateMatrixWorld(true);
  return new THREE.Box3().setFromObject(obj, true);
};
const materialsOf = (obj) => {
  const out = [];
  obj.traverse((o) => { if (o.isMesh) out.push(...(Array.isArray(o.material) ? o.material : [o.material])); });
  return out;
};
"""


def run(js, body):
    return js(NEEDLE_JS + body)


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def norm(a):
    return math.sqrt(dot(a, a))


def close(a, b, eps=EPS):
    return len(a) == len(b) and all(abs(x - y) <= eps for x, y in zip(a, b))


def test_create_needle_has_body_and_tail_with_its_origin_at_the_tip(js):
    r = run(js, r"""
        const n = N.createNeedle();
        n.updateMatrixWorld(true);
        const tip = [];
        n.getObjectByName('body').traverse((o) => {
          if (!o.isMesh) return;
          const p = o.geometry.attributes.position;
          for (let i = 0; i < p.count; i += 1) {
            const v = new THREE.Vector3().fromBufferAttribute(p, i).applyMatrix4(o.matrixWorld);
            if (v.x <= 1e-6) tip.push(v.toArray());
          }
        });
        return { isObject3D: n.isObject3D === true, names: n.children.map((c) => c.name).sort(),
                 position: n.position.toArray(), quaternion: n.quaternion.toArray(), tip };
    """)
    assert r["isObject3D"] is True
    assert r["names"] == ["body", "tail"]
    assert r["position"] == [0, 0, 0] and r["quaternion"] == [0, 0, 0, 1]
    assert len(r["tip"]) >= 1
    centroid = [sum(v[i] for v in r["tip"]) / len(r["tip"]) for i in range(3)]
    assert abs(centroid[1]) <= 1e-5 and abs(centroid[2]) <= 1e-5, centroid


def test_body_spans_the_tip_to_the_eye_end(js):
    r = run(js, r"""
        const n = N.createNeedle();
        const body = boxOf(n.getObjectByName('body'));
        const all = boxOf(n);
        return { min: body.min.x, max: body.max.x, all: all.max.x };
    """)
    assert abs(r["min"]) <= EPS, r
    assert abs(r["max"] - 0.18) <= EPS, r
    # Sanity: the tail reaches past the eye, so the body measurement above excluded it.
    assert r["all"] > 0.18 + 0.05, r


def test_every_body_material_is_at_most_0_3_metallic(js):
    r = run(js, r"""
        return materialsOf(N.createNeedle().getObjectByName('body')).map((m) => [typeof m.metalness, m.metalness]);
    """)
    assert len(r) >= 1
    assert all(kind == "number" and value <= 0.3 for kind, value in r), r


def test_tail_uses_the_thread_color(js):
    r = run(js, r"""
        const custom = N.createNeedle({ threadColor: '#3366CC' });
        const plain = N.createNeedle();
        const colours = (n) => materialsOf(n.getObjectByName('tail')).map((m) => m.color.getHexString());
        return { custom: colours(custom), plain: colours(plain) };
    """)
    assert len(r["custom"]) >= 1 and len(r["plain"]) >= 1
    assert set(r["custom"]) == {"3366cc"}, r
    assert set(r["plain"]) == {"c9a227"}, r


def test_tail_starts_at_the_eye_and_ends_below_it(js):
    r = run(js, "return centreLine(N.createNeedle()).map((p) => p.toArray());")
    assert len(r) >= 2
    assert close(r[0], [0.18, 0, 0]), r[0]
    first = [b - a for a, b in zip(r[0], r[1])]
    assert dot(first, [1, 0, 0]) / norm(first) >= 0.99, first
    assert r[-1][1] < 0, r[-1]


@pytest.mark.parametrize("tail_length, expected", [(None, 0.12), (0.2, 0.2)])
def test_tail_arc_length_is_tail_length(js, tail_length, expected):
    options = "" if tail_length is None else f"{{ tailLength: {tail_length} }}"
    r = run(js, f"return centreLine(N.createNeedle({options})).map((p) => p.toArray());")
    assert len(r) >= 2
    length = sum(norm([b - a for a, b in zip(p, q)]) for p, q in zip(r, r[1:]))
    assert abs(length - expected) / expected <= TAIL_REL, length


@pytest.mark.parametrize("u", [0, 0.5, 1])
@pytest.mark.parametrize("curve", ["line", "circle"])
def test_pose_on_line_and_circle(js, curve, u):
    r = run(js, f"""
        const c = curves().{curve};
        const scene = new THREE.Scene();
        const n = N.createNeedle();
        scene.add(n);
        N.poseOnCurve(n, c, {u});
        scene.updateMatrixWorld(true);
        return {{ tip: n.getWorldPosition(new THREE.Vector3()).toArray(), point: c.getPointAt({u}).toArray(),
                 tangent: c.getTangentAt({u}).toArray(), x: axis(n, 0).toArray(), z: axis(n, 2).toArray() }};
    """)
    assert close(r["tip"], r["point"]), r
    assert dot(r["x"], r["tangent"]) <= ANTI, r
    assert dot(r["z"], [0, 0, 1]) >= COS_1_DEG, r


@pytest.mark.parametrize("curve", ["line", "circle", "catmull"])
def test_clamp_holds_the_ends(js, curve):
    r = run(js, f"""
        const c = curves().{curve};
        const n = N.createNeedle();
        const errors = [];
        const pose = (u) => {{
          try {{ N.poseOnCurve(n, c, u); }} catch (e) {{ errors.push(String(e)); }}
          return poseOf(n);
        }};
        pose(0.7);
        const poses = {{ below: pose(-0.1), start: pose(0), justOver: pose(1 + 1e-9), over: pose(1.5), end: pose(1) }};
        // The r170 control (U1): why the clamp is load-bearing. Read off fresh curves, never the posed one.
        let raw = null;
        try {{ raw = {{ value: curves().{curve}.getPointAt(1 + 1e-9).toArray() }}; }}
        catch (e) {{ raw = {{ threw: e.name }}; }}
        const line = curves().line;
        return {{ errors, poses, raw, lineMoves: line.getPointAt(1.5).x !== line.getPointAt(1).x }};
    """)
    assert r["errors"] == []
    p = r["poses"]
    assert p["below"] == p["start"]
    assert p["justOver"] == p["end"] and p["over"] == p["end"]
    control = "r170's out-of-range getPointAt changed (U1, #13): re-check whether poseOnCurve's clamp is needed"
    if curve == "line":
        assert all(math.isfinite(v) for v in r["raw"]["value"]), control
    elif curve == "circle":
        assert math.isnan(r["raw"]["value"][0]), control
    else:
        assert r["raw"] == {"threw": "TypeError"}, control
    assert r["lineMoves"] is True, control


def test_clamp_maps_non_finite_u_to_an_end(js):
    """D-a, beyond the AC: a caller slip never throws in the render loop."""
    r = run(js, r"""
        const c = curves().catmull;
        const n = N.createNeedle();
        const errors = [];
        const pose = (...args) => {
          try { N.poseOnCurve(n, c, ...args); } catch (e) { errors.push(String(e)); }
          return poseOf(n);
        };
        const start = pose(0); const end = pose(1);
        return { errors, start, end, nan: pose(NaN), undef: pose(), text: pose('x'), minusInf: pose(-Infinity),
                 plusInf: pose(Infinity) };
    """)
    assert r["errors"] == []
    for leg in ("nan", "undef", "text", "minusInf"):
        assert r[leg] == r["start"], leg
    assert r["plusInf"] == r["end"]


@pytest.mark.parametrize("ends", [
    [[0.2, 0.1, 0], [0.2, 0.1, 1]],
    [[0.2, 0.1, 1], [0.2, 0.1, 0]],
    [[0, 0, 0], [1e-9, 0, 1]],
], ids=["up", "down", "nearly-up"])
def test_vertical_tangent_is_a_true_rotation(js, ends):
    (a, b) = ends
    r = run(js, f"""
        const c = new THREE.LineCurve3(V({a[0]}, {a[1]}, {a[2]}), V({b[0]}, {b[1]}, {b[2]}));
        const scene = new THREE.Scene();
        const n = N.createNeedle();
        scene.add(n);
        N.poseOnCurve(n, c, 0.5);
        scene.updateMatrixWorld(true);
        const cols = [0, 1, 2].map((i) => new THREE.Vector3().setFromMatrixColumn(n.matrixWorld, i).toArray());
        return {{ pose: poseOf(n), tip: n.getWorldPosition(new THREE.Vector3()).toArray(),
                 point: c.getPointAt(0.5).toArray(), tangent: c.getTangentAt(0.5).toArray(), x: axis(n, 0).toArray(),
                 cols, det: n.matrixWorld.determinant() }};
    """)
    assert all(math.isfinite(v) for v in r["pose"]), r
    assert abs(norm(r["pose"][3:]) - 1) <= EPS, r
    assert close(r["tip"], r["point"]), r
    assert dot(r["x"], r["tangent"]) <= ANTI, r
    cols = r["cols"]
    assert all(abs(norm(col) - 1) <= EPS for col in cols), cols
    assert all(abs(dot(cols[i], cols[j])) <= EPS for i, j in ((0, 1), (0, 2), (1, 2))), cols
    assert r["det"] > 0, r


# The parent-space reading: world +Z projected off the needle's axis, computed from the world frame alone.
PARENT_CHECK = r"""
    const a = axis(n, 0);
    const Z = V(0, 0, 1);
    const want = Z.clone().addScaledVector(a, -Z.dot(a)).normalize();
    const tangent = c.getTangentAt(u).applyQuaternion(parent.getWorldQuaternion(new THREE.Quaternion()));
    const out = { z: axis(n, 2).toArray(), want: want.toArray(), tip: n.getWorldPosition(new THREE.Vector3()).toArray(),
                  point: parent.localToWorld(c.getPointAt(u)).toArray(), x: a.toArray(), tangent: tangent.toArray() };
"""


def assert_parent_space(r):
    assert close(r["z"], r["want"]), r
    assert close(r["tip"], r["point"]), r
    assert dot(r["x"], r["tangent"]) <= ANTI, r


@pytest.mark.parametrize("u", [0, 0.25, 0.5])
@pytest.mark.parametrize("curve", ["line", "circle"])
def test_parent_space_turns_the_eye_to_world_z(js, curve, u):
    r = run(js, f"""
        const c = curves().{curve};
        const u = {u};
        const scene = new THREE.Scene();
        const parent = new THREE.Group();
        parent.rotation.x = Math.PI / 6;
        const n = N.createNeedle();
        scene.add(parent); parent.add(n);
        N.poseOnCurve(n, c, u);                       // before any matrix update (D-b)
        scene.updateMatrixWorld(true);
        {PARENT_CHECK}
        // The parent-ignorant answer: parent-space Z projected off the local axis, then turned by the parent.
        const xl = c.getTangentAt(u).negate().normalize();
        const naive = V(0, 0, 1).addScaledVector(xl, -xl.z).normalize()
          .applyQuaternion(parent.getWorldQuaternion(new THREE.Quaternion()));
        out.naiveGap = naive.distanceTo(axis(n, 2));
        return out;
    """)
    assert_parent_space(r)
    if curve == "line":
        # Discriminating control: the test can tell world Z from the parent's Z (0.47 apart by hand).
        assert r["naiveGap"] > 0.1, r


def test_parent_space_holds_through_a_nested_chain(js):
    """Test 11's nested leg: scene.js's block rotation.z inside group's Ry.Rx; a parent-local reading fails (M10)."""
    r = run(js, f"""
        const c = curves().line;
        const u = 0.5;
        const scene = new THREE.Scene();
        const grand = new THREE.Group();
        grand.rotation.set(0.3, 0.5, 0, 'YXZ');
        const parent = new THREE.Group();
        parent.rotation.z = 0.4;
        const n = N.createNeedle();
        scene.add(grand); grand.add(parent); parent.add(n);
        N.poseOnCurve(n, c, u);                       // before any matrix update (D-b)
        scene.updateMatrixWorld(true);
        {PARENT_CHECK}
        return out;
    """)
    assert_parent_space(r)


def test_posing_sets_only_position_and_quaternion(js):
    r = run(js, r"""
        const scene = new THREE.Scene();
        const parent = new THREE.Group();
        parent.rotation.x = Math.PI / 6;
        const n = N.createNeedle();
        scene.add(parent); parent.add(n);
        const t = (o) => [o.position.toArray(), o.quaternion.toArray(), o.scale.toArray()];
        const snap = () => JSON.stringify({
          needle: [n.scale.toArray(), n.up.toArray(), n.visible, n.matrixAutoUpdate],
          children: n.children.map(t), parent: t(parent),
        });
        const before = snap(); const pose = poseOf(n);
        N.poseOnCurve(n, curves().circle, 0.3);
        return { before, after: snap(), pose, posed: poseOf(n) };
    """)
    assert r["after"] == r["before"]
    # Positive control: posing did move the needle.
    assert r["posed"][:3] != r["pose"][:3] and r["posed"][3:] != r["pose"][3:], r


@pytest.mark.parametrize("u", [0.125, 0.5])
def test_tail_trails_outside_a_clockwise_loop(js, u):
    """Beyond the AC: #16 runs its perimeters clockwise, so its tails must lie outside the loop."""
    r = run(js, f"""
        const side = (clockwise) => {{
          const scene = new THREE.Scene();
          const n = N.createNeedle();
          scene.add(n);
          N.poseOnCurve(n, new Circle(0.5, clockwise), {u});
          scene.updateMatrixWorld(true);
          const tip = n.getWorldPosition(new THREE.Vector3());
          const end = n.localToWorld(centreLine(n).at(-1));
          return end.sub(tip).dot(tip.clone().normalize());
        }};
        return {{ clockwise: side(true), counter: side(false) }};
    """)
    assert r["clockwise"] > 0.01, r
    assert r["counter"] < -0.01, r


def test_each_needle_owns_its_geometry_and_materials(js):
    r = run(js, r"""
        const parts = (n) => {
          const geometries = new Set(); const materials = new Set();
          n.traverse((o) => { if (o.isMesh) geometries.add(o.geometry.uuid); });
          materialsOf(n).forEach((m) => materials.add(m.uuid));
          return { geometries: [...geometries], materials: [...materials] };
        };
        return [parts(N.createNeedle()), parts(N.createNeedle())];
    """)
    a, b = r
    assert len(a["geometries"]) >= 2 and len(b["geometries"]) >= 2, r
    assert not set(a["geometries"]) & set(b["geometries"]), r
    assert not set(a["materials"]) & set(b["materials"]), r


def test_importing_builds_nothing(js):
    """r170 stamps one global id counter on every BufferGeometry and another on every Material, so anything built at
    import time shows up as a gap between two probes."""
    r = js(r"""
        const THREE = await import('three');
        const probe = () => [new THREE.BufferGeometry().id, new THREE.MeshBasicMaterial().id];
        const before = probe();
        const N = await import('/public/js/needle.js');
        const after = probe();
        N.createNeedle();
        const built = probe();
        return { before, after, built };
    """)
    assert r["after"] == [r["before"][0] + 1, r["before"][1] + 1], r
    # Positive control: building a needle does open a gap.
    assert r["built"][0] - r["after"][0] > 1 and r["built"][1] - r["after"][1] > 1, r


def test_zero_tangent_leaves_the_quaternion(js):
    """D-g: a degenerate curve moves the tip and keeps the last roll."""
    r = run(js, r"""
        const scene = new THREE.Scene();
        const n = N.createNeedle();
        scene.add(n);
        n.quaternion.setFromAxisAngle(V(1, 2, 3).normalize(), 0.7);
        const before = n.quaternion.toArray();
        let error = null;
        try { N.poseOnCurve(n, new THREE.LineCurve3(V(0.1, 0.2, 0), V(0.1, 0.2, 0)), 0.5); }
        catch (e) { error = String(e); }
        return { error, before, position: n.position.toArray(), after: n.quaternion.toArray() };
    """)
    assert r["error"] is None
    assert close(r["position"], [0.1, 0.2, 0]), r
    assert r["after"] == r["before"]
