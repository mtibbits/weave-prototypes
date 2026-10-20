// WEAVE's motion: Coalesce's fixed-step springs and the quilt's ambient sway and pointer tilt. Pure: no Three,
// no DOM, and no clock of its own (D8): time arrives only as the dt the caller measured from rAF timestamps.
import { LAYOUT, moveItem, nearestSlot } from './layout.js';
import { rngFor } from './random.js';

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
// pathDur (s) and lift shape Coalesce's path, tuned with stagger (s per scene unit from the origin) so a
// transition (one leg) settles in about 1.6 s (U1); follow is Coalesce's path gains, held from a path's start until
// the settle; settleEps is D40's settle (scene units and radians); pausedClickMs is the paused click guard.
export const DIRECTOR = Object.freeze({
  pathDur: 1.0, stagger: 0.06, lift: 0.25, fadeDur: 0.8, follow: Object.freeze({ k: 70, zeta: 0.8 }),
  settleEps: 1e-3, pausedClickMs: 400,
});

// #9's drag. A press has moved once Math.hypot(e.clientX - press.x, e.clientY - press.y) > thresholdPx (CSS px,
// from the pointerdown point). lift: the dragged tile's z in quilt space, so it draws over its neighbours (below
// the 0.25 arc, inside DEFAULT_BOUNDS' 0.3 margin).
export const DRAG = Object.freeze({ thresholdPx: 6, lift: 0.05 });

// #10's intro: each tile block flies in from a seeded scatter point (offset from its quilt pose, up to `scatter`
// across and `rise` towards the camera) after a seeded wait of up to `spread` s, along a pathDur path, while the fade
// runs 0 -> 1 over fadeDur. It settles (D40) in about 2.4 s at 20-60 fps (U1).
export const INTRO = Object.freeze({ pathDur: 1.2, spread: 0.6, fadeDur: 0.8, scatter: 1.2, rise: Object.freeze([0.6, 1.2]) });
// A block's decor (stitches, pins) is dressed once its flight's eased progress reaches DRESS_AT, in the intro and
// in a sew-back, so the sew/drop ends before the D40 settle; the settle's finishDecor() is the backstop.
export const DRESS_AT = 0.7;

// Seeded from rngFor(id, 'intro'), in this draw order: dx, dy in [-scatter, scatter], dz in rise, wait in [0, spread].
export function introScatter(id) {
  const rng = rngFor(id, 'intro');
  const { scatter, rise, spread } = INTRO;
  const dx = (rng() * 2 - 1) * scatter;
  const dy = (rng() * 2 - 1) * scatter;
  const dz = rise[0] + rng() * (rise[1] - rise[0]);
  return { offset: [dx, dy, dz], wait: rng() * spread };
}

// #16's sew-in: each new drawn block, one after another `stagger` s apart, runs its steps back to back in SEW_STEPS
// order (the pins pop, the block squares up, the face swaps at a puff, a needle stitches the perimeter, it glows). A
// schedule longer than `limit` s is scaled as a whole, so every window shrinks together and the needles never crowd.
export const SEW = Object.freeze({
  stagger: 0.6, steps: Object.freeze({ pins: 0.3, square: 0.4, puff: 0.25, needle: 1.2, glow: 0.4 }), limit: 5,
});
export const SEW_STEPS = Object.freeze(['pins', 'square', 'puff', 'needle', 'glow']);

// n blocks' sew-in in seconds from the sewing entry: { scale, total, blocks: [{ start, pins: [t0, t1], ... }] }. Pure.
export function sewSchedule(n) {
  if (typeof n !== 'number' || !Number.isInteger(n) || n < 0) {
    throw new RangeError('WEAVE: sewSchedule needs a whole number of blocks.');
  }
  if (n === 0) return { scale: 1, total: 0, blocks: [] };
  const each = SEW_STEPS.reduce((sum, name) => sum + SEW.steps[name], 0);
  const raw = SEW.stagger * (n - 1) + each;
  const scale = raw > SEW.limit ? SEW.limit / raw : 1;
  const blocks = Array.from({ length: n }, (_, k) => {
    const block = { start: k * SEW.stagger * scale };
    let at = block.start;
    for (const name of SEW_STEPS) {
      const end = at + SEW.steps[name] * scale;
      block[name] = [at, end];
      at = end;
    }
    return block;
  });
  return { scale, total: raw * scale, blocks };
}

