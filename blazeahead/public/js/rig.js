// Camera maths for the tour: fitting a view to any window shape, easing, and walks along a path.
// Everything here is plain arrays of numbers ([x, y, z]) so it can be tested without a renderer.

const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));

// Views keep a fixed horizontal field of view, so the edge signposts stay at the window's edges on any shape.
export function fitVerticalFov(hfovDeg, aspect) {
  const half = (hfovDeg * Math.PI) / 360;
  return (2 * Math.atan(Math.tan(half) / aspect) * 180) / Math.PI;
}

// A walk eases in, glides at a steady pace and eases out: its speed rises smoothly over the first 30 % of the time
// and falls over the last 30 %, so it never tops about 1.4x the walk's average (a cubic ease surges to 3x mid-walk).
const RAMP = 0.3;
const GLIDE = 1 / (1 - RAMP);                           // the steady speed, relative to the average
const rampDistance = (x) => x * x * x - (x * x * x * x) / 2;   // covered while the speed rises (a smoothstep)

export function easeInOut(t) {
  const x = clamp(t, 0, 1);
  if (x < RAMP) return GLIDE * RAMP * rampDistance(x / RAMP);
  if (x > 1 - RAMP) return 1 - GLIDE * RAMP * rampDistance((1 - x) / RAMP);
  return 0.5 + GLIDE * (x - 0.5);
}

// An unhurried stroll: about 2.9 m/s on average, so a leg between stops (about 27 m) takes about 9.5 s. Never shorter
// than 4 s nor longer than 12 s. Raise WALK_SPEED for a brisker tour.
const WALK_SPEED = 2.9;

export function walkDuration(lengthM) {
  return clamp(lengthM / WALK_SPEED, 4, 12);
}

// Where the camera looks on a walk. The stops face sideways onto their props, about a right angle from the path, so
// the camera turns from the stop's view to face down the path as it sets off, and turns to the next stop's view as it
// arrives. Each turn takes as long as its angle needs at TURN_RATE on average (a right angle: 4.5 s), but no more
// than half the walk; it eases in and out, so it peaks at about 1.5x that. In between, the camera looks at the path
// 5 to 20 m ahead, averaged, so it doesn't sway with every bend. Lower TURN_RATE for a lazier turn.
const TURN_RATE = 20;   // degrees per second
const LOOK_AHEAD_M = [5, 10, 15, 20];

const smoothstep = (x) => {
  const c = clamp(x, 0, 1);
  return c * c * (3 - 2 * c);
};

function heading(from, to) {
  const dx = to[0] - from[0];
  const dy = to[1] - from[1];
  const dz = to[2] - from[2];
  return { yaw: Math.atan2(dx, dz), pitch: Math.atan2(dy, Math.hypot(dx, dz)) };
}

// the turn from a to b, the shorter way round
const yawGap = (a, b) => ((((b.yaw - a.yaw + Math.PI) % (2 * Math.PI)) + 2 * Math.PI) % (2 * Math.PI)) - Math.PI;

function blendHeading(a, b, w) {
  return { yaw: a.yaw + yawGap(a, b) * w, pitch: a.pitch + (b.pitch - a.pitch) * w };
}

function turnSeconds(a, b, durationS) {
  return clamp((Math.abs(yawGap(a, b)) * 180) / Math.PI / TURN_RATE, 0.5, durationS / 2);
}

// The point d metres further along a walk; past its end, straight on along its final stretch.
function pointAhead(walk, u, d) {
  const v = u + d / walk.length;
  if (v <= 1) return walk.pointAt(v);
  const end = walk.pointAt(1);
  const before = walk.pointAt(1 - 0.5 / walk.length);
  const step = Math.max(1e-6, Math.hypot(end[0] - before[0], end[1] - before[1], end[2] - before[2]));
  return end.map((e, j) => e + ((e - before[j]) * (v - 1) * walk.length) / step);
}

