// WEAVE's Three.js scene: the renderer, lights, fabric material and camera fit that #8-#22 reuse, and
// buildQuilt, which builds the hanging quilt from LAYOUT and #6's painters. Importing it creates nothing.
import * as THREE from 'three';
import { makeCanvas, paintSashing, paintShadow, paintWeaveNormal, paintWood, sashingSize } from './fabric.js';
import { foldZ, LAYOUT, puffZ, slotCentre } from './layout.js';
import { rngFor } from './random.js';
import { faceKind, paintFace, paintTile } from './tiles.js';

// Coalesce's cap (coalesce/public/js/hero.js).
export const MAX_PIXEL_RATIO = 1.75;

// alpha: true is load-bearing: the page's linen shows through the cleared canvas, so a canvas resized but not
// yet redrawn reads as paper, not black, and the paused-resize redraw test can tell the two apart (U6).
export function createRenderer(canvas) {
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
  renderer.toneMapping = THREE.NeutralToneMapping;
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.setClearColor(0x000000, 0);
  return renderer;
}

// A soft sky/floor fill and a warm key from the upper left, in front of the quilt.
export function addLights(scene) {
  const hemi = new THREE.HemisphereLight(0xfff8ee, 0xb8ad9a, 1.4);
  const key = new THREE.DirectionalLight(0xffe2c0, 1.6);
  key.position.set(-3, 4, 5);
  scene.add(hemi, key);
  return { hemi, key };
}

// The weave's repeats per scene unit, shared by the blocks (1 unit wide) and the sashing's clone.
export const WEAVE_REPEAT = 3;

let weaveNormal = null;
// The shared weave normal map, painted on first use.
export function weaveNormalMap() {
  if (!weaveNormal) {
    const canvas = makeCanvas(512);
    paintWeaveNormal(canvas);
    weaveNormal = new THREE.CanvasTexture(canvas);
    weaveNormal.wrapS = THREE.RepeatWrapping;
    weaveNormal.wrapT = THREE.RepeatWrapping;
    weaveNormal.repeat.set(WEAVE_REPEAT, WEAVE_REPEAT);
    weaveNormal.colorSpace = THREE.NoColorSpace;
  }
  return weaveNormal;
}

// Cotton: rough, with a warm sheen. The face is colour (sRGB) and the normal map is data (no colour space).
// `transparent` is for the parts #8 fades; it is set at build, since toggling it later recompiles the shader.
export function fabricMaterial({ map, normalMap = weaveNormalMap(), transparent = false } = {}) {
  if (map) map.colorSpace = THREE.SRGBColorSpace;
  normalMap.colorSpace = THREE.NoColorSpace;
  return new THREE.MeshPhysicalMaterial({
    map: map ?? null,
    normalMap,
    transparent,
    roughness: 0.9,
    sheen: 1,
    sheenRoughness: 0.8,
    sheenColor: new THREE.Color('#FFF1DC'),
  });
}

// What the camera must always see: the quilt with its rod and caps, unioned with the tile grid, plus a margin
// for the sway, the pointer tilt and #8's tile lift, so #8 needs no camera move (D2).
const rodEnd = LAYOUT.rod.halfLength + LAYOUT.rod.capRadius;
export const DEFAULT_BOUNDS = Object.freeze({
  minX: -Math.max(rodEnd, LAYOUT.tilesW / 2),
  maxX: Math.max(rodEnd, LAYOUT.tilesW / 2),
  minY: -Math.max(LAYOUT.quiltH, LAYOUT.tilesH) / 2,
  maxY: Math.max(LAYOUT.rod.y + LAYOUT.rod.capRadius, LAYOUT.tilesH / 2),
  margin: 0.3,
});

// Fits a perspective camera (vertical fov in degrees) so `bounds` widened by its margin just fills the view at
// z = 0, looking straight at the bounds' centre, which is kept in camera.userData.target.
export function fitCamera(camera, aspect, bounds = DEFAULT_BOUNDS) {
  const { minX, maxX, minY, maxY, margin = 0 } = bounds;
  const cx = (minX + maxX) / 2;
  const cy = (minY + maxY) / 2;
  const halfW = (maxX - minX) / 2 + margin;
  const halfH = (maxY - minY) / 2 + margin;
  const t = Math.tan((camera.fov * Math.PI) / 360);
  const dist = Math.max(halfH / t, halfW / (aspect * t));
  camera.position.set(cx, cy, dist);
  camera.up.set(0, 1, 0);
  camera.lookAt(cx, cy, 0);
  camera.aspect = aspect;
  camera.near = 0.1;
  camera.far = dist + 10;
  camera.updateProjectionMatrix();
  camera.userData.target = new THREE.Vector3(cx, cy, 0);
  return camera;
}

