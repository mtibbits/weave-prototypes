// The Help page's hero (#18): one corner of the quilt coming apart, with loose threads swaying, a needle and a spool
// of thread beside it, and the pointer stirring the threads. It follows E1's hero contract (main.js): the load-time
// decision first, then Three.js and the scene through import() on the live path only, so the still path never
// requests them. It never loads panels.js: the corner's fabrics are constants here, so the Help still never goes
// stale from a panels.js edit (a painter or scene change still needs a recapture, #19).
// The corner is composed from E1's exports with no edit to fabric.js or scene.js. World space is quilt space (#7's
// frame: origin at the quilt's centre, x right, y up, scene units), so the sashing's UV rule (#6, D38), the fray edge,
// the strands and the needle share one frame, and the needle's parent space is world space (#13's poseOnCurve, #19).
// The hook is stage.__weaveHelp = { fray, stop(reason), project([x, y, z]), edge, needle, spool, fringe }: fray is the
// live fray.js simulation; stop tears the scene down once (later calls do nothing); project gives a world point's
// client CSS px on the canvas (test-only); edge is the fray-edge curve in world space (getPointAt(u), u in [0, 1]);
// needle and spool are the props as drawn (createNeedle and createSpool's roots; #22 swaps in the modelled ones);
// fringe is test-only: { paints, textureVersion, materialVersion, threshold }. The hook outlives the teardown.
import { readHooks, setPaused, showLiveControls } from './dom.js';
import { decideMode, FrameWatchdog, readEnvironment } from './eligibility.js';

const LOAD_FAILED = 'WEAVE: the frayed corner could not load, so the still image stays.';
const WEBGL_FAILED = 'WEAVE: WebGL setup failed, so the still image stays.';

// The corner's two blocks, slots 10 and 11 (row 2): a fabric preset and a seed id each, fixed here, never from
// panels.js. A block's loose threads take its preset's ground colour (colors[0]).
const CORNER = Object.freeze([{ slot: 10, preset: 'indigo-dots', seed: 'help-corner-a' },
  { slot: 11, preset: 'mustard-calico', seed: 'help-corner-b' }]);
// The threads under the sashing: a darker muslin, which reads on the linen page.
const SASHING_THREAD = '#B5A27C';
// The needle's tail and the spool's thread, one colour (the needle tail's default, #13).
const THREAD_COLOR = '#C9A227';
const SEED = 'help-fray';
// The fray: the bottom binding stops short of it, so along [EDGE_X0, EDGE_X1] the raw edge shows, at y = -H/2.
const EDGE_X0 = 0.35;
const EDGE_X1 = 2.0;
const STRAND_LENGTH = 0.55;
const STRAND_WIDTH = 0.011;
// Depths in front of the sashing (z = 0): the blocks, the fringe, then the strand plane, which the edge lies in.
const BLOCK_LIFT = 0.01;
const FRINGE_Z = BLOCK_LIFT + 0.002;
const STRAND_Z = BLOCK_LIFT + 0.004;
// What the camera must see: the edge, the strands at full length with their sway and stir room, the needle and the
// spool. The framing test, not these numbers, is the contract; widen the margin, never move the camera by hand.
const CORNER_BOUNDS = Object.freeze({ minX: 0.05, maxX: 2.45, minY: -2.45, maxY: -0.95, margin: 0.06 });

const hooks = readHooks(window.location.search);
const stage = document.querySelector('[data-hero]');
const controls = document.querySelector('[data-controls]');
const pause = document.querySelector('[data-pause]');

// The one writer of the stage's state attributes. Help has no hint line, so dom.js's setHeroState (which writes one)
// is not used.
function setHeroState(state, reason) {
  stage.dataset.heroState = state;
  stage.dataset.heroReason = reason;
}

async function startHero() {
  const decision = decideMode(readEnvironment(window));
  if (!decision.live) {
    setHeroState('still', decision.reason);
    return;
  }
  setHeroState('still', 'loading');
  let modules;
  try {
    const [THREE, scene, needle, spool, fabric, layout, random, fray] = await Promise.all([import('three'),
      import('./scene.js'), import('./needle.js'), import('./spool.js'), import('./fabric.js'), import('./layout.js'),
      import('./random.js'), import('./fray.js')]);
    modules = { THREE, scene, needle, spool, fabric, layout, random, fray };
  } catch (err) {
    console.warn(LOAD_FAILED, err);
    setHeroState('still', 'load-failed');
    return;
  }
  startLive(modules);
}

