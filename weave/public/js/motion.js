// WEAVE's motion: Coalesce's fixed-step springs and the quilt's ambient sway and pointer tilt. Pure: no Three,
// no DOM, and no clock of its own (D8): time arrives only as the dt the caller measured from rAF timestamps.
import { LAYOUT } from './layout.js';

// Coalesce's values (coalesce/public/js/motion.js).
export const STEP = 1 / 120;
export const MAX_DT = 0.05;

// A frame's dt, capped so a hitch (a background tab, a debugger) never launches the springs. Non-finite is 0.
export function capDt(dt) {
  return Number.isFinite(dt) ? Math.min(MAX_DT, Math.max(0, dt)) : 0;
}

// `count` damped springs, each pulling p toward target; stepped at a fixed STEP like Coalesce's stepPhysics.
export class SpringSet {
  constructor(count, { dims = 3, k = 38, zeta = 0.5 } = {}) {
    const zeros = () => Array.from({ length: count }, () => new Array(dims).fill(0));
    this.dims = dims;
    this.k = k;
    this.c = 2 * Math.sqrt(k) * zeta;
    this.p = zeros();
    this.v = zeros();
    this.target = zeros();
    this.acc = 0;
  }

  setTarget(i, vec) {
    for (let d = 0; d < this.dims; d += 1) this.target[i][d] = vec[d];
  }

  // Advances by the capped dt in whole STEPs (the remainder carries over); returns the capped dt.
  advance(dt) {
    const h = capDt(dt);
    this.acc += h;
    while (this.acc >= STEP) {
      for (let i = 0; i < this.p.length; i += 1) {
        const p = this.p[i];
        const v = this.v[i];
        const t = this.target[i];
        for (let d = 0; d < this.dims; d += 1) {
          v[d] += (this.k * (t[d] - p[d]) - this.c * v[d]) * STEP;
          p[d] += v[d] * STEP;
        }
      }
      this.acc -= STEP;
    }
    return h;
  }

  // Pause's "jump to the end": every spring at its target, at rest.
  snap() {
    for (let i = 0; i < this.p.length; i += 1) {
      this.p[i] = this.target[i].slice();
      this.v[i].fill(0);
    }
    this.acc = 0;
  }

  settled(eps) {
    return this.p.every((p, i) => p.every((x, d) => Math.abs(x - this.target[i][d]) <= eps
      && Math.abs(this.v[i][d]) <= eps));
  }
}

// The ambient motion. Sway rotates the quilt about the rod's own axis (x through the rod's centre); the pointer
// tilt rotates about y (left/right, up to tiltY) and, less, about x (up to tiltX), composed after the sway at the
// same pivot. The amplitudes are LAYOUT's ceilings, which the shadow plane is placed to clear.
export const AMBIENT = Object.freeze({
  swayRad: LAYOUT.ambientMax.sway,
  swayPeriod: 7,
  tiltX: LAYOUT.ambientMax.tiltX,
  tiltY: LAYOUT.ambientMax.tiltY,
  follow: 3,
});

// The sway angle at `clock` seconds: two incommensurate sines, so it never visibly loops; |angle| <= swayRad.
export function swayAngle(clock) {
  const { swayRad, swayPeriod } = AMBIENT;
  const a = Math.sin((2 * Math.PI * clock) / swayPeriod);
  const b = Math.sin((2 * Math.PI * clock) / (swayPeriod * 0.61) + 0.9);
  return swayRad * (0.75 * a + 0.25 * b);
}

// The tilt one frame of h seconds later, eased toward its target as Coalesce's startLive does.
export function followTilt(tilt, target, h) {
  const f = Math.min(1, h * AMBIENT.follow);
  return { x: tilt.x + (target.x - tilt.x) * f, y: tilt.y + (target.y - tilt.y) * f };
}
