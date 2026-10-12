// WEAVE's boot module: the panel lists first, then the hero. The load-time decision picks the still or the live
// quilt; going live is a port of Coalesce's startLive (coalesce/public/js/hero.js).
import { cleanPanels } from './catalog.js';
import { fillSlots, readHooks, renderPanels, setHeroState, setPaused, setStageLabel, showLiveControls } from './dom.js';
import { decideMode, FrameWatchdog, readEnvironment } from './eligibility.js';

const LOAD_FAILED = 'WEAVE: the 3D quilt could not load, so the still image stays.';
const WEBGL_FAILED = 'WEAVE: WebGL setup failed, so the still image stays.';

const hooks = readHooks(window.location.search);
// ?frame=still: the capture recipe (D19) shows the stage alone, filling the viewport.
if (hooks.still) document.documentElement.dataset.frame = 'still';
const result = cleanPanels(window.WEAVE_PANELS);
if (result.error) console.error(result.error);
result.warnings.forEach((warning) => console.warn(warning));
const stage = document.querySelector('[data-hero]');
const hint = document.querySelector('[data-hint]');
const controls = document.querySelector('[data-controls]');
const pause = document.querySelector('[data-pause]');
renderPanels(document.getElementById('panels'), result);
// A broken file keeps the static label from the HTML.
if (!result.error) setStageLabel(stage, result.panels);

async function startHero() {
  const decision = decideMode(readEnvironment(window));
  if (!decision.live) {
    setHeroState(stage, hint, 'still', decision.reason);
    return;
  }
  setHeroState(stage, hint, 'still', 'loading');
  let modules;
  try {
    // Dynamic only: the still path must never request Three.js or the scene.
    const [scene, motion, tiles] = await Promise.all([import('./scene.js'), import('./motion.js'), import('./tiles.js'),
      import('three'), import('./layout.js')]);
    modules = { scene, motion, tiles };
  } catch (err) {
    console.warn(LOAD_FAILED, err);
    setHeroState(stage, hint, 'still', 'load-failed');
    return;
  }
  // false keeps the fallback font for the session: a late font never repaints the faces.
  await modules.tiles.fontsReady();
  startLive(modules, fillSlots(result.panels));
}