// The raw edge's fringe: short threads of the cloth above each point (colorAt(u), u across the strip), hanging from
// the strip's top, painted once. Alpha encodes depth into the fringe (1 at the top, falling toward 0.06 at the
// bottom), so the material's alphaTest alone sets how far it reaches.
function paintFringe(canvas, rng, colorAt) {
  const ctx = canvas.getContext('2d');
  const { width: w, height: h } = canvas;
  ctx.clearRect(0, 0, w, h);
  for (let i = 0; i < 1400; i += 1) {
    const x = rng() * w;
    // Many short threads keep the edge dense; fewer reach the bottom.
    const reach = h * (0.15 + 0.85 * rng() ** 2);
    ctx.lineWidth = 1 + rng() * 2;
    ctx.strokeStyle = colorAt(x / w);
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x + (rng() - 0.5) * 8, reach);
    ctx.stroke();
  }
  // Depth into alpha: keep each pixel's colour, and scale its alpha by how far down it sits.
  ctx.globalCompositeOperation = 'destination-in';
  const depth = ctx.createLinearGradient(0, 0, 0, h);
  depth.addColorStop(0, 'rgba(0, 0, 0, 1)');
  depth.addColorStop(1, 'rgba(0, 0, 0, 0.06)');
  ctx.fillStyle = depth;
  ctx.fillRect(0, 0, w, h);
  ctx.globalCompositeOperation = 'source-over';
}

// The fringe's alphaTest for a frayAmount: 0.05 shows the full fringe (1), 1 shows only the band (0). It stays in
// (0, 1], so a change never crosses 0 and recompiles the shader; it is one uniform. frayAmount is #19's to write, so
// a value that is not a finite number counts as fully frayed.
const fringeThreshold = (frayAmount) => {
  const f = Number.isFinite(frayAmount) ? Math.min(1, Math.max(0, frayAmount)) : 1;
  return 1 - 0.95 * f;
};

