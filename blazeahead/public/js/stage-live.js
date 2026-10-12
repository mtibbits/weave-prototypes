// The live side of the stage: loads the world, runs the render loop, and gives the page what it needs
// (home: the signpost that starts the tour; help: the junction; tour: walks between stops and rock tooltips).
// Anything going wrong (slow device, lost GPU) leaves the still image in place and says why.
import { FrameWatchdog } from './eligibility.js';
import { loadWorld, WorldView } from './world.js';
import { loadTour, signText } from './content.js';
import { Walk, walkDuration, walkPose } from './rig.js';

const MAX_PIXEL_RATIO = 1.5;
export const VIEW_ORDER = ['trailhead', 'continuity', 'scaffolding', 'knowledge', 'in-flight'];

// Camera points for a move between tour positions a and b (-1 = trailhead, 0.. = stops), and the two views' look
// targets (walkPose turns from one to the other, looking down the path in between).
export function walkPlan(layout, a, b) {
  const lo = Math.min(a, b) + 1;
  const hi = Math.max(a, b) + 1;
  const pts = [];
  for (let j = lo; j < hi; j++) {
    const seg = layout.walks[j].points;
    const from = j === lo ? 0 : 1;
    const to = j === hi - 1 ? seg.length : seg.length - 1;
    pts.push(...seg.slice(from, to));
  }
  if (b < a) pts.reverse();
  const views = layout.views;
  const start = views[VIEW_ORDER[a + 1]];
  const end = views[VIEW_ORDER[b + 1]];
  return { points: pts, fromTarget: start.target, toTarget: end.target, hfovFrom: start.hfov, hfovTo: end.hfov };
}

