// The live 3D world: the GLB's pieces placed from world.json (or junction.json), drawn unlit with fog.
// Light is baked into vertex and instance colours by the Blender build; here we add motion: breathing flames,
// lights drifting along their paths, flowing water, and ferns that part around the pointer.
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { fitVerticalFov } from './rig.js';
import { BOARD as MAP_BOARD, PAPER, drawMap, canvasPainter } from './kbmap.js';

const FOG_COLOR = 0x183740;
const FOG_DENSITY = 0.03;
const BOARD = { tail: 0.10, length: 0.457, width: 0.14, thick: 0.019 };
const AMBER = new THREE.Color(0xffb23f);
const PROPS = ['Water', 'Foam', 'Rock0', 'Rock1', 'Rock2', 'Rock3', 'Rock4', 'Tent', 'TentDoor', 'Rack', 'Key', 'Crate',
  'LogSeat', 'LanternPole', 'Kiosk', 'KioskMap', 'LaunchBoard', 'Tag', 'TagLit'];
const FLOWS = { path: { spacing: 1.6, speed: 0.7 }, stream: { spacing: 0.75, speed: 0.6 },
  flight: { spacing: 0.45, speed: 0.9 }, default: { spacing: 1.5, speed: 0.7 } };
const HOVER_RADIUS = 2.6;
const HOVER_MAX = THREE.MathUtils.degToRad(42);
const REFERENCE_ASPECT = 16 / 9;
const TORCH_REACH = 45;
const TONE = 'aces';
const TONE_EXPOSURE = 1.15;
const LABEL_REACH = 30;

export async function loadWorld(base, which = 'world') {
  const [gltf, layout] = await Promise.all([
    new GLTFLoader().loadAsync(`${base}blazeahead.glb`),
    fetch(`${base}${which}.json`).then((res) => {
      if (!res.ok) throw new Error(`${which}.json: HTTP ${res.status}`);
      return res.json();
    }),
  ]);
  return { gltf, layout, which };
}

function glowTexture(size = 128) {
  const c = document.createElement('canvas');
  c.width = c.height = size;
  const g = c.getContext('2d');
  const grad = g.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
  grad.addColorStop(0, 'rgba(255,255,255,1)');
  grad.addColorStop(0.18, 'rgba(255,255,255,0.85)');
  grad.addColorStop(0.45, 'rgba(255,255,255,0.22)');
  grad.addColorStop(1, 'rgba(255,255,255,0)');
  g.fillStyle = grad;
  g.fillRect(0, 0, size, size);
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  return tex;
}

function streakTexture() {
  const c = document.createElement('canvas');
  c.width = 64;
  c.height = 256;
  const g = c.getContext('2d');
  g.fillStyle = '#000';
  g.fillRect(0, 0, 64, 256);
  let seed = 7;
  const rand = () => {
    seed = (seed * 16807) % 2147483647;
    return seed / 2147483647;
  };
  for (let i = 0; i < 26; i++) {
    const x = rand() * 64;
    const y = rand() * 256;
    const len = 20 + rand() * 60;
    const grad = g.createLinearGradient(0, y, 0, y + len);
    grad.addColorStop(0, 'rgba(140,199,214,0)');
    grad.addColorStop(0.5, `rgba(140,199,214,${0.35 + rand() * 0.4})`);
    grad.addColorStop(1, 'rgba(140,199,214,0)');
    g.fillStyle = grad;
    g.fillRect(x, y, 1 + rand() * 2, len);
  }
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
  tex.repeat.set(1, 3);
  return tex;
}

// Text drawn on a canvas and shown on a small plane (signpost words, prop lettering).
function makeLabel(text, { capHeight, maxWidth, color }) {
  const px = 96;
  const c = document.createElement('canvas');
  const g = c.getContext('2d');
  const font = `600 ${px}px Fraunces, Georgia, serif`;
  g.font = font;
  const w = Math.ceil(g.measureText(text).width) + 24;
  c.width = Math.max(32, w);
  c.height = Math.round(px * 1.35);
  g.font = font;
  g.fillStyle = '#fff';
  g.textAlign = 'center';
  g.textBaseline = 'middle';
  g.fillText(text, c.width / 2, c.height / 2 + px * 0.04);
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.anisotropy = 4;
  let height = capHeight * 1.9;
  let width = height * (c.width / c.height);
  if (width > maxWidth) {
    height *= maxWidth / width;
    width = maxWidth;
  }
  const mat = new THREE.MeshBasicMaterial({ map: tex, transparent: true, depthWrite: false, color, fog: true,
    polygonOffset: true, polygonOffsetFactor: -2, polygonOffsetUnits: -2 });
  return new THREE.Mesh(new THREE.PlaneGeometry(width, height), mat);
}

