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

const damping = (k, zeta) => 2 * Math.sqrt(k) * zeta;
const progress = (t, t0, dur) => Math.min(1, Math.max(0, (t - t0) / dur));

// `count` damped springs, each pulling p toward target; stepped at a fixed STEP like Coalesce's stepPhysics.
export class SpringSet {
  constructor(count, { dims = 3, k = 38, zeta = 0.5 } = {}) {
    const zeros = () => Array.from({ length: count }, () => new Array(dims).fill(0));
    this.dims = dims;
    this.k = k;
    this.c = damping(k, zeta);
    this.p = zeros();
    this.v = zeros();
    this.target = zeros();
    // Per-index { k, c } overrides (#8's path followers); null keeps the constructor's k and c.
    this.gains = new Array(count).fill(null);
    this.acc = 0;
  }

  // Spring i's own gains ({ k, zeta }), or null for the constructor's.
  setGains(i, gains) {
    this.gains[i] = gains ? { k: gains.k, c: damping(gains.k, gains.zeta) } : null;
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
// pathDur (s) and lift shape Coalesce's path, tuned with stagger (s per scene unit from the origin) so a cycle
// settles in about 1.6 s (U1); follow is Coalesce's path gains, held from a path's start until the settle;
// settleEps is D40's settle (scene units and radians); pausedClickMs is the paused click guard.
export const DIRECTOR = Object.freeze({
  pathDur: 1.0, stagger: 0.06, lift: 0.25, fadeDur: 0.8, follow: Object.freeze({ k: 70, zeta: 0.8 }),
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
    const onQuilt = hit.part === 'block' || hit.part === 'sashing';
    if (this.current === 'quilt' && onQuilt) this.begin('unstitching', hit.point);
    else if (this.current === 'tiles' && hit.part === 'none') this.begin('restitching', hit.point);
    else return false;
    return this.snapIfPaused(now);
  }

  setPaused(paused, now) {
    this.paused = paused;
    this.snapIfPaused(now);
  }

  // A transition jumps to its end: snap, then enter its settled mode. False when none is running.
  finish() {
    if (!this.leg) return false;
    const { settle } = this.leg;
    this.snap();
    this.enter(settle);
    return true;
  }

  // One frame of h seconds (#7's capped dt). D40: the settle is checked before stepping, so a settled transition
  // snaps and enters its mode at most once per call.
  advance(h) {
    if (this.leg) {
      const error = this.settleError();
      if (error <= DIRECTOR.settleEps) {
        this.lastSettleError = error;
        this.finish();
        return;
      }
    }
    this.time += h;
    if (this.leg) this.follow();
    this.springs.advance(h);
  }

  // --- Internals. ---

  // Starts a transition from the current pose. From a settled mode each block's path waits stagger x its distance
  // from origin (Coalesce's burst); a reversal starts every path now and keeps the springs' velocities.
  begin(next, origin) {
    const reversal = this.leg !== null;
    const end = LEGS[next];
    const { pathDur, stagger, fadeDur } = DIRECTOR;
    const paths = this.isTile.map((tile, i) => {
      if (!tile) return null;
      const p = this.springs.p[i].slice();
      const wait = reversal ? 0 : stagger * Math.hypot(p[0] - origin[0], p[1] - origin[1]);
      return { t0: this.time + wait, from: { p, s: this.s[i] },
        to: { p: this.endPoses(end.s)[i].position, s: end.s } };
    });
    const fade = { t0: this.time, dur: fadeDur, from: this.g, to: end.g };
    const ends = Math.max(fade.t0 + fadeDur, ...paths.map((q) => (q ? q.t0 + pathDur : 0)));
    this.leg = { ...end, paths, fade, ends };
    this.enter(next);
  }

  // Each path's spring target at this.time: from -> to along the eased path, lifted on Coalesce's arc
  // (coalesce/public/js/motion.js pathPoint). The follower gains hold from the path's start until the settle:
  // switching to the home gains (k 38, zeta 0.5) at the path's end, as Coalesce does, adds about 1.1 s before 1e-3.
  follow() {
    const { pathDur, lift, follow } = DIRECTOR;
    const target = [0, 0, 0];
    this.leg.paths.forEach((path, i) => {
      if (!path) return;
      const e = ease.inout(progress(this.time, path.t0, pathDur));
      for (let d = 0; d < 3; d += 1) target[d] = path.from.p[d] + (path.to.p[d] - path.from.p[d]) * e;
      // The arc scales with the flip the path has left, so a block turned back before it moved does not lift.
      target[2] += lift * Math.abs(path.to.s - path.from.s) * Math.sin(Math.PI * e);
      this.springs.setTarget(i, target);
      this.springs.setGains(i, this.time >= path.t0 ? follow : null);
      this.s[i] = path.from.s + (path.to.s - path.from.s) * e;
    });
    const { fade } = this.leg;
    this.g = fade.from + (fade.to - fade.from) * ease.inout(progress(this.time, fade.t0, fade.dur));
  }

  // The largest distance from the endpoint, in position (per axis) or rotation, once every path and the fade have
  // run their course; Infinity before then.
  settleError() {
    if (this.time < this.leg.ends) return Infinity;
    let worst = 0;
    this.leg.paths.forEach((path, i) => {
      if (!path) return;
      const p = this.springs.p[i];
      for (let d = 0; d < 3; d += 1) worst = Math.max(worst, Math.abs(p[d] - path.to.p[d]));
      const pose = this.pose(i);
      const end = this.endPoses(path.to.s)[i];
      worst = Math.max(worst, Math.abs(pose.rotY - end.rotY), Math.abs(pose.rotZ - end.rotZ));
    });
    return worst;
  }

  // The end poses a flip of s lands on: the tiles at 1, the quilt at 0.
  endPoses(s) {
    return s ? this.tile : this.quilt;
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
      this.springs.setTarget(i, this.endPoses(s)[i].position);
      this.springs.setGains(i, null);
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