export async function startLive(el, options, setState) {
  const { variant = 'home', assetsBase = 'assets/', watchdog = true, watchdogLimitMs = 45, tourUrl = 'tour/' } = options;
  const tour = loadTour(window);
  let assets;
  try {
    assets = await loadWorld(assetsBase, variant === 'help' ? 'junction' : 'world');
    if (document.fonts && document.fonts.load) {
      await Promise.all([document.fonts.load('600 64px Fraunces'), document.fonts.ready]);
    }
  } catch (err) {
    console.warn('blazeAhead: the 3D scene could not load, so the still image stays.', err);
    return setState(el, 'still', 'load-failed');
  }
  const canvas = document.createElement('canvas');
  canvas.setAttribute('aria-hidden', 'true');
  let view;
  try {
    // ?tone=aces|agx|none&exposure=1.2 tune the look while developing; the defaults ship
    const query = new URLSearchParams(window.location.search);
    const look = {};
    if (query.has('tone')) look.tone = query.get('tone');
    if (query.has('exposure')) look.exposure = Number(query.get('exposure'));
    view = new WorldView(canvas, assets, { label: (key) => signText(tour, key), rocks: tour.rocks, ...look });
  } catch (err) {
    console.warn('blazeAhead: WebGL setup failed, so the still image stays.', err);
    return setState(el, 'still', 'webgl-failed');
  }
  const layout = assets.layout;
  const firstView = variant === 'help' ? 'junction' : 'trailhead';
  view.showView(firstView);

  const pauseButton = document.querySelector('[data-pause]');
  const dog = watchdog ? new FrameWatchdog({ limitMs: watchdogLimitMs }) : null;
  const tip = document.createElement('div');
  tip.className = 'stage-tip';
  tip.hidden = true;
  let paused = false;
  let onScreen = true;
  let stopped = false;
  let rafId = 0;
  let last = 0;
  let frames = 0;
  let walking = null;
  let stopIndex = -1;
  const api = { state: 'live', reason: 'ok', view, onstop: null };

  el.append(canvas);
  el.append(tip);
  el.classList.add('is-live');

  const resize = () => {
    const width = el.clientWidth;
    const height = el.clientHeight;
    if (!width || !height) return;
    view.resize(width, height, Math.min(window.devicePixelRatio || 1, MAX_PIXEL_RATIO));
    if (!rafId && !stopped) view.render();
  };
  const sizeObserver = new ResizeObserver(resize);
  sizeObserver.observe(el);
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
    if (walking) advanceWalk(now);
    view.update(dt, !paused);
    view.render();
    frames += 1;
    el.dataset.stageFrames = String(frames);
    schedule();
  }

  function schedule() {
    const wanted = walking || (!paused && onScreen && !document.hidden);
    if (!rafId && !stopped && wanted) rafId = requestAnimationFrame(frame);
  }

  function unschedule() {
    if (rafId) cancelAnimationFrame(rafId);
    rafId = 0;
    last = 0;
  }

  // ---- walks (tour)
  function advanceWalk(now) {
    const w = walking;
    const t = Math.min(1, (now - w.start) / w.durationMs);
    const pose = walkPose(w.walk, t, w.durationMs / 1000, w.plan.fromTarget, w.plan.toTarget);
    view.setPose(pose.position, pose.target, w.plan.hfovFrom + (w.plan.hfovTo - w.plan.hfovFrom) * t);
    if (t >= 1) {
      walking = null;
      w.resolve();
    }
  }

  api.walk = (from, to) => new Promise((resolve) => {
    if (stopped) {
      resolve();
      return;
    }
    const plan = walkPlan(layout, from, to);
    const walk = new Walk(plan.points);
    tip.hidden = true;
    walking = { walk, plan, start: performance.now(), durationMs: walkDuration(walk.length) * 1000, resolve };
    stopIndex = to;
    view.viewId = null;
    schedule();
  }).then(() => {
    if (!stopped) view.showView(VIEW_ORDER[to + 1]);
  });
  api.show = (index) => {
    stopIndex = index;
    view.showView(VIEW_ORDER[index + 1]);
    if (!rafId) view.render();
  };
  api.signBox = (side) => (walking || stopIndex < 0 ? null : view.boxFor(VIEW_ORDER[stopIndex + 1], side));
  api.paintMap = (laid, focus) => {
    if (stopped || !view.paintBoard(laid, focus)) return false;
    if (!rafId) view.render();
    return true;
  };
  const atKiosk = () => variant === 'tour' && !walking && VIEW_ORDER[stopIndex + 1] === 'knowledge';

  // ---- pointer
  const toNdc = (event) => {
    const r = canvas.getBoundingClientRect();
    return [((event.clientX - r.left) / r.width) * 2 - 1, 1 - ((event.clientY - r.top) / r.height) * 2];
  };
  const inBox = (box, event) => box && event.clientX >= box[0] && event.clientX <= box[2]
    && event.clientY >= box[1] && event.clientY <= box[3];
  canvas.addEventListener('pointermove', (event) => {
    const [x, y] = toNdc(event);
    view.pointer(x, y);
    if (variant === 'home') {
      canvas.style.cursor = inBox(view.boxFor('trailhead', 'tour'), event) ? 'pointer' : '';
    }
    if (atKiosk()) canvas.style.cursor = view.boardAt(x, y) ? 'pointer' : '';
    else if (variant === 'tour') canvas.style.cursor = '';     // walked away from the kiosk with the pointer on it
    if (variant === 'tour' && !walking && stopIndex === 0) {
      const label = view.rockAt(x, y);
      tip.hidden = !label;
      if (label) {
        const r = el.getBoundingClientRect();
        tip.textContent = `${label} · absorbed`;
        tip.style.left = `${event.clientX - r.left}px`;
        tip.style.top = `${event.clientY - r.top}px`;
      }
    }
    if (paused && !rafId) {
      view.update(0.016, false);
      view.render();
    }
  });
  canvas.addEventListener('pointerleave', () => {
    view.pointerLeave();
    tip.hidden = true;
  });
  canvas.addEventListener('click', (event) => {
    if (variant === 'home' && inBox(view.boxFor('trailhead', 'tour'), event)) window.location.href = tourUrl;
    if (atKiosk() && typeof api.onboard === 'function' && view.boardAt(...toNdc(event))) api.onboard();
  });
  canvas.addEventListener('webglcontextlost', (event) => {
    event.preventDefault();
    stop('context-lost');
  });

  const onPause = () => {
    paused = !paused;
    pauseButton.setAttribute('aria-pressed', String(paused));
    pauseButton.textContent = paused ? 'Play motion' : 'Pause motion';
    if (paused && !walking) unschedule();
    else schedule();
  };
  if (pauseButton) {
    pauseButton.hidden = false;
    pauseButton.addEventListener('click', onPause);
  }

  const visibility = new IntersectionObserver((entries) => {
    onScreen = entries[entries.length - 1].isIntersecting;
    if (onScreen) schedule();
    else if (!walking) unschedule();
  });
  visibility.observe(el);
  const onVisibilityChange = () => {
    if (document.hidden && !walking) unschedule();
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
    if (walking) {
      const w = walking;
      walking = null;
      w.resolve();
    }
    canvas.remove();
    tip.remove();
    el.classList.remove('is-live');
    view.dispose();
    api.state = 'still';
    api.reason = reason;
    setState(el, 'still', reason);
    if (typeof api.onstop === 'function') api.onstop(reason);
  }
  api.stop = stop;

  el.__blaze = api;
  setState(el, 'live', 'ok');
  schedule();
  return api;
}