function startLive({ THREE, scene: S, needle: N, spool: P, fabric: F, layout: L, random: R, fray: Y }) {
  const canvas = document.createElement('canvas');
  // Before createRenderer: the stage canvas is hidden from assistive tech, and the webgl-failed test keys on it.
  canvas.setAttribute('aria-hidden', 'true');
  let renderer;
  try {
    renderer = S.createRenderer(canvas);
  } catch (err) {
    console.warn(WEBGL_FAILED, err);
    setHeroState('still', 'webgl-failed');
    return;
  }

  const { quiltW: W, quiltH: H, border } = L.LAYOUT;
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(35, 1.6);
  let edge;
  let fray;
  let needle;
  let spool;
  let fringeMaterial;
  let fringeTexture;
  let fringePaints = 0;
  const strandMeshes = [];
  try {
    S.addLights(scene);
    // A flat quad in quilt space, its UVs by #6's rule (u, v follow x and y across the whole quilt).
    const quad = (x0, x1, y0, y1, z, uv = (x, y) => [(x + W / 2) / W, (y + H / 2) / H]) => {
      const g = new THREE.BufferGeometry();
      const corners = [[x0, y0], [x1, y0], [x1, y1], [x0, y1]];
      g.setAttribute('position', new THREE.Float32BufferAttribute(corners.flatMap(([x, y]) => [x, y, z]), 3));
      g.setAttribute('normal', new THREE.Float32BufferAttribute(corners.flatMap(() => [0, 0, 1]), 3));
      g.setAttribute('uv', new THREE.Float32BufferAttribute(corners.flatMap(([x, y]) => uv(x, y)), 2));
      g.setIndex([0, 1, 2, 0, 2, 3]);
      return g;
    };
    const texture = (c) => {
      const t = new THREE.CanvasTexture(c);
      t.colorSpace = THREE.SRGBColorSpace;
      return t;
    };

    // The sashing and binding: #6's texture of the whole home quilt, sampled over the corner, with the bottom
    // binding left out along the fray. The weave keeps the blocks' scale, as scene.js's sashing does.
    const sashCanvas = F.makeCanvas(...F.sashingSize(L.LAYOUT));
    F.paintSashing(sashCanvas, L.LAYOUT);
    const sashNormal = S.weaveNormalMap().clone();
    sashNormal.repeat.set(W * S.WEAVE_REPEAT, H * S.WEAVE_REPEAT);
    const sashMaterial = S.fabricMaterial({ map: texture(sashCanvas), normalMap: sashNormal });
    const bindingTop = -H / 2 + border;
    for (const g of [quad(-0.4, W / 2, bindingTop, -0.5, 0), quad(-0.4, EDGE_X0, -H / 2, bindingTop, 0),
      quad(EDGE_X1, W / 2, -H / 2, bindingTop, 0)]) scene.add(new THREE.Mesh(g, sashMaterial));

    // The two blocks, lifted off the sashing so they never z-fight it.
    for (const { slot, preset, seed } of CORNER) {
      const c = F.makeCanvas(512);
      F.paintFabric(c, preset, seed);
      const block = new THREE.Mesh(new THREE.PlaneGeometry(L.LAYOUT.block, L.LAYOUT.block),
        S.fabricMaterial({ map: texture(c) }));
      block.position.set(...L.slotCentre(slot), BLOCK_LIFT);
      scene.add(block);
    }

    // The thread colour under a quilt-space x: the block's cloth, or the sashing's.
    const colorAt = (x) => {
      const block = CORNER.find(({ slot }) => Math.abs(x - L.slotCentre(slot)[0]) <= L.LAYOUT.block / 2);
      return block ? F.fabricFor(block.preset).colors[0] : SASHING_THREAD;
    };
    // The fringe, in the binding's band along the fray, painted once.
    const fringeCanvas = F.makeCanvas(1024, 96);
    paintFringe(fringeCanvas, R.rngFor(SEED, 'fringe'), (u) => colorAt(EDGE_X0 + u * (EDGE_X1 - EDGE_X0)));
    fringePaints += 1;
    fringeTexture = texture(fringeCanvas);
    fringeMaterial = new THREE.MeshStandardMaterial({ map: fringeTexture, roughness: 0.9,
      alphaTest: fringeThreshold(1) });
    scene.add(new THREE.Mesh(quad(EDGE_X0, EDGE_X1, -H / 2, bindingTop, FRINGE_Z,
      (x, y) => [(x - EDGE_X0) / (EDGE_X1 - EDGE_X0), (y + H / 2) / border]), fringeMaterial));

    // The fray edge, a straight line (never a CurvePath or a spline: r170 throws past u = 1 there, Issue-13), and
    // the strands pinned along it.
    edge = new THREE.LineCurve3(new THREE.Vector3(EDGE_X0 + 0.05, -H / 2, STRAND_Z),
      new THREE.Vector3(EDGE_X1 - 0.05, -H / 2, STRAND_Z));
    const pins = Array.from({ length: Y.STRANDS }, (_, k) => edge.getPointAt((k + 0.5) / Y.STRANDS).toArray());
    fray = Y.createFray({ pins, length: STRAND_LENGTH, seed: R.seedFor(SEED, 'fray'), rest: hooks.rest });
    // One material per thread colour, shared by the strands of that colour.
    const strandMaterials = new Map([...new Set(pins.map(([x]) => colorAt(x)))].map((color) => [color,
      new THREE.MeshStandardMaterial({ color, roughness: 0.9, side: THREE.DoubleSide })]));
    const index = [];
    for (let j = 0; j + 1 < Y.POINTS; j += 1) index.push(2 * j, 2 * j + 1, 2 * j + 2, 2 * j + 1, 2 * j + 3, 2 * j + 2);
    for (let k = 0; k < Y.STRANDS; k += 1) {
      const g = new THREE.BufferGeometry();
      g.setAttribute('position', new THREE.BufferAttribute(new Float32Array(Y.POINTS * 6), 3));
      const normals = new Float32Array(Y.POINTS * 6).map((_, i) => (i % 3 === 2 ? 1 : 0));
      g.setAttribute('normal', new THREE.BufferAttribute(normals, 3));
      g.setIndex(index);
      const mesh = new THREE.Mesh(g, strandMaterials.get(colorAt(pins[k][0])));
      mesh.frustumCulled = false;
      strandMeshes.push(mesh);
      scene.add(mesh);
    }

    // The props, at rest beside the corner, directly in the scene (world space is their parent space).
    needle = N.createNeedle({ threadColor: THREAD_COLOR });
    needle.position.set(0.42, -1.4, BLOCK_LIFT + 0.01);
    needle.rotation.z = THREE.MathUtils.degToRad(24);
    spool = P.createSpool({ threadColor: THREAD_COLOR });
    spool.position.set(2.16, -1.3, BLOCK_LIFT + P.SPOOL_FLANGE_RADIUS + 0.005);
    scene.add(needle, spool);

    S.fitCamera(camera, 1.6, CORNER_BOUNDS);
    // Every program now, so the first frame does not stall on a shader compile.
    renderer.compile(scene, camera);
  } catch (err) {
    renderer.dispose();
    renderer.forceContextLoss();
    console.warn(LOAD_FAILED, err);
    setHeroState('still', 'load-failed');
    return;
  }

  // Each strand's ribbon, rewritten in place from fray.js's points: STRAND_WIDTH across, in the strand plane.
  function writeStrands() {
    fray.strands.forEach(({ points }, k) => {
      const attr = strandMeshes[k].geometry.attributes.position;
      const a = attr.array;
      for (let j = 0; j < points.length; j += 1) {
        const p = points[j];
        const q = points[Math.min(j + 1, points.length - 1)];
        const o = points[Math.max(j - 1, 0)];
        let tx = q[0] - o[0];
        let ty = q[1] - o[1];
        const len = Math.sqrt(tx * tx + ty * ty) || 1;
        tx /= len;
        ty /= len;
        const nx = (-ty * STRAND_WIDTH) / 2;
        const ny = (tx * STRAND_WIDTH) / 2;
        const i = 6 * j;
        a[i] = p[0] - nx;
        a[i + 1] = p[1] - ny;
        a[i + 2] = p[2];
        a[i + 3] = p[0] + nx;
        a[i + 4] = p[1] + ny;
        a[i + 5] = p[2];
      }
      attr.needsUpdate = true;
    });
  }

  function draw() {
    if (stopped) return;
    writeStrands();
    const threshold = fringeThreshold(fray.frayAmount);
    if (fringeMaterial.alphaTest !== threshold) fringeMaterial.alphaTest = threshold;
    renderer.render(scene, camera);
  }

  const dog = hooks.watchdog ? new FrameWatchdog({ limitMs: hooks.limitMs }) : null;
  let stopped = false;
  let paused = false;
  let onScreen = true;
  let rafId = 0;
  let last = 0;
  let frames = 0;

  function writeFrayState() {
    if (stage.dataset.frayState !== fray.state) stage.dataset.frayState = fray.state;
  }

  // The one clock: time comes only from rAF timestamps, never from Date (#12's test clock pins Date).
  function frame(now) {
    rafId = 0;
    if (stopped) return;
    const dtMs = last ? Math.min(100, now - last) : 1000 / 60;
    last = now;
    if (dog && dog.add(dtMs) === 'too-slow') {
      stop('too-slow');
      return;
    }
    fray.advance(dtMs / 1000);
    draw();
    writeFrayState();
    frames += 1;
    stage.dataset.heroFrames = String(frames);
    if (frames === 1) performance.mark('weave:first-live-frame');
    schedule();
  }

  // rAF keeps firing in a hidden tab, so the loop checks document.hidden itself.
  function schedule() {
    if (!rafId && !stopped && !paused && onScreen && !document.hidden) rafId = requestAnimationFrame(frame);
  }

  function unschedule() {
    if (rafId) cancelAnimationFrame(rafId);
    rafId = 0;
    last = 0;
  }

  stage.append(canvas);
  stage.classList.add('is-live');
  showLiveControls(controls, [pause], true);

  // Every resize redraws the current pose at once, paused or not: a WebGL buffer resize clears the canvas.
  const resize = () => {
    const width = stage.clientWidth;
    const height = stage.clientHeight;
    if (!width || !height) return;
    const ratio = Math.min(window.devicePixelRatio || 1, S.MAX_PIXEL_RATIO);
    if (renderer.getPixelRatio() !== ratio) renderer.setPixelRatio(ratio);
    renderer.setSize(width, height, false);
    S.fitCamera(camera, width / height, CORNER_BOUNDS);
    draw();
  };
  const sizeObserver = new ResizeObserver(resize);
  sizeObserver.observe(stage);
  resize();

  // The pointer stirs the threads: its client point is cast through the camera onto the strand plane. Leaving the
  // canvas (which fills the stage) clears the stir. Neither listener exists at ?pose=rest.
  const ray = new THREE.Raycaster();
  const ndc = new THREE.Vector2();
  const strandPlane = new THREE.Plane(new THREE.Vector3(0, 0, 1), -STRAND_Z);
  const hit = new THREE.Vector3();
  const onStir = (event) => {
    const r = canvas.getBoundingClientRect();
    ndc.set(((event.clientX - r.left) / r.width) * 2 - 1, 1 - ((event.clientY - r.top) / r.height) * 2);
    ray.setFromCamera(ndc, camera);
    if (ray.ray.intersectPlane(strandPlane, hit)) fray.setStir([hit.x, hit.y, STRAND_Z]);
  };
  const onStirLeave = () => fray.setStir(null);
  if (!hooks.rest) {
    canvas.addEventListener('pointermove', onStir);
    canvas.addEventListener('pointerleave', onStirLeave);
  }
  const onContextLost = (event) => {
    event.preventDefault();
    stop('context-lost');
  };
  canvas.addEventListener('webglcontextlost', onContextLost);

  // Pause freezes the threads: no frame is scheduled and the sim does not advance; the pose is drawn once.
  const onPause = () => {
    paused = !paused;
    setPaused(pause, paused);
    if (paused) {
      unschedule();
      draw();
    } else {
      schedule();
    }
  };
  pause.addEventListener('click', onPause);

  // Off screen or in a hidden tab, the pending frame is cancelled too, so none runs.
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

  // The only teardown: the watchdog, a lost context and the hook all come here, once. It releases the frame, both
  // observers and every listener, hides Pause and its row, removes the canvas, is-live and data-fray-state, then
  // disposes every geometry, material and texture and the renderer; the still is written even if that throws.
  function stop(reason) {
    if (stopped) return;
    stopped = true;
    unschedule();
    sizeObserver.disconnect();
    visibility.disconnect();
    document.removeEventListener('visibilitychange', onVisibilityChange);
    pause.removeEventListener('click', onPause);
    showLiveControls(controls, [pause], false);
    canvas.removeEventListener('pointermove', onStir);
    canvas.removeEventListener('pointerleave', onStirLeave);
    canvas.removeEventListener('webglcontextlost', onContextLost);
    canvas.remove();
    stage.classList.remove('is-live');
    delete stage.dataset.frayState;
    try {
      const owned = new Set();
      scene.traverse((o) => {
        if (o.geometry) owned.add(o.geometry);
        const materials = Array.isArray(o.material) ? o.material : [o.material];
        for (const m of materials) {
          if (!m) continue;
          owned.add(m);
          for (const key of ['map', 'normalMap']) if (m[key]) owned.add(m[key]);
        }
      });
      owned.forEach((x) => x.dispose());
      renderer.dispose();
      // An already-lost context has no WEBGL_lose_context to call, and Three would warn.
      if (!renderer.getContext().isContextLost()) renderer.forceContextLoss();
    } finally {
      setHeroState('still', reason);
    }
  }

  stage.__weaveHelp = {
    fray,
    stop,
    project([x, y, z]) {
      camera.updateMatrixWorld();
      const v = new THREE.Vector3(x, y, z).project(camera);
      const r = canvas.getBoundingClientRect();
      return [r.left + ((v.x + 1) / 2) * r.width, r.top + ((1 - v.y) / 2) * r.height];
    },
    edge,
    needle,
    spool,
    get fringe() {
      return { paints: fringePaints, textureVersion: fringeTexture.version, materialVersion: fringeMaterial.version,
        threshold: fringeMaterial.alphaTest };
    },
  };
  writeFrayState();
  setHeroState('live', 'ok');
  schedule();
}

startHero();
