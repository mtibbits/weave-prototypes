// Decides whether the live 3D scene may run on this device, and watches its frame times once it does.

export function readEnvironment(win = window) {
  const media = (query) => typeof win.matchMedia === 'function' && win.matchMedia(query).matches;
  let webgl = false;
  try {
    const canvas = win.document.createElement('canvas');
    const gl = canvas.getContext('webgl2') || canvas.getContext('webgl');
    webgl = Boolean(gl);
    const lose = gl && gl.getExtension('WEBGL_lose_context');
    if (lose) lose.loseContext();
  } catch (err) {
    webgl = false;
  }
  const connection = win.navigator && win.navigator.connection;
  return {
    webgl,
    reducedMotion: media('(prefers-reduced-motion: reduce)'),
    canHover: media('(hover: hover) and (pointer: fine)'),
    saveData: Boolean(connection && connection.saveData),
  };
}

export function decideMode(env) {
  if (!env.webgl) return { live: false, reason: 'no-webgl' };
  if (env.reducedMotion) return { live: false, reason: 'reduced-motion' };
  if (!env.canHover) return { live: false, reason: 'no-hover' };
  if (env.saveData) return { live: false, reason: 'save-data' };
  return { live: true, reason: 'ok' };
}

export class FrameWatchdog {
  constructor({ windowMs = 2000, limitMs = 45, minFrames = 3 } = {}) {
    this.windowMs = windowMs;
    this.limitMs = limitMs;
    this.minFrames = minFrames;
    this.samples = [];
    this.elapsed = 0;
    this.verdict = 'pending';
  }

  add(frameMs) {
    if (this.verdict !== 'pending') return this.verdict;
    this.samples.push(frameMs);
    this.elapsed += frameMs;
    if (this.elapsed >= this.windowMs && this.samples.length >= this.minFrames) {
      const sorted = [...this.samples].sort((a, b) => a - b);
      const median = sorted[Math.floor(sorted.length / 2)];
      this.verdict = median > this.limitMs ? 'too-slow' : 'ok';
    }
    return this.verdict;
  }
}