// --- The quilt. ---

const SEGMENTS = LAYOUT.segments;
const TILT_MAX = (LAYOUT.maxTiltDeg * Math.PI) / 180;
// A planned block sits this far above the sashing, so its tilted corners never z-fight the muslin under them.
const PLANNED_LIFT = 0.01;
// A block's tile face sits this far behind it, facing the other way, so the flip reveals it.
const TILE_OFFSET = 0.005;

function canvasTexture(canvas) {
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
}

// The dashboard face on a block's back (#8): #6's tile, rotated pi about y, hidden until the block flips. Unlit, so
// the tile reads as painted; alphaTest drops its transparent corners.
function buildTile(slot, entry) {
  const canvas = makeCanvas(512);
  paintTile(canvas, entry);
  const tile = new THREE.Mesh(new THREE.PlaneGeometry(1, 1),
    new THREE.MeshBasicMaterial({ map: canvasTexture(canvas), alphaTest: 0.5, toneMapped: false }));
  tile.rotation.y = Math.PI;
  tile.position.z = -TILE_OFFSET;
  tile.visible = false;
  tile.userData = { slot, part: 'tile' };
  return tile;
}

// One block: a 40 x 40 plane at its slot, puffed and folded (foldZ is evaluated where each vertex really hangs,
// so a tilted block follows the fold under it), with a flat morph target 0 at influence 0 for #10's lift and #8's
// flatten. A filler is built transparent, since it fades; every other block carries its tile face.
function buildBlock(slot, entry, renderer) {
  const face = faceKind(entry);
  const [cx, cy] = slotCentre(slot);
  const tilt = face === 'planned' ? (rngFor(entry.id, 'tilt')() * 2 - 1) * TILT_MAX : 0;
  const cos = Math.cos(tilt);
  const sin = Math.sin(tilt);
  const geometry = new THREE.PlaneGeometry(1, 1, SEGMENTS, SEGMENTS);
  const position = geometry.attributes.position;
  const flat = position.clone();
  for (let j = 0; j < position.count; j += 1) {
    const lx = position.getX(j);
    const ly = position.getY(j);
    position.setZ(j, puffZ(lx + 0.5, ly + 0.5) + foldZ(cx + cos * lx - sin * ly, cy + sin * lx + cos * ly));
  }
  geometry.computeVertexNormals();
  const up = new Float32Array(position.count * 3);
  for (let j = 0; j < position.count; j += 1) up[3 * j + 2] = 1;
  geometry.morphAttributes.position = [flat];
  geometry.morphAttributes.normal = [new THREE.BufferAttribute(up, 3)];

  const canvas = makeCanvas(512);
  paintFace(canvas, entry, face);
  const map = canvasTexture(canvas);
  map.anisotropy = Math.min(8, renderer.capabilities.getMaxAnisotropy());
  const mesh = new THREE.Mesh(geometry, fabricMaterial({ map, transparent: face === 'filler' }));
  mesh.updateMorphTargets();
  mesh.morphTargetInfluences[0] = 0;
  mesh.position.set(cx, cy, face === 'planned' ? PLANNED_LIFT : 0);
  mesh.rotation.z = tilt;
  mesh.userData = { slot, id: entry ? entry.id : null, status: entry ? entry.status : null, face };
  if (face !== 'filler') mesh.add(buildTile(slot, entry));
  return mesh;
}

