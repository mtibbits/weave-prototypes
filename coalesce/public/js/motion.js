// Crowd motion for the Coalesce hero: pure data and maths, no Three.js.
// Coordinates are layout.json's web space: x right, y up, z toward the viewer.

export const STEP = 1 / 120;
export const MAX_DT = 0.05;
export const HOVER = { radius: 1.2, push: 0.8, lift: 0.9 };
const TOKEN_MIDDLE = 0.14; // height of a person's middle above their base at tokenScale 0.4
const LENS_FLOOR = 1.0; // the lens never aims lower than this above the bottom row, so its handle stays in frame

export function hexToLinear(hex) {
  const h = hex.replace('#', '');
  return [0, 2, 4].map((i) => {
    const c = parseInt(h.slice(i, i + 2), 16) / 255;
    return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  });
}

export const COLORS = {
  teal: hexToLinear('#1D5E5B'),
  terra: hexToLinear('#C4623A'),
  paper: hexToLinear('#F4F0E8'),
};

export function mulberry32(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export const ease = {
  out: (u) => 1 - (1 - u) ** 3,
  inout: (u) => (u < 0.5 ? 4 * u * u * u : 1 - (-2 * u + 2) ** 3 / 2),
};

const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));

export function pathPoint(path, now, out) {
  const u = clamp((now - path.t0) / path.dur, 0, 1);
  const e = ease[path.ease](u);
  const bulge = Math.sin(Math.PI * e);
  for (let i = 0; i < 3; i++) {
    out[i] = path.from[i] + (path.to[i] - path.from[i]) * e + (path.arc ? path.arc[i] * bulge : 0);
  }
  return u;
}

export function hoverOffset(home, ptr, amount, out, opts = HOVER) {
  out[0] = 0;
  out[1] = 0;
  out[2] = 0;
  if (amount < 0.001) return out;
  const dx = home[0] - ptr[0];
  const dy = home[1] - ptr[1];
  const d = Math.hypot(dx, dy);
  if (d >= opts.radius) return out;
  let f = 1 - d / opts.radius;
  f = f * f * (3 - 2 * f) * amount;
  const inv = d > 1e-4 ? 1 / d : 0;
  out[0] = dx * inv * opts.push * f;
  out[1] = dy * inv * opts.push * f;
  out[2] = opts.lift * f;
  return out;
}

function makeToken(home, color, mode) {
  const spare = mode === 'spare';
  return {
    home, mode, path: null,
    p: home ? home.slice() : [0, -50, 0], v: [0, 0, 0],
    s: spare ? 0 : 1, sT: spare ? 0 : 1,
    col: color.slice(), colT: color.slice(), colRate: 0.9,
    rx: 0, rz: 0, assimAt: 0, busyUntil: 0,
  };
}

function randArc(rand, size) {
  return [(rand() - 0.5) * size, (rand() - 0.5) * size, rand() * size];
}

function updateTokens(tokens, now, dt) {
  for (const t of tokens) {
    const path = t.path;
    if (path) {
      const u = clamp((now - path.t0) / path.dur, 0, 1);
      if (path.hideUntilStart) t.sT = now < path.t0 ? 0 : 1;
      if (t.mode === 'leave') t.sT = 1 - u;
      if (u >= 1) {
        if (path.next) {
          t.path = { ...path.next, from: t.p.slice(), t0: now };
        } else {
          t.path = null;
          t.mode = path.endMode;
          if (path.onDone) path.onDone(t, now);
        }
      }
    }
    if (t.assimAt && now >= t.assimAt) {
      t.colT = COLORS.teal.slice();
      t.assimAt = 0;
    }
    t.s += (t.sT - t.s) * Math.min(1, dt * 5);
    const rate = Math.min(1, dt * (t.mode === 'leave' ? 1.6 : t.colRate));
    for (let i = 0; i < 3; i++) t.col[i] += (t.colT[i] - t.col[i]) * rate;
  }
}

const target = [0, 0, 0];
const offset = [0, 0, 0];

function stepPhysics(tokens, now, h, hover) {
  for (const t of tokens) {
    let k = 38;
    let zeta = 0.5;
    if (t.path) {
      pathPoint(t.path, now, target);
      k = 70;
      zeta = 0.8;
    } else if (t.mode === 'home') {
      if (hover.enabled) hoverOffset(t.home, hover.ptr, hover.amount, offset);
      else offset.fill(0);
      for (let i = 0; i < 3; i++) target[i] = t.home[i] + offset[i];
    } else {
      for (let i = 0; i < 3; i++) target[i] = t.p[i];
    }
    const c = 2 * Math.sqrt(k) * zeta;
    for (let i = 0; i < 3; i++) {
      t.v[i] += (k * (target[i] - t.p[i]) - c * t.v[i]) * h;
      t.p[i] += t.v[i] * h;
    }
  }
}