// Where each transition goes: the settled mode it ends in, and the flip (s) and fade (g) it ends at.
const LEGS = Object.freeze({
  unstitching: Object.freeze({ settle: 'tiles', s: 1, g: 0 }),
  restitching: Object.freeze({ settle: 'quilt', s: 0, g: 1 }),
});

// The blocks' poses between the quilt (s = 0) and the tiles (s = 1), the fade of everything that is not a tile,
// and the mode. Pure like the rest of this module: time arrives only through advance(h), and `now` (an event's
// timeStamp, D8) only for the paused click guard. onEnter(mode, from) runs from enter(), the one writer of mode.
export class Director {
  // quiltPose(i, slot) and tilePose(i, slot) are block i's poses in a slot; every block starts in slot i (#9).
  // introFrom(i) (#10, optional) is block i's intro flight, { offset, wait }; null, or a filler, only fades in.
  constructor({ count, quiltPose, tilePose, isTile, onEnter, introFrom = null }) {
    this.count = count;
    this.quiltPose = quiltPose;
    this.tilePose = tilePose;
    this.slots = [];
    this.blocks = [];
    this.quilt = [];
    this.tile = [];
    for (let i = 0; i < count; i += 1) this.place(i, i);
    this.drag = null;
    this.isTile = Array.from({ length: count }, (_, i) => isTile(i));
    this.tileCount = this.isTile.filter(Boolean).length;
    this.onEnter = onEnter;
    this.introFrom = introFrom;
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

  // --- The drag (#9). ---

  // Block i's current slot, and the block in slot k.
  slotOf(i) { return this.slots[i]; }

  blockAt(k) { return this.blocks[k]; }

  get dragging() { return this.drag !== null; }

  // Picks block i up at `point` (the press in quilt-group xy): only a tile, only in settled tiles, one at a time.
  // The block lifts to DRAG.lift and keeps its offset from the pointer.
  grab(i, point) {
    if (this.current !== 'tiles' || this.leg || !this.isTile[i] || this.drag) return false;
    const [x, y] = this.springs.p[i];
    const from = this.slots[i];
    this.drag = { i, offset: [x - point[0], y - point[1]], start: this.blocks.slice(), from, to: from };
    this.hold(i, x, y);
    return true;
  }

  // The dragged block follows `point`; the tiles reflow by move-and-shift from the drag's start order, clamped to
  // the last tile slot (fillSlots puts the tiles first, so the fillers never move). Returns [[block, slot], ...]
  // for the blocks whose slot changed in this call.
  dragTo(point) {
    if (!this.drag) return [];
    const { i, offset, start, from } = this.drag;
    const x = point[0] + offset[0];
    const y = point[1] + offset[1];
    this.hold(i, x, y);
    const to = Math.min(nearestSlot(x, y, 'tiles'), this.tileCount - 1);
    if (to === this.drag.to) return [];
    this.drag.to = to;
    const moves = [];
    moveItem(start, from, to).forEach((b, k) => {
      if (this.slots[b] === k) return;
      this.place(b, k);
      if (b !== i) this.springs.setTarget(b, this.tile[b].position);
      moves.push([b, k]);
    });
    if (this.paused) this.springs.snap();
    return moves;
  }

  // Lets the dragged block go to its current slot: the home spring carries it in, or at once while paused.
  drop() {
    if (!this.drag) return false;
    const { i } = this.drag;
    this.springs.setTarget(i, this.tile[i].position);
    this.drag = null;
    if (this.paused) this.springs.snap();
    return true;
  }

  // Block i at (x, y, DRAG.lift), at rest, with its target there too.
  hold(i, x, y) {
    const at = [x, y, DRAG.lift];
    this.springs.p[i] = at.slice();
    this.springs.setTarget(i, at);
    this.springs.v[i].fill(0);
  }

  // Block b takes slot k: the slot map both ways, and its quilt and tile poses re-derived for k.
  place(b, k) {
    this.slots[b] = k;
    this.blocks[k] = b;
    this.quilt[b] = this.quiltPose(b, k);
    this.tile[b] = this.tilePose(b, k);
  }

  get fade() { return this.g; }

  get ambient() { return this.g; }

  enter(next) {
    const from = this.current;
    this.current = next;
    this.onEnter(next, from);
  }

  // The first state: 'quilt' at rest, or (#10) 'intro', a leg like begin()'s that settles into the quilt: each tile
  // block is seated at its quilt pose plus its introFrom offset, at rest, and flies home; the fade starts at 0.
  start(first = 'quilt') {
    if (first === 'intro') {
      const { pathDur, fadeDur } = INTRO;
      const paths = this.isTile.map((tile, i) => {
        const from = tile && this.introFrom ? this.introFrom(i) : null;
        if (!from) return null;
        const home = this.quilt[i].position;
        const p = home.map((v, d) => v + from.offset[d]);
        this.springs.p[i] = p.slice();
        this.springs.setTarget(i, p);
        this.springs.v[i].fill(0);
        return { t0: this.time + from.wait, from: { p, s: 0 }, to: { p: home.slice(), s: 0 } };
      });
      const fade = { t0: this.time, dur: fadeDur, from: 0, to: 1 };
      const ends = Math.max(fade.t0 + fadeDur, ...paths.map((q) => (q ? q.t0 + pathDur : 0)));
      this.g = 0;
      this.leg = { settle: 'quilt', s: 0, g: 1, pathDur, paths, fade, ends };
    }
    this.enter(first);
  }

  // Block i's eased path progress in the running leg, 0 ... 1; 1 with no leg or no path.
  progress(i) {
    const path = this.leg ? this.leg.paths[i] : null;
    if (!path) return 1;
    return ease.inout(progress(this.time, path.t0, this.leg.pathDur));
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
    if (this.current === 'intro') return this.cutIntro(now, origin);
    const next = { quilt: 'unstitching', tiles: 'restitching', unstitching: 'restitching', restitching: 'unstitching' };
    if (!(this.current in next)) return false;
    this.begin(next[this.current], origin);
    return this.snapIfPaused(now);
  }

  // hit is what scene.js's pick returns; true when the click acted.
  click(hit, now) {
    if (this.paused && now - this.lastSnapAt < DIRECTOR.pausedClickMs) return false;
    const onQuilt = hit.part === 'block' || hit.part === 'sashing';
    if (this.current === 'intro' && onQuilt) return this.cutIntro(now, hit.point);
    if (this.current === 'quilt' && onQuilt) this.begin('unstitching', hit.point);
    else if (this.current === 'tiles' && hit.part === 'none') this.begin('restitching', hit.point);
    else return false;
    return this.snapIfPaused(now);
  }

  // Pausing outside a transition lands every spring on its target too (a tile just dropped, or reflowing mid-drag).
  setPaused(paused, now) {
    this.paused = paused;
    if (paused && !this.leg) this.springs.snap();
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

  // Unstitch during the intro (#10): the intro finishes first (entering quilt), then unstitches, unless a weave:mode
  // handler on that quilt entry has already moved on (Issue-8's re-entrancy lesson).
  cutIntro(now, origin) {
    this.finish();
    if (this.current === 'quilt') this.begin('unstitching', origin);
    return this.snapIfPaused(now);
  }

  // Starts a transition from the current pose. From a settled mode each block's path waits stagger x its distance
  // from origin (Coalesce's burst); a reversal starts every path now and keeps the springs' velocities.
  // A toggle or click mid-drag drops the tile first (#9), so the transition starts from its current slot.
  begin(next, origin) {
    this.drop();
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
    this.leg = { ...end, pathDur, paths, fade, ends };
    this.enter(next);
  }

  // Each path's spring target at this.time: from -> to along the eased path, lifted on Coalesce's arc
  // (coalesce/public/js/motion.js pathPoint). The follower gains hold from the path's start until the settle:
  // switching to the home gains (k 38, zeta 0.5) at the path's end, as Coalesce does, adds about 1.1 s before 1e-3.
  follow() {
    const { lift, follow } = DIRECTOR;
    const { pathDur } = this.leg;
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