// Where the path leads from fraction u of a walk: towards the mean of the points ahead, a little below eye height.
function pathHeading(walk, u) {
  const aim = [0, -0.4, 0];
  for (const d of LOOK_AHEAD_M) {
    const p = pointAhead(walk, u, d);
    for (let j = 0; j < 3; j++) aim[j] += p[j] / LOOK_AHEAD_M.length;
  }
  return heading(walk.pointAt(u), aim);
}

// The camera's pose at time fraction t of a walk lasting durationS, starting on one view's target and ending on
// the next one's.
export function walkPose(walk, t, durationS, fromTarget, toTarget) {
  const u = easeInOut(t);
  const position = walk.pointAt(u);
  if (t <= 0) return { position, target: [...fromTarget] };
  if (t >= 1) return { position, target: [...toTarget] };
  const fromView = heading(walk.pointAt(0), fromTarget);
  const toView = heading(walk.pointAt(1), toTarget);
  const setOff = turnSeconds(fromView, pathHeading(walk, 0), durationS);
  const arrive = turnSeconds(pathHeading(walk, 1), toView, durationS);
  const s = t * durationS;
  let look = blendHeading(fromView, pathHeading(walk, u), smoothstep(s / setOff));
  look = blendHeading(look, toView, smoothstep((s - (durationS - arrive)) / arrive));
  const flat = Math.cos(look.pitch);
  return {
    position,
    target: [position[0] + Math.sin(look.yaw) * flat, position[1] + Math.sin(look.pitch), position[2] + Math.cos(look.yaw) * flat],
  };
}

function catmull(p0, p1, p2, p3, t) {
  const t2 = t * t;
  const t3 = t2 * t;
  return p1.map((_, j) => 0.5 * (2 * p1[j] + (-p0[j] + p2[j]) * t + (2 * p0[j] - 5 * p1[j] + 4 * p2[j] - p3[j]) * t2
    + (-p0[j] + 3 * p1[j] - 3 * p2[j] + p3[j]) * t3));
}

function curvePoint(pts, seg, t) {
  const n = pts.length;
  const at = (i) => {
    if (i < 0) return pts[0].map((v, j) => 2 * v - pts[1][j]);
    if (i >= n) return pts[n - 1].map((v, j) => 2 * v - pts[n - 2][j]);
    return pts[i];
  };
  return catmull(at(seg - 1), at(seg), at(seg + 1), at(seg + 2), t);
}

// A walk: the camera's path, a smooth curve through its points, travelled at even speed.
export class Walk {
  constructor(points, samplesPerSegment = 24) {
    if (!Array.isArray(points) || points.length < 2) throw new Error('A walk needs at least two points.');
    this.points = points;
    this.table = [{ s: 0, seg: 0, t: 0 }];
    let prev = points[0];
    let s = 0;
    for (let seg = 0; seg < points.length - 1; seg++) {
      for (let k = 1; k <= samplesPerSegment; k++) {
        const t = k / samplesPerSegment;
        const p = curvePoint(points, seg, t);
        s += Math.hypot(p[0] - prev[0], p[1] - prev[1], p[2] - prev[2]);
        this.table.push({ s, seg, t });
        prev = p;
      }
    }
    this.total = s;
  }

  get length() {
    return this.total;
  }

  // the point a fraction u of the way along the curve, by distance
  pointAt(u) {
    if (u <= 0) return [...this.points[0]];
    if (u >= 1) return [...this.points[this.points.length - 1]];
    const want = u * this.total;
    let lo = 0;
    let hi = this.table.length - 1;
    while (hi - lo > 1) {
      const mid = (lo + hi) >> 1;
      if (this.table[mid].s < want) lo = mid;
      else hi = mid;
    }
    const a = this.table[lo];
    const b = this.table[hi];
    const f = b.s > a.s ? (want - a.s) / (b.s - a.s) : 0;
    const seg = b.seg;
    const ta = a.seg === seg ? a.t : 0;
    const t = ta + (b.t - ta) * f;
    return curvePoint(this.points, seg, t);
  }
}