function updateTilt(t, dt) {
  let rz = clamp(-t.v[0] * 0.12, -0.7, 0.7);
  let rx = clamp(t.v[2] * 0.1 - t.v[1] * 0.05, -0.7, 0.7);
  if (t.mode === 'home' && t.home) {
    rz += clamp(-(t.p[0] - t.home[0]) * 0.45, -0.6, 0.6);
    rx += clamp((t.p[2] - t.home[2]) * 0.35, -0.6, 0.6);
  }
  const a = Math.min(1, dt * 10);
  t.rz += (rz - t.rz) * a;
  t.rx += (rx - t.rx) * a;
}

export class CrowdSim {
  constructor(layout, { variant = 'home', seed = 7 } = {}) {
    this.variant = variant;
    this.rand = mulberry32(seed);
    this.center = layout.figureCenter.slice();
    const accents = variant === 'home';
    this.tokens = layout.people.map((home, i) =>
      makeToken(home.slice(), accents && layout.accent[i] ? COLORS.terra : COLORS.teal, 'home'));
    if (variant === 'home') {
      for (let k = 0; k < 3; k++) this.tokens.push(makeToken(null, COLORS.teal, 'spare'));
    }
    this.turnovers = variant === 'home';
    this.hover = { enabled: variant === 'home', ptr: [0, 99, 0], amount: 0 };
    this.pointer = { inside: false, target: [0, 99, 0] };
    this.clock = 0;
    this.acc = 0;
    this.quietUntil = 0;
    this.nextTurn = 0;
    this.focusIndex = -1;
  }

  setPointer(point, inside) {
    const entering = inside && !this.pointer.inside;
    this.pointer.inside = Boolean(inside && point);
    if (point) {
      this.pointer.target = point.slice();
      if (entering) this.hover.ptr = point.slice();
    }
  }

  // Everyone flies in from a loose crowd around the figure (page load).
  intro() {
    const [cx, cy, cz] = this.center;
    for (const t of this.tokens) {
      if (!t.home) continue;
      const angle = this.rand() * Math.PI * 2;
      const r = 6 + this.rand() * 4;
      const from = [cx + Math.cos(angle) * r, cy + Math.sin(angle) * r * 0.7, cz - 2 + this.rand() * 5];
      t.p = from.slice();
      t.v = [0, 0, 0];
      t.s = 0;
      t.sT = 0;
      t.mode = 'intro';
      t.path = {
        from, to: t.home.slice(), t0: this.clock + 0.1 + this.rand() ** 0.7 * 1.3, dur: 1.7 + this.rand() * 0.8,
        ease: 'out', arc: randArc(this.rand, 1.2), hideUntilStart: true, endMode: 'home',
      };
    }
    this.quietUntil = this.clock + 3.6;
  }

  // Click: people burst outward from the click point, then re-form.
  burst(origin) {
    for (const t of this.tokens) {
      if (t.mode !== 'home') continue;
      let dx = t.home[0] - origin[0];
      let dy = t.home[1] - origin[1];
      let d = Math.hypot(dx, dy);
      if (d < 1e-3) {
        dx = this.rand() - 0.5;
        dy = this.rand() - 0.5;
        d = Math.hypot(dx, dy) || 1;
      }
      const k = (1.6 + this.rand() * 2.4) / d;
      const out = [
        t.p[0] + dx * k + (this.rand() - 0.5) * 1.4,
        t.p[1] + dy * k + (this.rand() - 0.5) * 1.4,
        t.p[2] + 1 + this.rand() * 2.4,
      ];
      t.mode = 'burst';
      t.path = {
        from: t.p.slice(), to: out, t0: this.clock + d * 0.035, dur: 0.55, ease: 'out', arc: null,
        next: { to: t.home.slice(), dur: 1.5 + this.rand() * 0.9, ease: 'inout', arc: randArc(this.rand, 0.6), endMode: 'home' },
      };
    }
    this.quietUntil = Math.max(this.quietUntil, this.clock + 3.2);
  }

  // Onboarding / offboarding: one person drifts out and fades; a newcomer arrives from the right and takes the spot.
  turnover() {
    const now = this.clock;
    const spare = this.tokens.find((t) => t.mode === 'spare');
    const candidates = this.tokens.filter((t, i) =>
      t.mode === 'home' && !t.assimAt && now > t.busyUntil && i !== this.focusIndex);
    if (!spare || candidates.length === 0) return false;
    const leaver = candidates[Math.floor(this.rand() * candidates.length)];
    const slot = leaver.home.slice();
    const [cx, cy, cz] = this.center;
    let ox = slot[0] - cx;
    let oy = slot[1] - cy;
    const length = Math.hypot(ox, oy);
    if (length < 1e-4) {
      ox = -1;
      oy = 0;
    } else {
      ox /= length;
      oy /= length;
    }
    leaver.home = null;
    leaver.mode = 'leave';
    leaver.colT = COLORS.paper.slice();
    leaver.path = {
      from: slot.slice(), to: [slot[0] + ox * 3.4, slot[1] + oy * 1.4 - 0.3, slot[2] + 1.8],
      t0: now, dur: 2.6, ease: 'inout', arc: [0, 0.5, 0.4], endMode: 'spare',
      onDone: (t) => {
        t.s = 0;
        t.sT = 0;
      },
    };
    const spawn = [cx + 5.4, cy - 1.4 + this.rand() * 2.4, cz + 0.8];
    spare.p = spawn.slice();
    spare.v = [0, 0, 0];
    spare.s = 0;
    spare.sT = 1;
    spare.col = COLORS.terra.slice();
    spare.colT = COLORS.terra.slice();
    spare.colRate = 0.9;
    spare.mode = 'arrive';
    spare.path = {
      from: spawn, to: slot, t0: now + 0.8, dur: 3, ease: 'inout', arc: [0, 0.7, 1.6], endMode: 'home',
      onDone: (t, when) => {
        t.home = slot;
        t.assimAt = when + 2.4;
        t.busyUntil = when + 8;
      },
    };
    return true;
  }

