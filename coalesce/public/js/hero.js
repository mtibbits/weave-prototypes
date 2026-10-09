// Mounts the live 3D hero, or leaves the still image in place when 3D shouldn't or can't run.
// Three.js and the 3D assets download only after the device qualifies.
import { readEnvironment, decideMode, FrameWatchdog } from './eligibility.js';

const MAX_PIXEL_RATIO = 1.75;

export async function mountHero(stage, options = {}) {
  if (!stage) return { state: 'still', reason: 'no-stage' };
  const { variant = 'home', assetsBase = 'assets/', watchdog = true, watchdogLimitMs = 45 } = options;
  const setState = (state, reason) => {
    stage.dataset.heroState = state;
    stage.dataset.heroReason = reason;
    return { state, reason };
  };
  const decision = decideMode(readEnvironment(window));
  if (!decision.live) return setState('still', decision.reason);
  setState('still', 'loading');
  let modules;
  try {
    const [crowd, motion] = await Promise.all([import('./crowd.js'), import('./motion.js')]);
    modules = { crowd, motion, assets: await crowd.loadAssets(assetsBase) };
  } catch (err) {
    console.warn('Coalesce: the 3D figure could not load, so the still image stays.', err);
    return setState('still', 'load-failed');
  }
  return startLive(stage, modules, { variant, watchdog, watchdogLimitMs, setState });
}

function startLive(stage, { crowd, motion, assets }, { variant, watchdog, watchdogLimitMs, setState }) {
  const canvas = document.createElement('canvas');
  canvas.setAttribute('aria-hidden', 'true');
  let view;
  let lens = null;
  try {
    view = new crowd.CrowdView(canvas, assets);
    if (variant === 'help') lens = new crowd.MagnifierView(view, assets);
  } catch (err) {
    console.warn('Coalesce: WebGL setup failed, so the still image stays.', err);
    return setState('still', 'webgl-failed');
  }
  const { layout } = assets;
  const sim = new motion.CrowdSim(layout, { variant });
  const aim = lens ? new motion.MagnifierSim(sim, layout.magnifier.restAim) : null;
  const pauseButton = stage.parentElement.querySelector('[data-pause]');
  const dog = watchdog ? new FrameWatchdog({ limitMs: watchdogLimitMs }) : null;
  const tilt = { x: 0, y: 0, targetX: 0, targetY: 0 };
  let paused = false;
  let onScreen = true;
  let stopped = false;
  let rafId = 0;
  let last = 0;
  let frames = 0;

  stage.append(canvas);
  stage.classList.add('is-live');
  sim.intro();

  const resize = () => {
    const width = stage.clientWidth;
    const height = stage.clientHeight;
    if (!width || !height) return;
    view.resize(width, height, Math.min(window.devicePixelRatio || 1, MAX_PIXEL_RATIO));
    // Resizing clears the canvas; when no frame is coming (paused or off-screen), redraw the current pose.
    if (!rafId && !stopped) draw();
  };
  const sizeObserver = new ResizeObserver(resize);
  sizeObserver.observe(stage);
  resize();

  function frame(now) {
    rafId = 0;
    if (stopped) return;
    const dtMs = last ? Math.min(100, now - last) : 1000 / 60;
    last = now;
    if (dog && dog.add(dtMs) === 'too-slow') {
      stop('too-slow');
      return;
    }
    const dt = dtMs / 1000;
    sim.advance(dt);
    if (aim) aim.advance(dt);
    const follow = Math.min(1, dt * 3);
    tilt.x += (tilt.targetX - tilt.x) * follow;
    tilt.y += (tilt.targetY - tilt.y) * follow;
    view.setTilt(tilt.x, tilt.y);
    draw();
    frames += 1;
    stage.dataset.heroFrames = String(frames);
    schedule();
  }

  function draw() {
    view.sync(sim.tokens, layout.tokenScale);
    if (lens) {
      lens.update(aim.aimPoint());
      lens.render();
    } else {
      view.render();
    }
  }

  function schedule() {
    if (!rafId && !stopped && !paused && onScreen && !document.hidden) rafId = requestAnimationFrame(frame);
  }

  function unschedule() {
    if (rafId) cancelAnimationFrame(rafId);
    rafId = 0;
    last = 0;
  }

  const toNdc = (event) => {
    const r = canvas.getBoundingClientRect();
    return [((event.clientX - r.left) / r.width) * 2 - 1, 1 - ((event.clientY - r.top) / r.height) * 2];
  };
  canvas.addEventListener('pointermove', (event) => {
    const [x, y] = toNdc(event);
    tilt.targetX = -y * 0.1;
    tilt.targetY = x * 0.24;
    sim.setPointer(view.pointerToFigure(x, y), true);
  });
  canvas.addEventListener('pointerleave', () => {
    tilt.targetX = 0;
    tilt.targetY = 0;
    sim.setPointer(null, false);
  });
  canvas.addEventListener('click', (event) => {
    if (paused) return;
    const [x, y] = toNdc(event);
    const point = view.pointerToFigure(x, y);
    if (point) sim.burst(point);
  });
  canvas.addEventListener('webglcontextlost', (event) => {
    event.preventDefault();
    stop('context-lost');
  });

  const onPause = () => {
    paused = !paused;
    pauseButton.setAttribute('aria-pressed', String(paused));
    pauseButton.textContent = paused ? 'Play motion' : 'Pause motion';
    if (paused) unschedule();
    else schedule();
  };
  if (pauseButton) {
    pauseButton.hidden = false;
    pauseButton.addEventListener('click', onPause);
  }

  const visibility = new IntersectionObserver((entries) => {
    onScreen = entries[entries.length - 1].isIntersecting;
    if (onScreen) schedule();
    else unschedule();
  });
  visibility.observe(stage);
  const onVisibilityChange = () => {
    if (document.hidden) unschedule();
    else schedule();
  };
  document.addEventListener('visibilitychange', onVisibilityChange);

  function stop(reason) {
    if (stopped) return;
    stopped = true;
    unschedule();
    sizeObserver.disconnect();
    visibility.disconnect();
    document.removeEventListener('visibilitychange', onVisibilityChange);
    if (pauseButton) {
      pauseButton.hidden = true;
      pauseButton.removeEventListener('click', onPause);
    }
    canvas.remove();
    stage.classList.remove('is-live');
    if (lens) lens.dispose();
    view.dispose();
    setState('still', reason);
  }

  stage.__coalesce = { sim, aim, view, stop };
  setState('live', 'ok');
  schedule();
  return { state: 'live', reason: 'ok', stop };
}
