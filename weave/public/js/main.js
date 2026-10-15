// WEAVE's boot module: the panel lists first, then the hero. The load-time decision picks the still or the live
// quilt; going live is a port of Coalesce's startLive (coalesce/public/js/hero.js).
import { cleanPanels } from './catalog.js';
import {
  createTooltip, fillSlots, hideTooltip, readHooks, renderPanels, setDataMode, setHeroState, setPaused, setStageLabel,
  setToggle, showLiveControls, showTooltip,
} from './dom.js';
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
const toggle = document.querySelector('[data-toggle]');
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
    // Dynamic only: the still path must never request Three.js or the scene. The font wait (which never rejects;
    // false keeps the fallback font for the session, so a late font never repaints the faces) overlaps the rest.
    const [scene, motion, tiles, , layout] = await Promise.all([import('./scene.js'), import('./motion.js'),
      import('./tiles.js').then(async (module) => { await module.fontsReady(); return module; }),
      import('three'), import('./layout.js')]);
    modules = { scene, motion, tiles, layout };
  } catch (err) {
    console.warn(LOAD_FAILED, err);
    setHeroState(stage, hint, 'still', 'load-failed');
    return;
  }
  startLive(modules, fillSlots(result.panels));
}

function startLive({ scene: S, motion: M, layout: L }, slots) {
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
  // #10: compile every program now, the hidden decor's included (compile walks hidden objects), so the first frame
  // that shows a stitch or a pin does not stall on a shader compile.
  renderer.compile(quilt.scene, quilt.camera);

  // Block index -> id, as built; the hooks map it through the director's slot map (#9).
  const order = slots.map((entry) => (entry ? entry.id : null));
  const dog = hooks.watchdog ? new FrameWatchdog({ limitMs: hooks.limitMs }) : null;
  // The director (#8) owns the blocks' springs, the mode and (#9) the slot map. A block's quilt pose is its slot's
  // centre with its own build lift and tilt, read once here (scene.js keeps the planned lift to itself); the tile
  // pose is its slot in the tile grid, flat and flipped.
  const lifts = quilt.blocks.map((block) => block.position.z);
  const tilts = quilt.blocks.map((block) => block.rotation.z);
  const director = new M.Director({
    count: slots.length,
    quiltPose: (i, slot) => ({ position: [...L.slotCentre(slot), lifts[i]], rotY: 0, rotZ: tilts[i], morph: 0 }),
    tilePose: (i, slot) => ({ position: [...L.slotCentre(slot, 'tiles'), 0], rotY: Math.PI, rotZ: 0, morph: 1 }),
    isTile: (i) => quilt.blocks[i].userData.face !== 'filler',
    // #10's intro: each panel block flies in from its seeded scatter point; a filler only fades in.
    introFrom: (i) => (order[i] === null ? null : M.introScatter(order[i])),
    onEnter,
  });
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
  // __weave.mode after a teardown: the director's mode at that moment, even if a transition was mid-flight.
  let stoppedMode = null;

  stage.append(canvas);
  const tip = createTooltip(stage);
  stage.classList.add('is-live');
  showLiveControls(controls, [pause, toggle], true);

  const resize = () => {
    const width = stage.clientWidth;
    const height = stage.clientHeight;
    if (!width || !height) return;
    quilt.resize(width, height, Math.min(window.devicePixelRatio || 1, S.MAX_PIXEL_RATIO));
  };
  const sizeObserver = new ResizeObserver(resize);
  sizeObserver.observe(stage);
  // Synchronously too, as Coalesce does, so the first live frame already has the right buffer and aspect.
  resize();

  // The director's pose, fade and ambient weight into the scene, without rendering. The sway and tilt are scaled
  // by the ambient weight, which is exactly 0 in tiles mode.
  function sync() {
    for (let i = 0; i < slots.length; i += 1) quilt.setBlockPose(i, director.pose(i));
    quilt.setFade(director.fade);
    const a = director.ambient;
    quilt.setAmbient({ sway: (hooks.rest ? 0 : M.swayAngle(clock)) * a, tiltX: tilt.x * a, tiltY: tilt.y * a });
  }

  function draw() {
    if (stopped) return;
    sync();
    quilt.render();
  }

  // --- #10's decor: each block is dressed (its stitches sewn in, its pins dropped) once, as its intro flight passes
  // DRESS_AT; a sew-back returns each block's stowed decor the same way. `dressed` holds the block indices done. ---
  const dressed = new Set();

  function dress(i, options) {
    dressed.add(i);
    const { id, status, face } = quilt.blocks[i].userData;
    if (face === 'sewn' && status === 'live') quilt.revealStitches(id, options);
    if (face === 'planned') quilt.restorePins(id, options);
  }

  // The blocks whose flight has passed DRESS_AT this frame: dressed in the intro, unstowed in a sew-back.
  function dressFlights() {
    const mode = director.mode;
    if (mode !== 'intro' && mode !== 'restitching') return;
    for (let i = 0; i < slots.length; i += 1) {
      if (dressed.has(i) || director.progress(i) < M.DRESS_AT) continue;
      if (mode === 'intro') dress(i);
      else {
        dressed.add(i);
        quilt.unstowBlock(i);
      }
    }
  }

  // --- #10's hover: in settled quilt only, the block under the pointer lifts and is named. One pick a frame (every
  // frame, so a resting pointer is named on entering quilt and the sway is followed); each block's amount eases to
  // its target and snaps to it within 1e-3, so leaving restores #8's exact pose. ---
  const pointer = { x: 0, y: 0, inside: false };
  let hoverTarget = null;
  const amounts = new Array(slots.length).fill(0);

  function pickHover() {
    hoverTarget = director.mode === 'quilt' && pointer.inside ? quilt.pickBlock(pointer.x, pointer.y) : null;
    if (hoverTarget === null) {
      hideTooltip(tip);
      return;
    }
    const r = stage.getBoundingClientRect();
    showTooltip(tip, { name: slots[hoverTarget].name, face: quilt.blocks[hoverTarget].userData.face },
      pointer.x - r.left, pointer.y - r.top);
  }

  function easeHover(h) {
    const f = h === null ? 1 : Math.min(1, h * S.HOVER.rate);
    amounts.forEach((a, i) => {
      const target = i === hoverTarget ? 1 : 0;
      if (a === target) return;
      let next = a + (target - a) * f;
      if (Math.abs(target - next) < 1e-3) next = target;
      amounts[i] = next;
      quilt.setHover(i, next);
    });
  }

  function clearHover() {
    hoverTarget = null;
    amounts.forEach((a, i) => {
      if (a === 0) return;
      amounts[i] = 0;
      quilt.setHover(i, 0);
    });
  }

  // Every state the director enters (D39): the scene first, so a handler's snapshot() sees the pose (outside quilt
  // with no hover lift); data-mode quilt from the intro's entry, and otherwise only when the mode is settled; the
  // label and hint on every entry, so they change on press; the decor (dressed at once on the first quilt, returned
  // at a sew-back's settle, stowed on unstitching); then weave:mode. After a teardown (a weave:mode handler may call
  // stop) nothing is written and nothing fires.
  function onEnter(mode, from) {
    if (stopped) return;
    if (mode !== 'quilt') clearHover();
    sync();
    if (mode === 'intro') setDataMode(stage, 'quilt');
    else if (M.SETTLED.includes(mode)) setDataMode(stage, mode);
    setToggle(toggle, hint, mode);
    if (mode === 'quilt' && (from === null || from === 'intro')) {
      for (let i = 0; i < slots.length; i += 1) if (!dressed.has(i)) dress(i, { animate: false });
      quilt.finishDecor();
    } else if (mode === 'quilt' && from === 'restitching') {
      quilt.unstowAll({ animate: false });
      quilt.finishDecor();
    } else if (mode === 'unstitching') {
      dressed.clear();
      quilt.stowAll();
    }
    if (mode !== 'quilt') hideTooltip(tip);
    stage.dispatchEvent(new CustomEvent('weave:mode', { detail: { mode, from } }));
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
    director.advance(h);
    // A weave:mode handler run from the advance may have torn the scene down: the still counts no frame.
    if (stopped) return;
    dressFlights();
    quilt.tick(h);
    if (director.mode === 'quilt') {
      pickHover();
      easeHover(h);
    }
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
  // and the watchdog run as usual. The pointer is clamped to the canvas: defensive, since only a tile press
  // in tiles is captured (#9) and the ambient weight is 0 there, but a captured move past the edge never tilts
  // past AMBIENT's ceilings.
  const clamp1 = (v) => Math.min(1, Math.max(-1, v));
  const onTilt = (event) => {
    const r = canvas.getBoundingClientRect();
    const x = clamp1(((event.clientX - r.left) / r.width) * 2 - 1);
    const y = clamp1(1 - ((event.clientY - r.top) / r.height) * 2);
    tiltTarget.x = -y * M.AMBIENT.tiltX;
    tiltTarget.y = x * M.AMBIENT.tiltY;
  };
  const onTiltLeave = () => {
    tiltTarget.x = 0;
    tiltTarget.y = 0;
  };
  // #10's hover follows the pointer over the canvas; the frame picks, but while paused (no frame) the pick runs
  // here, the amounts snap to their target and the pose is drawn at once.
  const onHoverMove = (event) => {
    pointer.x = event.clientX;
    pointer.y = event.clientY;
    pointer.inside = true;
    if (!paused) return;
    pickHover();
    easeHover(null);
    draw();
  };
  const onHoverLeave = () => {
    pointer.inside = false;
    hoverTarget = null;
    hideTooltip(tip);
    if (!paused) return;
    easeHover(null);
    draw();
  };
  if (!hooks.rest) {
    canvas.addEventListener('pointermove', onTilt);
    canvas.addEventListener('pointerleave', onTiltLeave);
    canvas.addEventListener('pointermove', onHoverMove);
    canvas.addEventListener('pointerleave', onHoverLeave);
  }
  const onContextLost = (event) => {
    event.preventDefault();
    stop('context-lost');
  };
  canvas.addEventListener('webglcontextlost', onContextLost);

  // Pausing jumps a running transition to its end, stops the loop and draws that pose once (uncounted). Every
  // `now` the director sees is the event's timeStamp (D8).
  const onPause = (event) => {
    paused = !paused;
    setPaused(pause, paused);
    // The decor first, so a transition the director finishes here dresses or stows its decor at once.
    quilt.setPaused(paused);
    director.setPaused(paused, event.timeStamp);
    if (paused) {
      // The hover jumps to its end too: the block under the pointer fully lifted, every other one back on its seams.
      if (director.mode === 'quilt') pickHover();
      easeHover(null);
      unschedule();
      draw();
    } else {
      schedule();
    }
  };
  pause.addEventListener('click', onPause);

  // #9's drag: one press at a time, from the primary pointer's main button. A press that moves more than
  // DRAG.thresholdPx is never a click; one that starts on a tile in settled tiles grabs it at that point (the mode
  // at the press decides) and is captured, so the drag follows the pointer off the canvas. Each slot change
  // refolds the moved blocks at once (they are flat in tiles); the sashing is re-cut once, at the drop, since it is
  // hidden until the sew-back. A paused drag draws itself, as no frame will.
  let press = null;
  let suppressClick = false;
  let reseamDue = false;

  function apply(moves) {
    for (const [i, slot] of moves) quilt.placeBlock(i, slot);
    if (moves.length > 0) reseamDue = true;
  }

  function endDrag() {
    director.drop();
    if (reseamDue) {
      quilt.reseam();
      reseamDue = false;
    }
    if (paused) draw();
  }

  // A drag ends on its own pointer's release or cancel, and also on anything that means that release is lost: a
  // new press (a touch tap is primary too), lost capture, or a move with the button up.
  const onPointerDown = (event) => {
    if (!event.isPrimary || event.button !== 0) return;
    if (director.dragging) endDrag();
    suppressClick = false;
    const hit = quilt.pick(event.clientX, event.clientY);
    const armed = director.mode === 'tiles' && hit.part === 'tile';
    press = { id: event.pointerId, x: event.clientX, y: event.clientY, at: quilt.planePoint(event.clientX, event.clientY),
      hit, moved: false, armed };
    if (armed) {
      canvas.setPointerCapture(event.pointerId);
      event.preventDefault();
    }
  };
  const onPointerMove = (event) => {
    if (!press || event.pointerId !== press.id) return;
    if ((event.buttons & 1) === 0) {
      onPointerEnd(event);
      return;
    }
    if (!press.moved) {
      if (Math.hypot(event.clientX - press.x, event.clientY - press.y) <= M.DRAG.thresholdPx) return;
      press.moved = true;
      if (press.armed) director.grab(director.blockAt(press.hit.slot), press.at);
    }
    if (!director.dragging) return;
    apply(director.dragTo(quilt.planePoint(event.clientX, event.clientY)));
    if (paused) draw();
  };
  const onPointerEnd = (event) => {
    if (!press || event.pointerId !== press.id) return;
    if (press.moved) suppressClick = true;
    if (director.dragging) endDrag();
    press = null;
  };
  canvas.addEventListener('pointerdown', onPointerDown);
  canvas.addEventListener('pointermove', onPointerMove);
  canvas.addEventListener('pointerup', onPointerEnd);
  canvas.addEventListener('pointercancel', onPointerEnd);
  canvas.addEventListener('lostpointercapture', onPointerEnd);

  // The toggle and a click on the canvas (at ?pose=rest too). While paused a press snaps, so it is drawn at once.
  // A toggle mid-drag drops the tile first, so the sew-back starts from its new slot.
  const onToggle = (event) => {
    if (director.dragging) endDrag();
    director.toggle(event.timeStamp);
    if (paused) draw();
  };
  toggle.addEventListener('click', onToggle);
  const onCanvasClick = (event) => {
    if (director.dragging) endDrag();
    if (suppressClick) {
      suppressClick = false;
      return;
    }
    if (director.click(quilt.pick(event.clientX, event.clientY), event.timeStamp) && paused) draw();
  };
  canvas.addEventListener('click', onCanvasClick);

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
  // (with last reset), both observers, the document's visibilitychange listener, the Pause and toggle listeners
  // (both buttons and the controls row hidden again), the canvas with its click, tilt and drag (#9) pointer
  // listeners, the hover listeners and tooltip (#10), and the webglcontextlost listener (removed before
  // quilt.dispose() forces the context loss); then
  // is-live and data-mode, and setHeroState writes the still and #5's still hint, even if dispose throws. The
  // director's in-flight transition (or drag) is abandoned: nothing advances it again, onEnter writes and fires
  // nothing, and __weave.mode keeps the mode it had here.
  function stop(reason) {
    if (stopped) return;
    stopped = true;
    stoppedMode = director.mode;
    unschedule();
    sizeObserver.disconnect();
    visibility.disconnect();
    document.removeEventListener('visibilitychange', onVisibilityChange);
    pause.removeEventListener('click', onPause);
    toggle.removeEventListener('click', onToggle);
    showLiveControls(controls, [pause, toggle], false);
    canvas.removeEventListener('click', onCanvasClick);
    canvas.removeEventListener('pointermove', onTilt);
    canvas.removeEventListener('pointerleave', onTiltLeave);
    canvas.removeEventListener('pointermove', onHoverMove);
    canvas.removeEventListener('pointerleave', onHoverLeave);
    canvas.removeEventListener('pointerdown', onPointerDown);
    canvas.removeEventListener('pointermove', onPointerMove);
    canvas.removeEventListener('pointerup', onPointerEnd);
    canvas.removeEventListener('pointercancel', onPointerEnd);
    canvas.removeEventListener('lostpointercapture', onPointerEnd);
    canvas.removeEventListener('webglcontextlost', onContextLost);
    canvas.remove();
    tip.remove();
    stage.classList.remove('is-live');
    setDataMode(stage, null);
    try {
      quilt.dispose();
    } finally {
      setHeroState(stage, hint, 'still', reason);
    }
  }

  // A per-block call forwarded to the scene; nothing after a teardown.
  function perBlock(name, id, arg) {
    if (stopped) return;
    quilt[name](id, arg);
    if (paused) draw();
  }

  // The test and sibling-epic hooks; they outlive the teardown (stop is then a no-op and the clock frozen).
  stage.__weave = {
    get mode() { return stopped ? stoppedMode : director.mode; },
    // order and slots list the slots, so they follow a drag (#9).
    get order() { return slots.map((_, k) => order[director.blockAt(k)]); },
    get slots() {
      return slots.map((_, k) => {
        const entry = slots[director.blockAt(k)];
        // The drawn face, which #16's setFace can change.
        return { id: entry ? entry.id : null, name: entry ? entry.name : null, status: entry ? entry.status : null,
          face: quilt.blocks[director.blockAt(k)].userData.face };
      });
    },
    get clock() { return clock; },
    // Test-only: the last frame's h, in seconds.
    get lastDt() { return lastDt; },
    stop,
    snapshot: () => quilt.snapshot(),
    // Test-only.
    project: (point) => quilt.project(point),
    // Test-only: the faded parts' { opacity, visible }.
    fades: () => quilt.fades(),
    // Test-only (#9): block `id`'s { slot, tilt, positions, normals } base (local, before its tilt), or null.
    blockBase: (id) => {
      const i = order.indexOf(id);
      return id === null || i < 0 ? null : quilt.blockBase(i);
    },
    // Test-only (#9): what is under a client point, as the canvas's press sees it.
    pick: (x, y) => quilt.pick(x, y),
    // Test-only (#10): the hover's pick (a block index, or null), which verify.py times.
    pickBlock: (x, y) => quilt.pickBlock(x, y),
    // #10's per-block calls for E2's #16 (scene.js has the contract); a paused page draws the change at once.
    revealStitches: (id, options) => perBlock('revealStitches', id, options),
    popStitches: (id, options) => perBlock('popStitches', id, options),
    popPins: (id, options) => perBlock('popPins', id, options),
    restorePins: (id, options) => perBlock('restorePins', id, options),
    setFace: (id, kind) => perBlock('setFace', id, kind),
    // Test-only (#10): no stitch or pin animation running; the hovered block's id (null for none) with the largest
    // hover amount; the quilt group's world matrix (16 numbers), read after an update.
    get decorIdle() { return quilt.decorIdle; },
    get hover() { return { id: hoverTarget === null ? null : order[hoverTarget], amount: Math.max(...amounts) }; },
    groupMatrix: () => {
      quilt.group.updateMatrixWorld(true);
      return Array.from(quilt.group.matrixWorld.elements);
    },
  };
  setHeroState(stage, hint, 'live', 'ok');
  // The first weave:mode (from null) fires here, after __weave exists and before the first frame: the intro (#10),
  // or the quilt at once at ?pose=rest.
  director.start(hooks.rest ? 'quilt' : 'intro');
  schedule();
}

startHero();