  setFocus(index) {
    if (index === this.focusIndex) return;
    const previous = this.tokens[this.focusIndex];
    if (previous) {
      previous.colT = COLORS.teal.slice();
      previous.colRate = 6;
    }
    this.focusIndex = index;
    const next = this.tokens[index];
    if (next) {
      next.colT = COLORS.terra.slice();
      next.colRate = 6;
    }
  }

  nearest(x, y) {
    let best = -1;
    let bestDistance = Infinity;
    this.tokens.forEach((t, i) => {
      if (t.mode !== 'home' || !t.home) return;
      const d = (t.home[0] - x) ** 2 + (t.home[1] + TOKEN_MIDDLE - y) ** 2;
      if (d < bestDistance) {
        bestDistance = d;
        best = i;
      }
    });
    return best;
  }

  advance(dt) {
    const h = Math.min(MAX_DT, Math.max(0, dt));
    this.clock += h;
    const now = this.clock;
    this.hover.amount += ((this.pointer.inside ? 1 : 0) - this.hover.amount) * Math.min(1, h * 5);
    const follow = Math.min(1, h * 16);
    for (let i = 0; i < 3; i++) this.hover.ptr[i] += (this.pointer.target[i] - this.hover.ptr[i]) * follow;
    if (this.turnovers && now > this.quietUntil && now > this.nextTurn) {
      this.turnover();
      this.nextTurn = now + 3.2 + this.rand() * 1.6;
    }
    updateTokens(this.tokens, now, h);
    this.acc += h;
    while (this.acc >= STEP) {
      stepPhysics(this.tokens, now, STEP, this.hover);
      this.acc -= STEP;
    }
    for (const t of this.tokens) updateTilt(t, h);
  }
}

// Help page: where the magnifying glass points, and which person it picks out.
export class MagnifierSim {
  constructor(sim, restAim, { seed = 11 } = {}) {
    this.sim = sim;
    this.rand = mulberry32(seed);
    this.pos = restAim.slice(0, 2);
    this.target = restAim.slice(0, 2);
    this.nextDrift = 3;
    this.bounds = { minX: Infinity, maxX: -Infinity, minY: Infinity, maxY: -Infinity };
    for (const t of sim.tokens) {
      if (!t.home) continue;
      this.bounds.minX = Math.min(this.bounds.minX, t.home[0]);
      this.bounds.maxX = Math.max(this.bounds.maxX, t.home[0]);
      this.bounds.minY = Math.min(this.bounds.minY, t.home[1]);
      this.bounds.maxY = Math.max(this.bounds.maxY, t.home[1] + 2 * TOKEN_MIDDLE);
    }
    this.bounds.minY += LENS_FLOOR;
  }

  advance(dt) {
    const h = Math.min(MAX_DT, Math.max(0, dt));
    const { pointer, clock } = this.sim;
    if (pointer.inside) {
      const b = this.bounds;
      this.target = [clamp(pointer.target[0], b.minX, b.maxX), clamp(pointer.target[1], b.minY, b.maxY)];
      this.nextDrift = clock + 1.5;
    } else if (clock >= this.nextDrift) {
      const homes = this.sim.tokens.filter((t) => t.mode === 'home');
      const pick = homes[Math.floor(this.rand() * homes.length)];
      if (pick) this.target = [pick.home[0], Math.max(this.bounds.minY, pick.home[1] + TOKEN_MIDDLE)];
      this.nextDrift = clock + 3;
    }
    const follow = Math.min(1, h * (pointer.inside ? 8 : 1.6));
    this.pos[0] += (this.target[0] - this.pos[0]) * follow;
    this.pos[1] += (this.target[1] - this.pos[1]) * follow;
    this.sim.setFocus(this.sim.nearest(this.pos[0], this.pos[1]));
  }

  aimPoint() {
    const focus = this.sim.tokens[this.sim.focusIndex];
    const z = focus && focus.home ? focus.home[2] + 0.1 : this.sim.center[2] + 1;
    return [this.pos[0], this.pos[1], z];
  }
}
