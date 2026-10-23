// The Help corner's loose threads (#18): a pure simulation, with no Three and no DOM. help.js draws it and #19's mend
// builds on it. Importing it builds nothing.
// The model: 10 strands, each a chain of 16 points. Point 0 is pinned to its pin on the fray edge and never moves.
// The rest are Verlet points joined by distance constraints, moved by gravity (−y), damping, a weak pull back toward
// the seeded rest pose (a thread's curl), a gentle seeded breeze in x and a soft push away from the stir point within
// STIR_RADIUS (0.4 scene units; a block is 1.0). Every point
// keeps its pin's z, so the strands move in their plane and a pointer cast onto that plane is exact. Points are in
// the Help scene's world space, in scene units, as [x, y, z] arrays that are mutated in place, never reallocated.
// The clock: advance(dt) takes seconds, clamped to MAX_DT, and steps the physics in fixed steps of 1/120 s; `clock`
// is the sim time in seconds. help.js passes the dt between requestAnimationFrame timestamps, never a Date
// difference: #12's test clock pins Date, so a sim timed by Date would freeze in every test. A dt that is not a
// positive number (NaN, a string, a boolean, an array, a BigInt) steps nothing.
// Randomness: the rest pose and the breeze come only from mulberry32(seed), with seed a uint32 (help.js passes
// seedFor('help-fray', 'fray')); there is no Math.random. The same seed always gives the same points.
// Fields: strands[i].points (16 [x, y, z], the pinned top first) and strands[i].hanging, the strand's current rest
// length over its starting rest length (a setting #19 shortens, not a measured length); frayAmount, from 0 (mended)
// to 1 (fully frayed); state; clock; and stir, an [x, y, z] copy in world space, or null. In #18 the state is always
// 'frayed', frayAmount is 1 and every hanging is 1; #19 adds the other states. A hanging that is not a finite number
// counts as 1. setStir(p) takes [x, y, z] or null and stores a copy; anything but three finite numbers clears it.
// ?pose=rest (createFray's `rest`): no breeze and no stir, and no integration step runs, so the points hold the
// seeded rest pose exactly while the clock still advances.
// The page hook stage.__weaveHelp = { fray, stop(reason), project(p), edge, needle, spool }: fray is this simulation,
// edge the fray-edge curve in world space, and needle and spool the props as drawn. help.js has its full shape.
import { mulberry32 } from './random.js';

export const STRANDS = 10;
export const POINTS = 16;
export const STEP = 1 / 120;
export const MAX_DT = 0.05;
export const STIR_RADIUS = 0.4;

const GRAVITY = 1.2;
// The curl's spring toward the rest pose, per second squared.
const CURL = 6;
const DAMPING = 0.985;
const BREEZE = 0.35;
const STIR_PUSH = 12;
const ITERATIONS = 6;
const SEGMENTS = POINTS - 1;

const isUint32 = (n) => Number.isInteger(n) && n >= 0 && n <= 0xffffffff;

export function createFray({ pins, length, seed, rest = false }) {
  if (!isUint32(seed)) throw new TypeError('createFray: seed must be a uint32');
  const rng = mulberry32(seed);
  const anchors = pins.map((p) => [p[0], p[1], p[2]]);
  const restSegment = length / SEGMENTS;
  // Per strand: the rest pose's lean and curl, then the breeze's two phases.
  const strands = anchors.map((pin) => {
    const lean = (rng() - 0.5) * 0.25;
    const curl = (rng() - 0.5) * 0.9;
    const points = [[...pin]];
    for (let j = 1; j < POINTS; j += 1) {
      const a = lean + curl * (j / SEGMENTS);
      const [x, y] = points[j - 1];
      points.push([x + restSegment * Math.sin(a), y - restSegment * Math.cos(a), pin[2]]);
    }
    return { points, hanging: 1 };
  });
  const phases = strands.map(() => [rng() * 2 * Math.PI, rng() * 2 * Math.PI]);
  const previous = strands.map((s) => s.points.map((p) => [p[0], p[1]]));
  const shape = strands.map((s) => s.points.map((p) => [p[0], p[1]]));
  let clock = 0;
  let pending = 0;
  let stir = null;

  function integrate() {
    const h2 = STEP * STEP;
    strands.forEach((strand, k) => {
      const { points } = strand;
      const [a, b] = phases[k];
      const wind = rest ? 0 : BREEZE * (Math.sin(1.7 * clock + a) + 0.5 * Math.sin(4.3 * clock + b));
      for (let j = 1; j < POINTS; j += 1) {
        const p = points[j];
        const q = previous[k][j];
        const home = shape[k][j];
        let ax = wind * (j / SEGMENTS) + CURL * (home[0] - p[0]);
        let ay = -GRAVITY + CURL * (home[1] - p[1]);
        if (stir) {
          const dx = p[0] - stir[0];
          const dy = p[1] - stir[1];
          const d = Math.hypot(dx, dy);
          if (d < STIR_RADIUS) {
            const f = STIR_PUSH * (1 - d / STIR_RADIUS) ** 2;
            ax += d > 1e-9 ? (f * dx) / d : f;
            ay += d > 1e-9 ? (f * dy) / d : 0;
          }
        }
        const vx = (p[0] - q[0]) * DAMPING;
        const vy = (p[1] - q[1]) * DAMPING;
        q[0] = p[0];
        q[1] = p[1];
        p[0] += vx + ax * h2;
        p[1] += vy + ay * h2;
      }
      // hanging is #19's to write: anything but a finite number keeps the full length, never a NaN chain.
      const hanging = Number(strand.hanging);
      const segment = restSegment * (Number.isFinite(hanging) ? Math.max(0, hanging) : 1);
      for (let n = 0; n < ITERATIONS; n += 1) {
        for (let j = 1; j < POINTS; j += 1) {
          const u = points[j - 1];
          const v = points[j];
          const dx = v[0] - u[0];
          const dy = v[1] - u[1];
          const d = Math.hypot(dx, dy);
          if (d === 0) continue;
          const diff = (d - segment) / d;
          if (j === 1) {
            v[0] -= dx * diff;
            v[1] -= dy * diff;
          } else {
            u[0] += dx * diff * 0.5;
            u[1] += dy * diff * 0.5;
            v[0] -= dx * diff * 0.5;
            v[1] -= dy * diff * 0.5;
          }
        }
      }
    });
  }

  return {
    strands,
    frayAmount: 1,
    state: 'frayed',
    get clock() { return clock; },
    get stir() { return stir && [...stir]; },
    setStir(p) {
      const point = Array.isArray(p) && p.length === 3 ? p.map(Number) : null;
      stir = rest || !point || !point.every(Number.isFinite) ? null : point;
    },
    advance(dt) {
      if (typeof dt !== 'number' || !(dt > 0)) return;
      pending += Math.min(dt, MAX_DT);
      while (pending >= STEP) {
        pending -= STEP;
        if (!rest) integrate();
        clock += STEP;
      }
    },
  };
}