function startLive({ scene: S, motion: M, tiles }, slots) {
  const canvas = document.createElement('canvas');
  // Before createRenderer: the stage canvas is hidden from assistive tech, and U4's test keys on it.
  canvas.setAttribute('aria-hidden', 'true');
  let renderer;
  try {
    renderer = S.createRenderer(canvas);
  } catch (err) {
    console.warn(WEBGL_FAILED, err);
    setHeroState(stage, hint, 'still', 'webgl-failed');
    return;
  }
  let quilt;
  try {
    quilt = S.buildQuilt(renderer, { slots });
  } catch (err) {
    renderer.dispose();
    renderer.forceContextLoss();
    console.warn(LOAD_FAILED, err);
    setHeroState(stage, hint, 'still', 'load-failed');
    return;
  }

  const order = slots.map((entry) => (entry ? entry.id : null));
  const dog = hooks.watchdog ? new FrameWatchdog({ limitMs: hooks.limitMs }) : null;
  // The block springs: #8 and #9 set their targets; Pause jumps them to the end.
  const springs = new M.SpringSet(slots.length);
  let tilt = { x: 0, y: 0 };
  const tiltTarget = { x: 0, y: 0 };
  let stopped = false;
  let paused = false;
  let onScreen = true;
  let rafId = 0;
  let last = 0;
  let clock = 0;
  let lastDt = 0;
  let frames = 0;

  stage.append(canvas);
  stage.classList.add('is-live');
  showLiveControls(controls, pause, true);

  const resize = () => {
    const width = stage.clientWidth;
    const height = stage.clientHeight;
    if (!width || !height) return;
    quilt.resize(width, height, Math.min(window.devicePixelRatio || 1, S.MAX_PIXEL_RATIO));
    // Resizing clears the canvas, and a ResizeObserver runs after this frame's render and before it paints, so
    // redraw the current pose now (uncounted), whether or not a frame is coming: else the quilt flickers to paper.
    if (!stopped) draw();
  };
  const sizeObserver = new ResizeObserver(resize);
  sizeObserver.observe(stage);
  // Synchronously too, as Coalesce does, so the first live frame already has the right buffer and aspect.
  resize();

  function draw() {
    quilt.setAmbient({ sway: hooks.rest ? 0 : M.swayAngle(clock), tiltX: tilt.x, tiltY: tilt.y });
    quilt.render();
  }

  // D8: time comes only from rAF timestamps, never from Date.
  function frame(now) {
    rafId = 0;
    if (stopped) return;
    const dtMs = last ? Math.min(100, now - last) : 1000 / 60;
    last = now;
    if (dog && dog.add(dtMs) === 'too-slow') {
      stop('too-slow');
      return;
    }
    const h = M.capDt(dtMs / 1000);
    clock += h;
    lastDt = h;
    springs.advance(h);
    tilt = M.followTilt(tilt, tiltTarget, h);
    draw();
    frames += 1;
    stage.dataset.heroFrames = String(frames);
    if (frames === 1) performance.mark('weave:first-live-frame');
    schedule();
  }

  // rAF keeps firing in a hidden tab (U5), so the loop checks document.hidden itself.
  function schedule() {
    if (!rafId && !stopped && !paused && onScreen && !document.hidden) rafId = requestAnimationFrame(frame);
  }

  function unschedule() {
    if (rafId) cancelAnimationFrame(rafId);
    rafId = 0;
    last = 0;
  }

  // ?pose=rest (D34) holds the quilt at rest: no sway, and the pointer is ignored, so the tilt stays 0. The loop
  // and the watchdog run as usual.
  if (!hooks.rest) {
    canvas.addEventListener('pointermove', (event) => {
      const r = canvas.getBoundingClientRect();
      const x = ((event.clientX - r.left) / r.width) * 2 - 1;
      const y = 1 - ((event.clientY - r.top) / r.height) * 2;
      tiltTarget.x = -y * M.AMBIENT.tiltX;
      tiltTarget.y = x * M.AMBIENT.tiltY;
    });
    canvas.addEventListener('pointerleave', () => {
      tiltTarget.x = 0;
      tiltTarget.y = 0;
    });
  }
  const onContextLost = (event) => {
    event.preventDefault();
    stop('context-lost');
  };
  canvas.addEventListener('webglcontextlost', onContextLost);

  // Pausing jumps any running sequence to its end, stops the loop and draws that pose once (uncounted).
  const onPause = () => {
    paused = !paused;
    setPaused(pause, paused);
    if (paused) {
      springs.snap();
      unschedule();
      draw();
    } else {
      schedule();
    }
  };
  pause.addEventListener('click', onPause);

  // Off screen or in a hidden tab, the pending frame is cancelled too (coalesce/public/js/hero.js), so none runs.
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

  // The only teardown: the watchdog, a lost context and the hook all come here, once. It releases the rAF handle
  // (with last reset), both observers, the document's visibilitychange listener, the Pause listener (Pause and the
  // controls row hidden again), the canvas with its pointer listeners, and the webglcontextlost listener (removed
  // before quilt.dispose() forces the context loss); then is-live, and setHeroState writes the still and #5's
  // still hint.
  function stop(reason) {
    if (stopped) return;
    stopped = true;
    unschedule();
    sizeObserver.disconnect();
    visibility.disconnect();
    document.removeEventListener('visibilitychange', onVisibilityChange);
    pause.removeEventListener('click', onPause);
    showLiveControls(controls, pause, false);
    canvas.removeEventListener('webglcontextlost', onContextLost);
    canvas.remove();
    stage.classList.remove('is-live');
    quilt.dispose();
    setHeroState(stage, hint, 'still', reason);
  }

  // The test and sibling-epic hooks; they outlive the teardown (stop is then a no-op and the clock frozen).
  stage.__weave = {
    get mode() { return 'quilt'; },
    get order() { return order.slice(); },
    get slots() {
      return slots.map((entry) => ({ id: entry ? entry.id : null, name: entry ? entry.name : null,
        status: entry ? entry.status : null, face: tiles.faceKind(entry) }));
    },
    get clock() { return clock; },
    // Test-only: the last frame's h, in seconds.
    get lastDt() { return lastDt; },
    stop,
    snapshot: () => quilt.snapshot(),
    // Test-only.
    project: (point) => quilt.project(point),
  };
  setHeroState(stage, hint, 'live', 'ok');
  schedule();
}

startHero();