class Polyline {
  constructor(points) {
    this.pts = points.map((p) => new THREE.Vector3(p[0], p[1], p[2]));
    this.cum = [0];
    for (let i = 1; i < this.pts.length; i++) this.cum.push(this.cum[i - 1] + this.pts[i].distanceTo(this.pts[i - 1]));
    this.length = this.cum[this.cum.length - 1];
  }

  at(s, out) {
    const L = this.length;
    let d = ((s % L) + L) % L;
    let lo = 0;
    let hi = this.cum.length - 1;
    while (hi - lo > 1) {
      const mid = (lo + hi) >> 1;
      if (this.cum[mid] < d) lo = mid;
      else hi = mid;
    }
    const seg = this.cum[hi] - this.cum[lo] || 1;
    return out.lerpVectors(this.pts[lo], this.pts[hi], (d - this.cum[lo]) / seg);
  }
}

export class WorldView {
  constructor(canvas, assets, { label = () => '', rocks = [], tone = TONE, exposure = TONE_EXPOSURE } = {}) {
    const { gltf, layout } = assets;
    this.layout = layout;
    this.rockLabels = rocks;
    this.canvas = canvas;
    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: true, powerPreference: 'high-performance' });
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.renderer.toneMapping = { none: THREE.NoToneMapping, aces: THREE.ACESFilmicToneMapping,
      agx: THREE.AgXToneMapping }[tone] ?? THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = exposure;
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(FOG_COLOR);
    this.scene.fog = new THREE.FogExp2(FOG_COLOR, FOG_DENSITY);
    this.camera = new THREE.PerspectiveCamera(40, REFERENCE_ASPECT, 0.05, 220);
    this.hfov = 60;
    this.time = 0;
    this.disposables = [];
    this.instanced = [];
    this.torches = [];
    this.flows = [];
    this.glows = [];
    this.hoverActive = 0;
    this.pointerPoint = null;
    this.labels = [];
    this.raycaster = new THREE.Raycaster();

    const nodes = {};
    gltf.scene.traverse((o) => {
      if (o.isMesh) nodes[o.name] = o;
    });
    this.nodes = nodes;
    const base = new THREE.MeshBasicMaterial({ vertexColors: true, side: THREE.DoubleSide, fog: true });
    this.disposables.push(base);

    // the ground (a dark apron under the corridor's edge, then the baked ground itself)
    const apron = new THREE.Mesh(new THREE.PlaneGeometry(600, 600), new THREE.MeshBasicMaterial({ color: 0x0a120e, fog: true }));
    apron.rotation.x = -Math.PI / 2;
    apron.position.y = -0.75;
    this.scene.add(apron);
    this.disposables.push(apron.geometry, apron.material);
    const groundName = assets.which === 'junction' ? 'JunctionGround' : 'Ground';
    if (nodes[groundName]) {
      this.ground = new THREE.Mesh(nodes[groundName].geometry, base);
      this.scene.add(this.ground);
    }

    // shared pieces, instanced from the layout
    const m = new THREE.Matrix4();
    const p = new THREE.Vector3();
    const q = new THREE.Quaternion();
    const s = new THREE.Vector3();
    const col = new THREE.Color();
    this.ferns = [];
    for (const group of layout.instances) {
      const src = nodes[group.mesh];
      if (!src) continue;
      const d = group.data;
      const n = d.length / 13;
      const im = new THREE.InstancedMesh(src.geometry, base, n);
      for (let i = 0; i < n; i++) {
        const o = i * 13;
        p.set(d[o], d[o + 1], d[o + 2]);
        q.set(d[o + 3], d[o + 4], d[o + 5], d[o + 6]);
        s.set(d[o + 7], d[o + 8], d[o + 9]);
        m.compose(p, q, s);
        im.setMatrixAt(i, m);
        col.setRGB(d[o + 10], d[o + 11], d[o + 12]);
        im.setColorAt(i, col);
      }
      im.instanceMatrix.needsUpdate = true;
      if (im.instanceColor) im.instanceColor.needsUpdate = true;
      im.computeBoundingSphere();
      im.userData = { chunk: group.chunk, mesh: group.mesh, data: d };
      this.scene.add(im);
      this.instanced.push(im);
      if (group.mesh.startsWith('Fern')) this.ferns.push(im);
    }
    this.buildFernIndex();

    // props exported in place
    this.props = {};
    const tagGlow = base.clone();
    tagGlow.color = new THREE.Color(1.5, 1.5, 1.5);
    const foam = base.clone();
    foam.transparent = true;
    foam.opacity = 0.8;
    foam.depthWrite = false;
    this.foamMaterial = foam;
    this.disposables.push(tagGlow, foam);
    for (const name of PROPS) {
      const src = nodes[name];
      if (!src || assets.which === 'junction') continue;
      const mat = name === 'Foam' ? foam : (name === 'TagLit' || name === 'TentDoor') ? tagGlow : base;
      const mesh = new THREE.Mesh(src.geometry, mat);
      mesh.name = name;
      this.scene.add(mesh);
      this.props[name] = mesh;
    }
    if (this.props.Water && this.props.Water.geometry.attributes.uv) {
      const streaks = streakTexture();
      this.streaks = streaks;
      const overlay = new THREE.Mesh(this.props.Water.geometry, new THREE.MeshBasicMaterial({
        map: streaks, transparent: true, opacity: 0.55, blending: THREE.AdditiveBlending, depthWrite: false, fog: true,
        polygonOffset: true, polygonOffsetFactor: -1, polygonOffsetUnits: -1 }));
      this.scene.add(overlay);
      this.disposables.push(streaks, overlay.material);
    }

    // torches: the stylized flame with its blue crystal, breathing, always turned to the viewer
    const glow = glowTexture();
    this.glowTexture = glow;
    this.disposables.push(glow);
    const flameMat = new THREE.MeshBasicMaterial({ vertexColors: true, side: THREE.DoubleSide, fog: true,
      color: new THREE.Color(1.8, 1.8, 1.8) });
    const crystalMat = new THREE.MeshBasicMaterial({ vertexColors: true, side: THREE.DoubleSide, fog: true,
      color: new THREE.Color(1.5, 1.5, 1.5) });
    this.disposables.push(flameMat, crystalMat);
    let seed = 1;
    for (const t of layout.torches) {
      const g = new THREE.Group();
      g.position.set(...t.base);
      g.scale.setScalar(t.scale);
      const lean = new THREE.Group();
      g.add(lean);
      const shells = ['FlameOuter', 'FlameMid', 'FlameInner'].filter((k) => nodes[k])
        .map((k) => new THREE.Mesh(nodes[k].geometry, flameMat));
      shells.forEach((mesh) => lean.add(mesh));
      if (nodes.Crystal) g.add(new THREE.Mesh(nodes.Crystal.geometry, crystalMat));
      this.scene.add(g);
      const sprite = this.addGlow(t.pos, 1.9 * t.scale * 2.2, 0xffa340, 0.85);
      seed = (seed * 48271) % 2147483647;
      this.torches.push({ group: g, lean, shells, glow: sprite, phase: (seed / 2147483647) * 100, leanNow: 0, leanTo: 0 });
    }
    for (const l of layout.lanterns || []) this.addGlow(l.pos, 0.75, 0xffb45a, 0.8);
    if (layout.props && layout.props.tentGlow) this.addGlow(layout.props.tentGlow, 1.7, 0xffa24a, 0.55);

    // the lights, drifting along their paths (one per prompt, as the tour says)
    for (const [name, pts] of Object.entries(layout.flows || {})) {
      if (!pts || pts.length < 2) continue;
      const cfg = FLOWS[name] || FLOWS.default;
      const line = new Polyline(pts);
      const count = Math.max(4, Math.floor(line.length / cfg.spacing));
      const geo = new THREE.BufferGeometry();
      geo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(count * 3), 3));
      geo.setAttribute('color', new THREE.BufferAttribute(new Float32Array(count * 3), 3));
      const mat = new THREE.PointsMaterial({ size: name === 'flight' ? 0.9 : 0.62, map: glow, vertexColors: true, transparent: true,
        depthWrite: false, blending: THREE.AdditiveBlending, sizeAttenuation: true, fog: true });
      const points = new THREE.Points(geo, mat);
      points.frustumCulled = false;
      this.scene.add(points);
      this.disposables.push(geo, mat);
      this.flows.push({ name, line, count, cfg, points });
    }

    // stars over the launch clearing
    if (layout.sky) {
      const n = 420;
      const arr = new Float32Array(n * 3);
      let r = 11;
      const rand = () => {
        r = (r * 16807) % 2147483647;
        return r / 2147483647;
      };
      const [cx, , cz] = layout.sky.centre;
      for (let i = 0; i < n; i++) {
        const az = rand() * Math.PI * 2;
        const el = THREE.MathUtils.degToRad(18 + rand() * 67);
        arr.set([cx + 55 * Math.cos(el) * Math.cos(az), 55 * Math.sin(el), cz + 55 * Math.cos(el) * Math.sin(az)], i * 3);
      }
      const geo = new THREE.BufferGeometry();
      geo.setAttribute('position', new THREE.BufferAttribute(arr, 3));
      const mat = new THREE.PointsMaterial({ color: 0xdde8ff, size: 1.8, sizeAttenuation: false, fog: false });
      this.scene.add(new THREE.Points(geo, mat));
      this.disposables.push(geo, mat);
    }

    // words: on every signpost board, and the lettering on the props
    this.signs = this.collectSigns(layout);
    const burn = new THREE.Color(0x2a1a0f);
    for (const sg of this.signs) {
      const text = label(sg.label);
      if (!text) continue;
      const light = sg.light || [1, 1, 1];
      const c = burn.clone().multiply(new THREE.Color(light[0], light[1], light[2]));
      const mesh = makeLabel(text, { capHeight: 0.05, maxWidth: 0.33, color: c });
      const nrm = new THREE.Vector3(...sg.n).normalize();
      mesh.position.set(...sg.board).addScaledVector(nrm, BOARD.thick / 2 + 0.002);
      mesh.lookAt(mesh.position.clone().add(nrm));
      this.scene.add(mesh);
      this.labels.push(mesh);
      this.disposables.push(mesh.geometry, mesh.material, mesh.material.map);
    }
    for (const lb of layout.labels || []) {
      const mesh = makeLabel(lb.text, { capHeight: lb.size * 0.72, maxWidth: lb.maxWidth,
        color: new THREE.Color(lb.color[0], lb.color[1], lb.color[2]) });
      const nrm = new THREE.Vector3(...lb.normal).normalize();
      mesh.position.set(...lb.pos).addScaledVector(nrm, 0.004);
      mesh.lookAt(mesh.position.clone().add(nrm));
      this.scene.add(mesh);
      this.labels.push(mesh);
      this.disposables.push(mesh.geometry, mesh.material, mesh.material.map);
    }

    if (layout.props && layout.props.kioskBoard && assets.which !== 'junction') {
      try {
        this.buildBoard(layout.props.kioskBoard);
      } catch (err) {
        console.warn('blazeAhead: the kiosk map could not be drawn in 3D; the card and the unfolded map still work.', err);
      }
    }

    this.chunks = layout.chunks || [];
    this.lastChunkCheck = new THREE.Vector3(1e9, 0, 0);
  }

  addGlow(pos, size, color, opacity) {
    const mat = new THREE.SpriteMaterial({ map: this.glowTexture, color, transparent: true, opacity,
      blending: THREE.AdditiveBlending, depthWrite: false, fog: true });
    const sprite = new THREE.Sprite(mat);
    sprite.position.set(...pos);
    sprite.scale.setScalar(size);
    this.scene.add(sprite);
    this.disposables.push(mat);
    this.glows.push({ sprite, base: opacity, phase: this.glows.length * 1.7 });
    return sprite;
  }

  collectSigns(layout) {
    const out = [];
    if (layout.trailhead) out.push({ ...layout.trailhead.sign, view: 'trailhead', key: 'tour' });
    for (const stop of layout.stops || []) {
      for (const side of ['left', 'right']) out.push({ ...stop.signs[side], view: stop.id, key: side });
    }
    if (layout.junction) for (const b of layout.junction.boards) out.push({ ...b, view: 'junction', key: b.key });
    return out;
  }

  // The knowledge kiosk's map board: a panel just in front of the paper, carrying the trail map as a canvas texture,
  // tinted by the baked lantern light (a grid of vertex colours, row by row from the top-left, as PlaneGeometry
  // orders its vertices).
  buildBoard(b) {
    const canvas = document.createElement('canvas');
    canvas.width = 2048;
    canvas.height = Math.round((2048 * MAP_BOARD.h) / MAP_BOARD.w);
    // blank paper until the map is painted (and if it never is)
    const g = canvas.getContext('2d');
    g.fillStyle = PAPER;
    g.fillRect(0, 0, canvas.width, canvas.height);
    const tex = new THREE.CanvasTexture(canvas);
    tex.colorSpace = THREE.SRGBColorSpace;
    tex.anisotropy = this.renderer.capabilities.getMaxAnisotropy();
    const [cols, rows] = b.grid;
    const geo = new THREE.PlaneGeometry(b.size[0], b.size[1], cols - 1, rows - 1);
    const colors = new Float32Array(cols * rows * 3);
    b.light.forEach((c, i) => colors.set(c, i * 3));
    geo.setAttribute('color', new THREE.BufferAttribute(colors, 3));
    const mat = new THREE.MeshBasicMaterial({ map: tex, vertexColors: true, fog: true,
      polygonOffset: true, polygonOffsetFactor: -1, polygonOffsetUnits: -1 });
    const mesh = new THREE.Mesh(geo, mat);
    const basis = new THREE.Matrix4().makeBasis(new THREE.Vector3(...b.right), new THREE.Vector3(...b.up),
      new THREE.Vector3(...b.normal));
    mesh.quaternion.setFromRotationMatrix(basis);
    mesh.position.set(...b.centre);
    this.scene.add(mesh);
    this.board = { mesh, canvas, tex, laid: null, focus: null, draws: 0 };
    this.disposables.push(geo, mat, tex);
  }

  // `draws` counts real paints: the board already showing this map with this trail lit is left as it is
  paintBoard(laid, focus = null) {
    const bd = this.board;
    if (!bd || !laid) return false;
    if (bd.laid === laid && bd.focus === focus) return true;
    const ctx = bd.canvas.getContext('2d');
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, bd.canvas.width, bd.canvas.height);
    drawMap(canvasPainter(ctx, bd.canvas.width / MAP_BOARD.w), laid, { focus });
    bd.tex.needsUpdate = true;
    bd.laid = laid;
    bd.focus = focus;
    bd.draws += 1;
    return true;
  }

  boardAt(ndcX, ndcY) {
    return Boolean(this.board) && this.toRay(ndcX, ndcY).intersectObject(this.board.mesh, false).length > 0;
  }

  buildFernIndex() {
    this.fernCells = new Map();
    this.fernState = new Map();
    this.ferns.forEach((im, mi) => {
      const d = im.userData.data;
      for (let i = 0; i < d.length / 13; i++) {
        const x = d[i * 13];
        const z = d[i * 13 + 2];
        const key = `${Math.floor(x / 2)},${Math.floor(z / 2)}`;
        if (!this.fernCells.has(key)) this.fernCells.set(key, []);
        this.fernCells.get(key).push([mi, i, x, z]);
      }
    });
  }

  // ---- camera
  fovFor(hfov, aspect) {
    return fitVerticalFov(hfov, Math.min(aspect, REFERENCE_ASPECT));
  }

  resize(width, height, dpr) {
    this.renderer.setPixelRatio(dpr);
    this.renderer.setSize(width, height, false);
    this.camera.aspect = width / height;
    this.camera.fov = this.fovFor(this.hfov, this.camera.aspect);
    this.camera.updateProjectionMatrix();
  }

  setPose(position, target, hfov) {
    this.camera.position.set(position[0], position[1], position[2]);
    this.camera.lookAt(target[0], target[1], target[2]);
    if (hfov && hfov !== this.hfov) {
      this.hfov = hfov;
      this.camera.fov = this.fovFor(hfov, this.camera.aspect);
      this.camera.updateProjectionMatrix();
    }
    this.camera.updateMatrixWorld();
  }

  showView(id) {
    const v = this.layout.views[id];
    if (!v) return false;
    this.viewId = id;
    this.setPose(v.position, v.target, v.hfov);
    this.updateChunks(true);
    return true;
  }

  updateChunks(force = false) {
    const cam = this.camera.position;
    if (!force && cam.distanceTo(this.lastChunkCheck) < 0.75) return;
    this.lastChunkCheck.copy(cam);
    const visible = new Set();
    for (const c of this.chunks) {
      const dx = c.centre[0] - cam.x;
      const dz = c.centre[2] - cam.z;
      if (Math.hypot(dx, dz) < c.radius + 48) visible.add(c.id);
    }
    for (const im of this.instanced) im.visible = !this.chunks.length || visible.has(im.userData.chunk);
    // far torches and words are lost in the fog anyway: skip their draw calls
    for (const t of this.torches) {
      const near = t.group.position.distanceTo(cam) < TORCH_REACH;
      t.group.visible = near;
      t.glow.visible = near;
    }
    for (const mesh of this.labels) mesh.visible = mesh.position.distanceTo(cam) < LABEL_REACH;
  }

  // ---- pointer
  toRay(ndcX, ndcY) {
    this.raycaster.setFromCamera({ x: ndcX, y: ndcY }, this.camera);
    return this.raycaster;
  }

  pointer(ndcX, ndcY) {
    if (!this.ground) return;
    const hit = this.toRay(ndcX, ndcY).intersectObject(this.ground, false)[0];
    this.pointerPoint = hit && hit.distance < 25 ? hit.point.clone() : null;
    for (const t of this.torches) {
      t.leanTo = 0;
      if (!this.pointerPoint) continue;
      const dx = this.pointerPoint.x - t.group.position.x;
      const dz = this.pointerPoint.z - t.group.position.z;
      const d = Math.hypot(dx, dz);
      if (d < 4) {
        // lean toward the pointer, in screen terms: sideways relative to the viewer
        const right = new THREE.Vector3().setFromMatrixColumn(this.camera.matrixWorld, 0);
        const side = Math.sign(dx * right.x + dz * right.z) || 0;
        t.leanTo = -side * THREE.MathUtils.degToRad(12) * (1 - d / 4);
      }
    }
  }

  pointerLeave() {
    this.pointerPoint = null;
    for (const t of this.torches) t.leanTo = 0;
  }

  rockAt(ndcX, ndcY) {
    const rocks = [0, 1, 2, 3, 4].map((i) => this.props[`Rock${i}`]).filter(Boolean);
    if (!rocks.length) return null;
    const hit = this.toRay(ndcX, ndcY).intersectObjects(rocks, false)[0];
    if (!hit) return null;
    return this.rockLabels[Number(hit.object.name.slice(4))] || null;
  }

  // Screen box (page pixels) of a signpost board in a view, for the HTML buttons laid over it.
  boxFor(viewId, key) {
    const sg = this.signs.find((s) => s.view === viewId && s.key === key);
    if (!sg) return null;
    const rect = this.canvas.getBoundingClientRect();
    const c = new THREE.Vector3(...sg.centre);
    const dir = new THREE.Vector3(...sg.dir).normalize();
    const xs = [];
    const ys = [];
    for (const along of [-BOARD.tail, BOARD.length - BOARD.tail]) {
      for (const up of [-BOARD.width / 2, BOARD.width / 2]) {
        const v = c.clone().addScaledVector(dir, along);
        v.y += up;
        v.project(this.camera);
        if (v.z > 1) return null;
        xs.push(rect.left + (v.x + 1) / 2 * rect.width);
        ys.push(rect.top + (1 - v.y) / 2 * rect.height);
      }
    }
    const pad = 6;
    return [Math.min(...xs) - pad, Math.min(...ys) - pad, Math.max(...xs) + pad, Math.max(...ys) + pad];
  }

  // ---- motion
  update(dt, animate = true) {
    if (animate) this.time += dt;
    const t = this.time;
    const cam = this.camera.position;
    for (const tr of this.torches) {
      const k = tr.phase;
      tr.group.rotation.y = Math.atan2(cam.x - tr.group.position.x, cam.z - tr.group.position.z);
      tr.shells.forEach((mesh, i) => {
        mesh.scale.y = 1 + 0.06 * Math.sin(t * (7.3 + i * 1.9) + k + i) + 0.035 * Math.sin(t * (17 + i * 3) + k * 1.7);
        mesh.scale.x = 1 + 0.03 * Math.sin(t * (5.1 + i) + k * 0.7);
        mesh.rotation.z = 0.035 * Math.sin(t * (4.3 + i * 1.3) + k * 0.5);
      });
      tr.leanNow += (tr.leanTo - tr.leanNow) * Math.min(1, dt * 5);
      tr.lean.rotation.z = tr.leanNow;
      tr.glow.material.opacity = 0.72 + 0.12 * Math.sin(t * 9.1 + k) + 0.06 * Math.sin(t * 23 + k * 2);
    }
    for (const g of this.glows) {
      if (this.torches.some((tr) => tr.glow === g.sprite)) continue;
      g.sprite.material.opacity = g.base * (0.9 + 0.1 * Math.sin(t * 3.1 + g.phase));
    }
    const tmp = new THREE.Vector3();
    for (const f of this.flows) {
      const pos = f.points.geometry.attributes.position;
      const colr = f.points.geometry.attributes.color;
      const L = f.line.length;
      for (let i = 0; i < f.count; i++) {
        const u = (i * (L / f.count) + t * f.cfg.speed) % L;
        f.line.at(u, tmp);
        tmp.y += 0.06 * Math.sin(t * 1.3 + i * 1.7);
        pos.setXYZ(i, tmp.x, tmp.y, tmp.z);
        const ends = Math.min(1, u / 1.5, (L - u) / 1.5);
        const near = THREE.MathUtils.clamp((tmp.distanceTo(cam) - 2.2) / 1.6, 0, 1);
        const k = 1.7 * Math.max(0, ends) * near * (0.85 + 0.15 * Math.sin(t * 2.3 + i));
        colr.setXYZ(i, AMBER.r * k, AMBER.g * k, AMBER.b * k);
      }
      pos.needsUpdate = true;
      colr.needsUpdate = true;
    }
    if (this.streaks) this.streaks.offset.y -= dt * 0.28;
    if (this.foamMaterial) this.foamMaterial.opacity = 0.7 + 0.2 * Math.sin(t * 1.9);
    this.updateFerns(dt);
    this.updateChunks();
  }

  updateFerns(dt) {
    const p = this.pointerPoint;
    const want = new Map();
    if (p) {
      const cx = Math.floor(p.x / 2);
      const cz = Math.floor(p.z / 2);
      for (let gx = cx - 2; gx <= cx + 2; gx++) {
        for (let gz = cz - 2; gz <= cz + 2; gz++) {
          for (const [mi, i, x, z] of this.fernCells.get(`${gx},${gz}`) || []) {
            const dx = x - p.x;
            const dz = z - p.z;
            const d = Math.hypot(dx, dz);
            if (d < HOVER_RADIUS && d > 1e-3) {
              const a = HOVER_MAX * (1 - d / HOVER_RADIUS);
              want.set(`${mi}:${i}`, [mi, i, (dx / d) * a, (dz / d) * a]);
            }
          }
        }
      }
    }
    for (const [key, v] of want) {
      if (!this.fernState.has(key)) this.fernState.set(key, { mi: v[0], i: v[1], x: 0, z: 0 });
    }
    const m = new THREE.Matrix4();
    const pos = new THREE.Vector3();
    const q = new THREE.Quaternion();
    const tilt = new THREE.Quaternion();
    const scl = new THREE.Vector3();
    const axis = new THREE.Vector3();
    const touched = new Set();
    let active = 0;
    for (const [key, st] of this.fernState) {
      const target = want.get(key);
      const tx = target ? target[2] : 0;
      const tz = target ? target[3] : 0;
      const k = Math.min(1, dt * 7);
      st.x += (tx - st.x) * k;
      st.z += (tz - st.z) * k;
      const im = this.ferns[st.mi];
      const d = im.userData.data;
      const o = st.i * 13;
      pos.set(d[o], d[o + 1], d[o + 2]);
      q.set(d[o + 3], d[o + 4], d[o + 5], d[o + 6]);
      scl.set(d[o + 7], d[o + 8], d[o + 9]);
      const ang = Math.hypot(st.x, st.z);
      if (ang > 1e-4) {
        // tip the fern's up axis toward (x, z): rotate about the horizontal axis perpendicular to that direction
        axis.set(st.z, 0, -st.x).normalize();
        tilt.setFromAxisAngle(axis, ang);
        q.premultiply(tilt);
      }
      m.compose(pos, q, scl);
      im.setMatrixAt(st.i, m);
      touched.add(im);
      if (!target && ang < 0.002) this.fernState.delete(key);
      else active += 1;
    }
    for (const im of touched) im.instanceMatrix.needsUpdate = true;
    this.hoverActive = active;
  }

  render() {
    this.renderer.render(this.scene, this.camera);
  }

  stats() {
    this.render();
    const { triangles, calls } = this.renderer.info.render;
    return { triangles, calls };
  }

  dispose() {
    for (const d of this.disposables) {
      if (d && typeof d.dispose === 'function') d.dispose();
    }
    this.renderer.dispose();
  }
}
