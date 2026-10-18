// WEAVE's shared needle (#13): #16's sew-in, E3's mend in help.js (#18, #19) and E4's modelled needle (#22) build
// on it. It is live-path only: it imports Three, so never import it statically from the boot. Importing it builds
// nothing.
// Units are E1's scene units, where a block is 1.0. The frame's origin is the tip, +X runs from the tip to the eye
// end, and the eye's hole is along local Z.
// The child `body` spans 0.18 from the tip to the end of the eye, with metalness at most 0.3 and a light base colour
// (D29).
// The child `tail` is the thread: its colour is threadColor, default #C9A227, and its centre-line arc length is
// tailLength, default 0.12. It is rigid: it leaves the eye along +X and curves toward local -Y. It does not hang.
// Trail side: seen from local +Z, the tail curves to the left of the direction of travel, so it lies outside a
// clockwise loop. #16 runs its perimeters clockwise; E3 chooses its own direction.
// Posing: u is the arc-length fraction, and poseOnCurve clamps it to [0, 1] here, because r170 throws for splines and
// curve paths, extrapolates lines and returns NaN on analytic curves. NaN, undefined and other non-numbers pose at
// the start, and -Infinity and +Infinity at the nearer end. The tip goes to getPointAt(u), and +X runs along
// getTangentAt(u).negate(). The roll brings local Z as close as possible to world +Z, taken into the parent's space;
// when the tangent is vertical, any roll is used. The quaternion is always a unit quaternion; on a zero-length
// tangent it is left as it was. Posing writes only the needle's position and quaternion; reading the parent's world
// rotation refreshes the ancestors' world matrices, as a render does. The parent chain must have uniform positive
// scale, or the roll is only approximate.
// Frame ordering: pose a needle after its parent chain is posed for the frame, because posing reads the ancestors'
// current rotation.
// Disposal: a needle owns every geometry and material in it, so dispose it by traversal. #22 swaps the modelled body
// in the same frame; `tail` stays procedural.
import * as THREE from 'three';

// The body's run from the tip to the end of the eye, and the eye end the tail leaves from.
const BODY_LENGTH = 0.18;
const TAIL_SWEEP = THREE.MathUtils.degToRad(50);
const VERTICAL_EPS_SQ = 1e-12; // |up off the axis| below 1e-6: the tangent is vertical, so any roll will do

const _x = new THREE.Vector3();
const _y = new THREE.Vector3();
const _z = new THREE.Vector3();
const _up = new THREE.Vector3();
const _q = new THREE.Quaternion();
const _m = new THREE.Matrix4();

// The procedural body: a tapered shaft from the tip and an elongated eye whose hole is along Z. #22 replaces this.
function makeBody() {
  const material = new THREE.MeshStandardMaterial({ color: '#D9DDE2', metalness: 0.3, roughness: 0.3 });
  // A lathe profile (radius, run) from the tip's pole to a capped shaft end, turned so the lathe's Y axis is +X.
  const profile = [[0, 0], [0.0015, 0.006], [0.003, 0.02], [0.0035, 0.04], [0.0035, 0.156], [0, 0.158]]
    .map(([r, x]) => new THREE.Vector2(r, x));
  const shaft = new THREE.LatheGeometry(profile, 12).rotateZ(-Math.PI / 2);
  // The eye: a torus stretched along X, its far vertex (angle 0, at stretch * (R + r)) placed on the body's end.
  const R = 0.004;
  const r = 0.0012;
  const stretch = 2.5;
  const eye = new THREE.TorusGeometry(R, r, 8, 24).scale(stretch, 1, 1)
    .translate(BODY_LENGTH - stretch * (R + r), 0, 0);
  const body = new THREE.Group();
  body.name = 'body';
  body.add(new THREE.Mesh(shaft, material), new THREE.Mesh(eye, material));
  return body;
}

// A circular arc in the XY plane from the eye end, heading +X and turning toward -Y; its length is exactly `length`.
class TailArc extends THREE.Curve {
  constructor(length) {
    super();
    this.radius = length / TAIL_SWEEP;
  }

  getPoint(t, o = new THREE.Vector3()) {
    const a = TAIL_SWEEP * t;
    return o.set(BODY_LENGTH + this.radius * Math.sin(a), -this.radius * (1 - Math.cos(a)), 0);
  }
}

function makeTail(threadColor, tailLength) {
  const material = new THREE.MeshStandardMaterial({ color: threadColor, roughness: 0.85 });
  const tail = new THREE.Mesh(new THREE.TubeGeometry(new TailArc(tailLength), 24, 0.0025, 6, false), material);
  tail.name = 'tail';
  return tail;
}

export function createNeedle({ threadColor = '#C9A227', tailLength = 0.12 } = {}) {
  const needle = new THREE.Group();
  needle.add(makeBody(), makeTail(threadColor, tailLength));
  return needle;
}

export function poseOnCurve(needle, curve, u) {
  // NaN, -Infinity and non-numbers all fail `u > 0`, so they pose at the start.
  const t = typeof u === 'number' && u > 0 ? Math.min(1, u) : 0;
  // Read the returned vectors: a curve may ignore the target, as Three's own callers allow.
  needle.position.copy(curve.getPointAt(t, needle.position));
  _x.copy(curve.getTangentAt(t, _x)).negate();               // +X trails the tip
  if (_x.lengthSq() === 0) return;                           // zero tangent: keep the last roll (D-g)
  _x.normalize();
  _up.set(0, 0, 1);
  if (needle.parent) _up.applyQuaternion(needle.parent.getWorldQuaternion(_q).invert());
  if (_up.lengthSq() - _up.dot(_x) ** 2 < VERTICAL_EPS_SQ) {
    if (Math.abs(_x.x) < 0.9) _up.set(1, 0, 0); else _up.set(0, 1, 0);
  }
  _z.copy(_up).addScaledVector(_x, -_up.dot(_x)).normalize();
  _y.crossVectors(_z, _x);                                   // right-handed: x × y = z
  needle.quaternion.setFromRotationMatrix(_m.makeBasis(_x, _y, _z));
}