// The sashing: one folded sheet over the whole quilt, cut along every block-vertex line so it meets each block
// edge vertex for vertex. Cells inside an untilted block are left out; cells under a planned (tilted) block are
// kept, so the slivers a tilt uncovers show muslin, not the page. UVs follow #6's D38 rule.
function buildSashing(blocks) {
  const { quiltW: W, quiltH: H } = LAYOUT;
  const lines = (centres, sign) => {
    const out = [];
    for (const c of centres) for (let k = 0; k <= SEGMENTS; k += 1) out.push(c + sign * (k / SEGMENTS - 0.5));
    return out;
  };
  const xs = [-W / 2, ...lines([0, 1, 2, 3].map((i) => slotCentre(i)[0]), 1), W / 2].sort((a, b) => a - b);
  const ys = [-H / 2, ...lines([0, 4, 8].map((i) => slotCentre(i)[1]), -1), H / 2].sort((a, b) => a - b);
  const solid = blocks.filter((b) => b.userData.face !== 'planned').map((b) => slotCentre(b.userData.slot));
  const inSolid = (x, y) => solid.some(([cx, cy]) => Math.abs(x - cx) < 0.5 && Math.abs(y - cy) < 0.5);

  const positions = [];
  const uvs = [];
  const indices = [];
  const vertexAt = new Map();
  const vertex = (i, j) => {
    const key = i * ys.length + j;
    if (!vertexAt.has(key)) {
      const x = xs[i];
      const y = ys[j];
      vertexAt.set(key, positions.length / 3);
      positions.push(x, y, foldZ(x, y));
      uvs.push((x + W / 2) / W, (y + H / 2) / H);
    }
    return vertexAt.get(key);
  };
  for (let i = 0; i + 1 < xs.length; i += 1) {
    for (let j = 0; j + 1 < ys.length; j += 1) {
      if (inSolid((xs[i] + xs[i + 1]) / 2, (ys[j] + ys[j + 1]) / 2)) continue;
      const a = vertex(i, j);
      const b = vertex(i + 1, j);
      const c = vertex(i + 1, j + 1);
      const d = vertex(i, j + 1);
      indices.push(a, b, c, a, c, d);
    }
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
  geometry.setAttribute('uv', new THREE.Float32BufferAttribute(uvs, 2));
  geometry.setIndex(indices);
  geometry.computeVertexNormals();

  const canvas = makeCanvas(...sashingSize(LAYOUT));
  paintSashing(canvas, LAYOUT);
  // The weave keeps the blocks' scale in scene units: a block is 1 unit, the sheet W x H.
  const normalMap = weaveNormalMap().clone();
  normalMap.repeat.set(W * WEAVE_REPEAT, H * WEAVE_REPEAT);
  return new THREE.Mesh(geometry, fabricMaterial({ map: canvasTexture(canvas), normalMap, transparent: true }));
}

// The hanging rod: a wooden pole just above the top edge, with ball ends larger than the pole.
function buildRod() {
  const { y, radius, capRadius, halfLength } = LAYOUT.rod;
  const canvas = makeCanvas(1024, 256);
  paintWood(canvas);
  const material = new THREE.MeshStandardMaterial({ map: canvasTexture(canvas), roughness: 0.55, transparent: true });
  const rod = new THREE.Group();
  const pole = new THREE.Mesh(new THREE.CylinderGeometry(radius, radius, 2 * halfLength, 24, 1, true), material);
  pole.rotation.z = Math.PI / 2;
  const caps = [-halfLength, halfLength].map((x) => {
    const cap = new THREE.Mesh(new THREE.SphereGeometry(capRadius, 20, 14), material);
    cap.position.x = x;
    return cap;
  });
  rod.add(pole, ...caps);
  rod.position.y = y;
  return { rod, caps, material };
}

// The soft shadow on the wall behind, down and right of the quilt (the key light is upper left).
function buildShadow() {
  const canvas = makeCanvas(512);
  paintShadow(canvas);
  const geometry = new THREE.PlaneGeometry(LAYOUT.quiltW * 1.12, LAYOUT.quiltH * 1.08);
  const shadow = new THREE.Mesh(geometry, new THREE.MeshBasicMaterial({
    map: canvasTexture(canvas), transparent: true, depthWrite: false,
  }));
  shadow.position.set(0.12, -0.1, LAYOUT.shadowZ);
  return shadow;
}

// A mesh's `count` vertices in world space as one flat array; read(j, v) fills v with vertex j in local space.
function flatWorld(mesh, count, read) {
  const v = new THREE.Vector3();
  const out = new Array(count * 3);
  for (let j = 0; j < count; j += 1) {
    read(j, v).applyMatrix4(mesh.matrixWorld);
    out[3 * j] = v.x;
    out[3 * j + 1] = v.y;
    out[3 * j + 2] = v.z;
  }
  return out;
}

// Builds the quilt from `slots` (12 cleaned entries, null for a filler) once the caller has awaited
// fontsReady(). The blocks, sashing and rod hang in `group`, which setAmbient sways; the shadow stays put.
export function buildQuilt(renderer, { slots }) {
  const scene = new THREE.Scene();
  addLights(scene);
  const camera = fitCamera(new THREE.PerspectiveCamera(35, 1.6, 0.1, 100), 1.6);
  const group = new THREE.Group();
  const blocks = slots.map((entry, slot) => buildBlock(slot, entry, renderer));
  const sashing = buildSashing(blocks);
  const { rod, caps, material: rodMaterial } = buildRod();
  const shadow = buildShadow();
  group.add(sashing, ...blocks, rod);
  scene.add(group, shadow);
  const tiles = blocks.map((b) => b.children.find((c) => c.userData.part === 'tile') ?? null);
  const fillers = blocks.filter((b) => b.userData.face === 'filler');

  const pivot = new THREE.Vector3(0, LAYOUT.rod.y, 0);
  const aboutX = new THREE.Quaternion();
  const aboutY = new THREE.Quaternion();
  const X = new THREE.Vector3(1, 0, 0);
  const Y = new THREE.Vector3(0, 1, 0);

  // R = Ry(tiltY) Rx(tiltX) Rx(sway) about the rod's centre P, so the group moves to P - R P. Zeros are the identity.
  function setAmbient({ sway = 0, tiltX = 0, tiltY = 0 } = {}) {
    aboutX.setFromAxisAngle(X, sway + tiltX);
    aboutY.setFromAxisAngle(Y, tiltY);
    group.quaternion.multiplyQuaternions(aboutY, aboutX);
    group.position.copy(pivot).applyQuaternion(group.quaternion).negate().add(pivot);
  }

  // Block i's pose (#8's director): position, rotY (the flip), rotZ (the seeded tilt) and morph (the flatten).
  // Euler XYZ makes the rotation Ry(rotY) Rz(rotZ). Its tile face draws only once the block starts to flip.
  function setBlockPose(i, { position, rotY, rotZ, morph }) {
    const mesh = blocks[i];
    mesh.position.fromArray(position);
    mesh.rotation.y = rotY;
    mesh.rotation.z = rotZ;
    mesh.morphTargetInfluences[0] = morph;
    if (tiles[i]) tiles[i].visible = morph > 0;
  }

  // The faded parts as [object, material]: the rod's meshes share one material, so its group is what hides.
  const faded = [[sashing, sashing.material], [rod, rodMaterial], [shadow, shadow.material],
    ...fillers.map((b) => [b, b.material])];

  // The fade (#8): 1 shown ... 0 gone, on the sashing, rod, shadow and fillers; at 0 they are not drawn at all.
  function setFade(f) {
    for (const [object, material] of faded) {
      material.opacity = f;
      object.visible = f > 0;
    }
  }

  // Test-only: each faded part's { opacity, visible }.
  function fades() {
    const of = (object, material) => ({ opacity: material.opacity, visible: object.visible });
    return { sashing: of(sashing, sashing.material), rod: of(rod, rodMaterial), shadow: of(shadow, shadow.material),
      fillers: fillers.map((b) => ({ slot: b.userData.slot, ...of(b, b.material) })) };
  }

  const raycaster = new THREE.Raycaster();
  const pointer = new THREE.Vector2();
  const ray = new THREE.Ray();
  const ground = new THREE.Plane(new THREE.Vector3(0, 0, 1), 0);
  const targets = [sashing, ...blocks, ...tiles.filter(Boolean)];
  const shown = (object) => {
    for (let o = object; o; o = o.parent) if (!o.visible) return false;
    return true;
  };

  // What is under a client (CSS pixel) point: the nearest drawn block, sashing or tile face (the rod and shadow
  // are never targets; a flipped block or an unflipped tile faces away, so FrontSide skips it), and the point in
  // the group's space: the hit, or for 'none' where the ray meets the group's z = 0 plane. A block is known by
  // its place in `blocks`, so the snapshot's userData stays as it is; only a tile carries { slot, part }.
  function pick(clientX, clientY) {
    const rect = renderer.domElement.getBoundingClientRect();
    pointer.set(((clientX - rect.left) / rect.width) * 2 - 1, 1 - ((clientY - rect.top) / rect.height) * 2);
    scene.updateMatrixWorld();
    raycaster.setFromCamera(pointer, camera);
    // The Raycaster ignores `visible`, so a hidden or faded part is filtered here.
    const hit = raycaster.intersectObjects(targets, false).find((h) => shown(h.object));
    if (hit) {
      const [x, y] = group.worldToLocal(hit.point.clone()).toArray();
      const slot = blocks.indexOf(hit.object);
      if (hit.object === sashing) return { part: 'sashing', slot: null, point: [x, y] };
      if (slot >= 0) return { part: 'block', slot, point: [x, y] };
      return { part: 'tile', slot: hit.object.userData.slot, point: [x, y] };
    }
    ray.copy(raycaster.ray).applyMatrix4(group.matrixWorld.clone().invert());
    const at = ray.intersectPlane(ground, new THREE.Vector3());
    return { part: 'none', slot: null, point: at ? [at.x, at.y] : [0, 0] };
  }

  // Resizing clears the canvas, so the current pose is redrawn at once (uncounted): a ResizeObserver runs after
  // the frame's render and before the paint, and without this the quilt flickers to paper on a live resize.
  function resize(width, height, pixelRatio) {
    // setPixelRatio resizes the buffer itself, so it runs only when the ratio changes.
    if (renderer.getPixelRatio() !== pixelRatio) renderer.setPixelRatio(pixelRatio);
    renderer.setSize(width, height, false);
    fitCamera(camera, width / height);
    render();
  }

  function render() {
    renderer.render(scene, camera);
  }

  // The D18 contract, as plain JSON-safe arrays in world space:
  // { blocks: [{ slot, id, status, face, positions /*1681*3 flat: getVertexPosition(i).applyMatrix4(matrixWorld)*/,
  //              indices, uvs /*1681*2*/ }] (12, slot order),
  //   sashing: { positions, indices, uvs }, pins: [], stitches: [],
  //   rod: { start, end, radius },            // world centres of the two ball ends
  //   shadow: { position, quaternion, width, height },
  //   camera: { position, target, up, fov, aspect } }
  // A filler block is id: null, status: null, face: 'filler'.
  function snapshot() {
    scene.updateMatrixWorld(true);
    const p = new THREE.Vector3();
    const q = new THREE.Quaternion();
    const s = new THREE.Vector3();
    shadow.matrixWorld.decompose(p, q, s);
    const { width, height } = shadow.geometry.parameters;
    const sashPosition = sashing.geometry.attributes.position;
    return {
      blocks: blocks.map((mesh) => ({
        ...mesh.userData,
        positions: flatWorld(mesh, mesh.geometry.attributes.position.count, (j, v) => mesh.getVertexPosition(j, v)),
        indices: Array.from(mesh.geometry.index.array),
        uvs: Array.from(mesh.geometry.attributes.uv.array),
      })),
      sashing: {
        positions: flatWorld(sashing, sashPosition.count, (j, v) => v.fromBufferAttribute(sashPosition, j)),
        indices: Array.from(sashing.geometry.index.array),
        uvs: Array.from(sashing.geometry.attributes.uv.array),
      },
      pins: [],
      stitches: [],
      rod: {
        start: caps[0].getWorldPosition(new THREE.Vector3()).toArray(),
        end: caps[1].getWorldPosition(new THREE.Vector3()).toArray(),
        radius: LAYOUT.rod.radius,
      },
      shadow: { position: p.toArray(), quaternion: q.toArray(), width: width * s.x, height: height * s.y },
      camera: {
        position: camera.position.toArray(), target: camera.userData.target.toArray(), up: camera.up.toArray(),
        fov: camera.fov, aspect: camera.aspect,
      },
    };
  }

  // A world point in client (CSS pixel) coordinates on the canvas.
  function project([x, y, z]) {
    camera.updateMatrixWorld();
    const v = new THREE.Vector3(x, y, z).project(camera);
    const rect = renderer.domElement.getBoundingClientRect();
    return [rect.left + ((v.x + 1) / 2) * rect.width, rect.top + ((1 - v.y) / 2) * rect.height];
  }

  // Releases every geometry, material and texture (the shared weave normal map and the sashing's clone
  // included), then the renderer and its context.
  function dispose() {
    const geometries = new Set();
    const materials = new Set();
    const textures = new Set();
    scene.traverse((object) => {
      if (!object.isMesh) return;
      geometries.add(object.geometry);
      materials.add(object.material);
      for (const key of ['map', 'normalMap']) if (object.material[key]) textures.add(object.material[key]);
    });
    geometries.forEach((g) => g.dispose());
    materials.forEach((m) => m.dispose());
    textures.forEach((t) => t.dispose());
    if (textures.has(weaveNormal)) weaveNormal = null;
    renderer.dispose();
    // An already-lost context has no WEBGL_lose_context to call, and Three would warn.
    if (!renderer.getContext().isContextLost()) renderer.forceContextLoss();
  }

  return {
    scene, camera, renderer, group, blocks, sashing, rod, shadow, setAmbient, setBlockPose, setFade, fades, pick, resize,
    render, snapshot, project, dispose,
  };
}
