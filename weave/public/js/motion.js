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

// Coalesce's in-out cubic (coalesce/public/js/motion.js:35-38).
export const ease = { inout: (u) => (u < 0.5 ? 4 * u * u * u : 1 - (-2 * u + 2) ** 3 / 2) };

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
    // Per-index { k, c } overrides (#8's path followers); null keeps the constructor's k and c.
    this.gains = new Array(count).fill(null);
    this.acc = 0;
  }

  // Spring i's own gains ({ k, zeta }), or null for the constructor's.
  setGains(i, gains) {
    this.gains[i] = gains ? { k: gains.k, c: 2 * Math.sqrt(gains.k) * gains.zeta } : null;
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
        const { k, c } = this.gains[i] ?? this;
        for (let d = 0; d < this.dims; d += 1) {
          v[d] += (k * (t[d] - p[d]) - c * v[d]) * STEP;
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

// --- The director (#8): the hero's state machine. ---

// The state names are a contract for #10 (intro) and E2's #15 and #16 (sewing); data-mode reads only SETTLED.
export const MODES = Object.freeze(['intro', 'quilt', 'unstitching', 'tiles', 'restitching', 'sewing']);
export const SETTLED = Object.freeze(['quilt', 'tiles']);
// pathDur and lift are Coalesce's path shape (s); stagger is s per scene unit from the origin; follow is
// Coalesce's path gains; settleEps is D40's settle (scene units and radians); pausedClickMs is the paused guard.
export const DIRECTOR = Object.freeze({
  pathDur: 1.2, stagger: 0.08, lift: 0.25, fadeDur: 0.8, follow: Object.freeze({ k: 70, zeta: 0.8 }),
  settleEps: 1e-3, pausedClickMs: 400,
});

// Where each transition goes: the settled mode it ends in, and the flip (s) and fade (g) it ends at.
const LEGS = Object.freeze({
  unstitching: Object.freeze({ settle: 'tiles', s: 1, g: 0 }),
  restitching: Object.freeze({ settle: 'quilt', s: 0, g: 1 }),
});

// The blocks' poses between the quilt (s = 0) and the tiles (s = 1), the fade of everything that is not a tile,
// and the mode. Pure like the rest of this module: time arrives only through advance(h), and `now` (an event's
// timeStamp, D8) only for the paused click guard. onEnter(mode, from) runs from enter(), the one writer of mode.
export class Director {
  constructor({ count, quiltPose, tilePose, isTile, onEnter }) {
    this.count = count;
    this.quilt = Array.from({ length: count }, (_, i) => quiltPose(i));
    this.tile = Array.from({ length: count }, (_, i) => tilePose(i));
    this.isTile = Array.from({ length: count }, (_, i) => isTile(i));
    this.onEnter = onEnter;
    this.springs = new SpringSet(count);
    // SpringSet starts at the origin; every block starts at its quilt pose.
    for (let i = 0; i < count; i += 1) {
      this.springs.setTarget(i, this.quilt[i].position);
      this.springs.p[i] = this.quilt[i].position.slice();
    }
    this.s = new Array(count).fill(0);
    this.g = 1;
    this.leg = null;
    this.time = 0;
    this.paused = false;
    this.lastSnapAt = -Infinity;
    this.lastSettleError = null;
    this.current = null;
  }

  get mode() { return this.current; }

  get fade() { return this.g; }

  get ambient() { return this.g; }

  enter(next) {
    const from = this.current;
    this.current = next;
    this.onEnter(next, from);
  }

  start(first = 'quilt') {
    this.enter(first);
  }

  // Block i's pose: position from its spring, the rest blended by its flip s (the ends exactly).
  pose(i) {
    const q = this.quilt[i];
    const t = this.tile[i];
    const s = this.s[i];
    const mix = (key) => (s === 0 ? q[key] : s === 1 ? t[key] : q[key] + (t[key] - q[key]) * s);
    return { position: this.springs.p[i].slice(), rotY: mix('rotY'), rotZ: mix('rotZ'), morph: mix('morph') };
  }

  toggle(now, origin = [0, 0]) {
    const next = { quilt: 'unstitching', tiles: 'restitching', unstitching: 'restitching', restitching: 'unstitching' };
    if (!(this.current in next)) return false;
    this.begin(next[this.current], origin);
    return this.snapIfPaused(now);
  }

  // hit is what scene.js's pick returns; true when the click acted.
  click(hit, now) {
    if (this.paused && now - this.lastSnapAt < DIRECTOR.pausedClickMs) return false;
    if (this.current === 'quilt' && (hit.part === 'block' || hit.part === 'sashing')) this.begin('unstitching', hit.point);
    else if (this.current === 'tiles' && hit.part === 'none') this.begin('restitching', hit.point);
    else return false;
    return this.snapIfPaused(now);
  }

  setPaused(paused, now) {
    this.paused = paused;
    if (paused && this.finish()) this.lastSnapAt = now;
  }

  // A transition jumps to its end: snap, then enter its settled mode. False when none is running.
  finish() {
    if (!this.leg) return false;
    const { settle } = this.leg;
    this.snap();
    this.enter(settle);
    return true;
  }

  advance(h) {
    this.time += h;
    this.springs.advance(h);
  }

  // --- Internals. ---

  begin(next, origin) {
    this.leg = { ...LEGS[next], origin };
    this.enter(next);
  }

  snapIfPaused(now) {
    if (this.paused && this.finish()) this.lastSnapAt = now;
    return true;
  }

  // The endpoint itself, never the arc's value at u = 1: positions, flips and the fade land exactly.
  snap() {
    const { s, g } = this.leg;
    for (let i = 0; i < this.count; i += 1) {
      if (!this.isTile[i]) continue;
      this.springs.setTarget(i, (s ? this.tile : this.quilt)[i].position);
      this.s[i] = s;
    }
    this.springs.snap();
    this.g = g;
    this.leg = null;
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
