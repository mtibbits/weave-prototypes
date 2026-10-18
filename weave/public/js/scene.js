// WEAVE's Three.js scene: the renderer, lights, fabric material and camera fit that #8-#22 reuse, and
// buildQuilt, which builds the hanging quilt from LAYOUT and #6's painters. Importing it creates nothing.
import * as THREE from 'three';
import { makeCanvas, paintSashing, paintShadow, paintWeaveNormal, paintWood, sashingSize } from './fabric.js';
import { foldZ, LAYOUT, puffZ, slotCentre } from './layout.js';
import { ease } from './motion.js';
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
// the tile reads as painted; alphaTest drops its transparent corners. `tagged` sews #14's "New" label on it.
function buildTile(slot, entry, tagged) {
  const canvas = makeCanvas(512);
  paintTile(canvas, entry, { tagged });
  const tile = new THREE.Mesh(new THREE.PlaneGeometry(1, 1),
    new THREE.MeshBasicMaterial({ map: canvasTexture(canvas), alphaTest: 0.5, toneMapped: false }));
  tile.rotation.y = Math.PI;
  tile.position.z = -TILE_OFFSET;
  tile.visible = false;
  tile.userData = { slot, part: 'tile' };
  return tile;
}

// Block-local z of the cloth at (lx, ly) for a block in `slot` at `tilt`: the puff plus the fold evaluated where that
// point really hangs (D10: read on every call, never cached). foldBlock and #10's decor both come here.
function surfaceZ(slot, tilt, lx, ly) {
  const [cx, cy] = slotCentre(slot);
  const cos = Math.cos(tilt);
  const sin = Math.sin(tilt);
  return puffZ(lx + 0.5, ly + 0.5) + foldZ(cx + cos * lx - sin * ly, cy + sin * lx + cos * ly);
}

// A block's base for `slot`: each vertex of the flat morph target puffed and folded (foldZ is evaluated where the
// vertex really hangs, so a tilted block follows the fold under it, and read on every call: D10), then its
// normals and bounds. The build and #9's placeBlock both come here, so a moved block is the block a fresh build
// would give at that slot.
function foldBlock(geometry, slot, tilt) {
  const position = geometry.attributes.position;
  const flat = geometry.morphAttributes.position[0];
  for (let j = 0; j < position.count; j += 1) position.setZ(j, surfaceZ(slot, tilt, flat.getX(j), flat.getY(j)));
  position.needsUpdate = true;
  geometry.computeVertexNormals();
  geometry.computeBoundingSphere();
}

// One block: a 40 x 40 plane at its slot, puffed and folded by foldBlock, with a flat morph target 0 at influence 0 for
// #8's flatten (#10's hover lift is the block's scale and z, not a morph). A filler is built transparent, since it
// fades; every other block carries its tile face.
function buildBlock(slot, entry, renderer, tagged) {
  const face = faceKind(entry);
  const [cx, cy] = slotCentre(slot);
  const tilt = face === 'planned' ? (rngFor(entry.id, 'tilt')() * 2 - 1) * TILT_MAX : 0;
  const geometry = new THREE.PlaneGeometry(1, 1, SEGMENTS, SEGMENTS);
  const { count } = geometry.attributes.position;
  const up = new Float32Array(count * 3);
  for (let j = 0; j < count; j += 1) up[3 * j + 2] = 1;
  geometry.morphAttributes.position = [geometry.attributes.position.clone()];
  geometry.morphAttributes.normal = [new THREE.BufferAttribute(up, 3)];
  foldBlock(geometry, slot, tilt);

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
  if (face !== 'filler') mesh.add(buildTile(slot, entry, tagged));
  return mesh;
}

// The sashing: one folded sheet over the whole quilt, cut along every block-vertex line so it meets each block
// edge vertex for vertex. Cells inside an untilted block are left out; cells under a planned (tilted) block are
// kept, so the slivers a tilt uncovers show muslin, not the page. The holes follow each block's current
// userData.slot, so #9's reseam re-cuts them after a reorder. UVs follow #6's D38 rule.
function sashingGeometry(blocks) {
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
  return geometry;
}

function buildSashing(blocks) {
  const { quiltW: W, quiltH: H } = LAYOUT;
  const canvas = makeCanvas(...sashingSize(LAYOUT));
  paintSashing(canvas, LAYOUT);
  // The weave keeps the blocks' scale in scene units: a block is 1 unit, the sheet W x H.
  const normalMap = weaveNormalMap().clone();
  normalMap.repeat.set(W * WEAVE_REPEAT, H * WEAVE_REPEAT);
  return new THREE.Mesh(sashingGeometry(blocks),
    fabricMaterial({ map: canvasTexture(canvas), normalMap, transparent: true }));
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

// --- #10: seam stitches, pins and the hover lift. ---

// Seam stitch dash frame (D33): local +X runs along the seam; the dash is a cylinder of length STITCH_DASH_LENGTH and
// radius STITCH_DASH_RADIUS centred at its origin; the centre lies ON the fabric surface at its x, y (puffZ + foldZ
// there, puffZ 0 on the seam line), with no lift, so half the thread sinks in. #16's needle has its own NEEDLE_LIFT.
export const STITCH_DASH_LENGTH = 0.05;
export const STITCH_DASH_RADIUS = 0.005;
export const STITCHES_PER_SIDE = 12;          // dash k on a side at (k + 0.5) / 12 along it: 48 per block
// Pin frame (#22 keeps it): origin at the tip, shaft along local +Y to a round head whose centre is PIN_LENGTH above,
// in scene units; the tip sits on the block's surface and +Y leans at most PIN_MAX_TILT_DEG from its normal there.
export const PIN_LENGTH = 0.16;
export const PIN_HEAD_RADIUS = 0.018;
export const PIN_SHAFT_RADIUS = 0.004;
export const PIN_MAX_TILT_DEG = 15;           // seeded; the AC bound is 20
export const DECOR_TIMING = Object.freeze({ sew: 0.4, pop: 0.3, drop: 0.3 }); // seconds of director time
export const HOVER = Object.freeze({ scale: 0.03, lift: 0.04, rate: 12 });

// The share of the sew each dash takes to scale in; the dashes start one after another over the rest.
const SEW_EACH = 0.25;
// A restored pin drops this far along its +Y; a popped one rises this far as it shrinks.
const DROP_FROM = 0.25;
const POP_RISE = 0.4;
// The step for the cloth's slope, in block-local units.
const SLOPE_EPS = 1e-4;

// The cloth's slope [dz/dx, dz/dy] at (lx, ly), by central difference.
function surfaceSlope(slot, tilt, lx, ly) {
  const at = (u, v) => surfaceZ(slot, tilt, u, v);
  return [(at(lx + SLOPE_EPS, ly) - at(lx - SLOPE_EPS, ly)) / (2 * SLOPE_EPS),
    (at(lx, ly + SLOPE_EPS) - at(lx, ly - SLOPE_EPS)) / (2 * SLOPE_EPS)];
}

// The dashes' rest matrices in block-local space: each side in turn (top, right, bottom, left, clockwise), its +X
// along the seam's slope and its +Z up off the cloth.
function stitchMatrices(slot, tilt) {
  const sides = [[[-0.5, 0.5], [1, 0]], [[0.5, 0.5], [0, -1]], [[0.5, -0.5], [-1, 0]], [[-0.5, -0.5], [0, 1]]];
  const out = [];
  const x = new THREE.Vector3();
  const y = new THREE.Vector3();
  const z = new THREE.Vector3();
  for (const [[sx, sy], [dx, dy]] of sides) {
    for (let k = 0; k < STITCHES_PER_SIDE; k += 1) {
      const t = (k + 0.5) / STITCHES_PER_SIDE;
      const lx = sx + dx * t;
      const ly = sy + dy * t;
      const [gx, gy] = surfaceSlope(slot, tilt, lx, ly);
      const slope = gx * dx + gy * dy;
      x.set(dx, dy, slope).normalize();
      z.crossVectors(x, y.set(-dy, dx, 0)).normalize();
      y.crossVectors(z, x);
      out.push(new THREE.Matrix4().makeBasis(x, y, z).setPosition(lx, ly, surfaceZ(slot, tilt, lx, ly)));
    }
  }
  return out;
}

// The pins' rest matrices in block-local space, seeded from rngFor(id, 'pins') in this draw order: the count (3 or
// 4), the corner a 3 leaves out, then per pin its insets from both edges (0.12-0.18), azimuth and lean.
function pinMatrices(id, slot, tilt) {
  const rng = rngFor(id, 'pins');
  const corners = [[-1, 1], [1, 1], [1, -1], [-1, -1]];
  if (rng() < 0.5) corners.splice(Math.floor(rng() * 4), 1);
  const maxLean = (PIN_MAX_TILT_DEG * Math.PI) / 180;
  const up = new THREE.Vector3(0, 1, 0);
  return corners.map(([sx, sy]) => {
    const lx = sx * (0.5 - (0.12 + 0.06 * rng()));
    const ly = sy * (0.5 - (0.12 + 0.06 * rng()));
    const azimuth = rng() * 2 * Math.PI;
    const lean = rng() * maxLean;
    const [gx, gy] = surfaceSlope(slot, tilt, lx, ly);
    const n = new THREE.Vector3(-gx, -gy, 1).normalize();
    const a = new THREE.Vector3(1, 0, 0).addScaledVector(n, -n.x).normalize();
    const b = new THREE.Vector3().crossVectors(n, a);
    const dir = n.multiplyScalar(Math.cos(lean))
      .addScaledVector(a, Math.sin(lean) * Math.cos(azimuth)).addScaledVector(b, Math.sin(lean) * Math.sin(azimuth));
    const quaternion = new THREE.Quaternion().setFromUnitVectors(up, dir.normalize());
    return new THREE.Matrix4().compose(new THREE.Vector3(lx, ly, surfaceZ(slot, tilt, lx, ly)), quaternion, new THREE.Vector3(1, 1, 1));
  });
}

// One decor part as a hidden InstancedMesh child of its block: never culled, never a pick target.
function decorMesh(geometry, material, count, part) {
  const mesh = new THREE.InstancedMesh(geometry, material, count);
  mesh.visible = false;
  mesh.frustumCulled = false;
  mesh.userData = { part };
  return mesh;
}

// The decor's shared geometries (in their D33 and pin frames) and materials.
function decorParts() {
  const dash = new THREE.CylinderGeometry(STITCH_DASH_RADIUS, STITCH_DASH_RADIUS, STITCH_DASH_LENGTH, 8, 1);
  dash.rotateZ(-Math.PI / 2);
  const shaft = new THREE.CylinderGeometry(PIN_SHAFT_RADIUS, PIN_SHAFT_RADIUS, PIN_LENGTH, 8, 1);
  shaft.translate(0, PIN_LENGTH / 2, 0);
  const head = new THREE.SphereGeometry(PIN_HEAD_RADIUS, 12, 8);
  head.translate(0, PIN_LENGTH, 0);
  return {
    dash, shaft, head,
    thread: new THREE.MeshStandardMaterial({ color: '#3B2F2A', roughness: 0.85 }),
    steel: new THREE.MeshStandardMaterial({ color: '#C3C7CB', metalness: 0.85, roughness: 0.35 }),
    bead: new THREE.MeshStandardMaterial({ color: '#C4623A', roughness: 0.45 }),
  };
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
// `tagged` (#14) is the ids whose tiles wear the "New" label, read once here; anything but an array tags nothing.
export function buildQuilt(renderer, { slots, tagged = [] }) {
  const wanted = new Set(Array.isArray(tagged) ? tagged : []);
  // Each block's tag, by block index (not in userData: the snapshot's block keys are pinned).
  const tags = slots.map((entry) => Boolean(entry) && wanted.has(entry.id));
  const scene = new THREE.Scene();
  addLights(scene);
  const camera = fitCamera(new THREE.PerspectiveCamera(35, 1.6, 0.1, 100), 1.6);
  const group = new THREE.Group();
  const blocks = slots.map((entry, slot) => buildBlock(slot, entry, renderer, tags[slot]));
  const sashing = buildSashing(blocks);
  const { rod, caps, material: rodMaterial } = buildRod();
  const shadow = buildShadow();
  group.add(sashing, ...blocks, rod);
  scene.add(group, shadow);
  const tiles = blocks.map((b) => b.children.find((c) => c.userData.part === 'tile') ?? null);
  const fillers = blocks.filter((b) => b.userData.face === 'filler');
  // Each block's seeded tilt, read once (not in userData: the snapshot's block keys are pinned).
  const tilts = blocks.map((b) => b.rotation.z);
  const entries = slots.slice();

  // --- #10's decor. Its state lives here, by block index, never in userData (the snapshot spreads userData into
  // every block, and its keys are pinned). Each kind (stitches, pins) has a state for #16 (shown or hidden), and is
  // drawn when shown and its block is not stowed (#8's transitions stow it). `drawn` is where its animation is
  // heading; `anim` is { dir, t, dur, from } while it runs.
  const parts = decorParts();
  const decor = blocks.map((mesh, i) => {
    const { id, status, face } = mesh.userData;
    const kinds = {};
    if (status === 'live') {
      const rest = stitchMatrices(i, tilts[i]);
      const stitches = decorMesh(parts.dash, parts.thread, rest.length, 'stitches');
      mesh.add(stitches);
      kinds.stitches = { type: 'stitches', meshes: [stitches], rest, f: new Array(rest.length).fill(0) };
    }
    if (status === 'live' || face === 'planned') {
      const rest = pinMatrices(id, i, tilts[i]);
      const shafts = decorMesh(parts.shaft, parts.steel, rest.length, 'pinShafts');
      const heads = decorMesh(parts.head, parts.bead, rest.length, 'pinHeads');
      mesh.add(shafts, heads);
      kinds.pins = { type: 'pins', meshes: [shafts, heads], rest, y: 0, s: 0 };
    }
    for (const kind of Object.values(kinds)) Object.assign(kind, { state: 'hidden', drawn: false, anim: null });
    return { kinds, stowed: false };
  });
  let decorPaused = false;

  const scratch = new THREE.Matrix4();
  const step = new THREE.Matrix4();
  // Writes a kind's instance matrices from its rest matrices and its current scales (stitches) or drop/pop (pins).
  function writeKind(kind) {
    kind.rest.forEach((rest, k) => {
      scratch.copy(rest);
      if (kind.type === 'stitches') {
        const f = kind.f[k];
        if (f !== 1) scratch.multiply(step.makeScale(f, f, f));
      } else if (kind.y !== 0 || kind.s !== 1) {
        scratch.multiply(step.makeTranslation(0, kind.y, 0)).multiply(step.makeScale(kind.s, kind.s, kind.s));
      }
      for (const mesh of kind.meshes) mesh.setMatrixAt(k, scratch);
    });
    for (const mesh of kind.meshes) mesh.instanceMatrix.needsUpdate = true;
  }

  // A kind at u (0-1) of its running animation: a sew scales the dashes in one after another, a drop lands the pins
  // along their +Y, and a pop shrinks either away (the pins rising as they go).
  function stepKind(kind, u) {
    const { dir, from } = kind.anim;
    const e = ease.inout(u);
    if (kind.type === 'stitches') {
      const n = kind.f.length;
      kind.f = from.f.map((f0, k) => {
        if (dir === 'out') return f0 * (1 - e);
        const start = (k / n) * (1 - SEW_EACH);
        return f0 + (1 - f0) * Math.min(1, Math.max(0, (u - start) / SEW_EACH));
      });
    } else if (dir === 'out') {
      kind.y = from.y + POP_RISE * e;
      kind.s = from.s * (1 - e);
    } else {
      kind.y = from.y * (1 - e);
      kind.s = from.s + (1 - from.s) * e;
    }
    writeKind(kind);
  }

  // A kind at the end of where it is heading: exactly at rest and drawn, or hidden.
  function endKind(kind) {
    kind.anim = null;
    if (kind.type === 'stitches') kind.f.fill(kind.drawn ? 1 : 0);
    else {
      kind.y = 0;
      kind.s = kind.drawn ? 1 : 0;
    }
    if (kind.drawn) writeKind(kind);
    for (const mesh of kind.meshes) mesh.visible = kind.drawn;
  }

  // Heads block i's kind for where its state and stow say it should be; a kind already heading there is left alone.
  // Instant when not animated or while paused.
  function retarget(i, kind, animate) {
    const want = kind.state === 'shown' && !decor[i].stowed;
    if (want === kind.drawn) return;
    kind.drawn = want;
    if (!animate || decorPaused) {
      endKind(kind);
      return;
    }
    // A drop starts DROP_FROM up at full size; one that turns back a pop starts where the pop has got to.
    const from = kind.type === 'stitches' ? { f: kind.f.slice() }
      : { y: kind.s === 0 ? DROP_FROM : kind.y, s: kind.s === 0 ? 1 : kind.s };
    const dur = !want ? DECOR_TIMING.pop : kind.type === 'stitches' ? DECOR_TIMING.sew : DECOR_TIMING.drop;
    kind.anim = { dir: want ? 'in' : 'out', t: 0, dur, from };
    for (const mesh of kind.meshes) mesh.visible = true;
    stepKind(kind, 0);
  }

  const indexOf = (id) => (typeof id === 'string' ? blocks.findIndex((b) => b.userData.id === id) : -1);

  // #16's per-block calls: set block id's state for that kind; an unknown id, or a block without that decor, does
  // nothing, and a call that would set the state the kind already has never restarts its animation.
  function setState(id, key, state, { animate = true } = {}) {
    const i = indexOf(id);
    const kind = i < 0 ? null : decor[i].kinds[key];
    if (!kind || kind.state === state) return;
    kind.state = state;
    retarget(i, kind, animate);
  }
  const revealStitches = (id, options) => setState(id, 'stitches', 'shown', options);
  const popStitches = (id, options) => setState(id, 'stitches', 'hidden', options);
  const restorePins = (id, options) => setState(id, 'pins', 'shown', options);
  const popPins = (id, options) => setState(id, 'pins', 'hidden', options);

  // #8's transitions hide the decor (stow) and return it (unstow) without touching the per-block state #16 sets.
  function setStowed(i, stowed, animate) {
    if (decor[i].stowed === stowed) return;
    decor[i].stowed = stowed;
    for (const kind of Object.values(decor[i].kinds)) retarget(i, kind, animate);
  }
  const byId = (fn) => (id, { animate = true } = {}) => {
    const i = indexOf(id);
    if (i >= 0) fn(i, animate);
  };
  const stow = byId((i, animate) => setStowed(i, true, animate));
  const unstow = byId((i, animate) => setStowed(i, false, animate));
  const stowAll = ({ animate = true } = {}) => decor.forEach((_, i) => setStowed(i, true, animate));
  const unstowAll = ({ animate = true } = {}) => decor.forEach((_, i) => setStowed(i, false, animate));
  // Block index i's unstow, for main.js's per-block sew-back (a filler or the suggest block has no id to name).
  const unstowBlock = (i, { animate = true } = {}) => setStowed(i, false, animate);

  const eachKind = (fn) => decor.forEach(({ kinds }) => Object.values(kinds).forEach(fn));

  // One frame of h seconds of director time (D8: the decor has no clock of its own).
  function tick(h) {
    eachKind((kind) => {
      if (!kind.anim) return;
      kind.anim.t += h;
      if (kind.anim.t >= kind.anim.dur - 1e-9) endKind(kind);
      else stepKind(kind, kind.anim.t / kind.anim.dur);
    });
  }

  // Every running decor animation at its end.
  function finishDecor() {
    eachKind((kind) => { if (kind.anim) endKind(kind); });
  }

  // Paused, every call is instant and a running animation ends now.
  function setPaused(paused) {
    decorPaused = paused;
    if (paused) finishDecor();
  }

  // Repaints block id's face as `kind` (#16's "start planned" and sew-in); its tilt and the sashing are unchanged.
  function setFace(id, kind) {
    if (!['sewn', 'planned', 'suggest'].includes(kind)) throw new Error("WEAVE: setFace needs 'sewn', 'planned' or 'suggest'.");
    const i = indexOf(id);
    if (i < 0) return;
    const { map } = blocks[i].material;
    paintFace(map.image, entries[i], kind);
    map.needsUpdate = true;
    blocks[i].userData.face = kind;
  }

  // The hover lift: block i's amount (0-1), which setBlockPose applies on every call; and each block's last pose.
  const hover = new Array(blocks.length).fill(0);
  const poses = blocks.map((b) => ({ position: b.position.toArray(), rotY: 0, rotZ: b.rotation.z, morph: 0 }));

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
  // #10: the stored hover amount a scales the block by 1 + HOVER.scale a and lifts it HOVER.lift a; at 0 the pose is
  // exactly the director's.
  function setBlockPose(i, pose) {
    const { position, rotY, rotZ, morph } = pose;
    const mesh = blocks[i];
    const a = hover[i];
    poses[i] = pose;
    mesh.position.fromArray(position);
    if (a !== 0) mesh.position.z += HOVER.lift * a;
    mesh.scale.setScalar(1 + HOVER.scale * a);
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

  // Aims the raycaster through a client (CSS pixel) point.
  function aim(clientX, clientY) {
    const rect = renderer.domElement.getBoundingClientRect();
    pointer.set(((clientX - rect.left) / rect.width) * 2 - 1, 1 - ((clientY - rect.top) / rect.height) * 2);
    scene.updateMatrixWorld();
    raycaster.setFromCamera(pointer, camera);
  }

  // Where the aimed ray meets the group's z = 0 plane, in the group's space.
  function groundPoint() {
    ray.copy(raycaster.ray).applyMatrix4(group.matrixWorld.clone().invert());
    const at = ray.intersectPlane(ground, new THREE.Vector3());
    return at ? [at.x, at.y] : [0, 0];
  }

  // A client point on the group's z = 0 plane, whatever is drawn there: #9's drag follows the pointer with it.
  function planePoint(clientX, clientY) {
    aim(clientX, clientY);
    return groundPoint();
  }

  // What is under a client (CSS pixel) point: the nearest drawn block, sashing or tile face (the rod and shadow
  // are never targets; a flipped block or an unflipped tile faces away, so FrontSide skips it), and the point in
  // the group's space: the hit, or for 'none' where the ray meets the group's z = 0 plane. A block and its tile
  // report their current userData.slot, which #9's placeBlock keeps up to date.
  function pick(clientX, clientY) {
    aim(clientX, clientY);
    // The Raycaster ignores `visible`, so a hidden or faded part is filtered here.
    const hit = raycaster.intersectObjects(targets, false).find((h) => shown(h.object));
    if (!hit) return { part: 'none', slot: null, point: groundPoint() };
    const [x, y] = group.worldToLocal(hit.point.clone()).toArray();
    if (hit.object === sashing) return { part: 'sashing', slot: null, point: [x, y] };
    const part = hit.object.userData.part === 'tile' ? 'tile' : 'block';
    return { part, slot: hit.object.userData.slot, point: [x, y] };
  }

  // Block i's hover amount (0-1), applied at once.
  function setHover(i, amount) {
    hover[i] = amount;
    setBlockPose(i, poses[i]);
  }

  // The hover's pick: the nearest drawn block under a client point (blocks only, never the sashing, so it stays
  // cheap), as its block index; null for none or a filler. pick (press and click) is unchanged.
  function pickBlock(clientX, clientY) {
    aim(clientX, clientY);
    const hit = raycaster.intersectObjects(blocks, false).find((h) => shown(h.object));
    if (!hit) return null;
    const i = blocks.indexOf(hit.object);
    return blocks[i].userData.face === 'filler' ? null : i;
  }

  // #9: refolds block i for `slot` (a fresh build's fold there) and moves its slot, and its tile's, to `slot`. Only
  // while the block is fully flat (morph influence 1), so the base it rewrites is never on screen; never cached.
  function placeBlock(i, slot) {
    const mesh = blocks[i];
    if (mesh.morphTargetInfluences[0] !== 1) throw new Error('WEAVE: placeBlock needs a flat block (morph influence 1).');
    foldBlock(mesh.geometry, slot, tilts[i]);
    mesh.userData.slot = slot;
    if (tiles[i]) tiles[i].userData.slot = slot;
    // #10: the decor re-lays on the new fold, and keeps its state.
    const { stitches, pins } = decor[i].kinds;
    if (stitches) stitches.rest = stitchMatrices(slot, tilts[i]);
    if (pins) pins.rest = pinMatrices(mesh.userData.id, slot, tilts[i]);
    for (const kind of [stitches, pins]) if (kind && (kind.drawn || kind.anim)) writeKind(kind);
  }

  // #9: re-cuts the sashing's holes for the blocks' current slots; the material and its maps are kept.
  function reseam() {
    const old = sashing.geometry;
    sashing.geometry = sashingGeometry(blocks);
    old.dispose();
  }

  // Test-only: block i's slot, seeded tilt and local base (before the tilt and the morph) as plain arrays.
  function blockBase(i) {
    const { geometry, userData } = blocks[i];
    return { slot: userData.slot, tilt: tilts[i], positions: Array.from(geometry.attributes.position.array),
      normals: Array.from(geometry.attributes.normal.array) };
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

  // The drawn instances of every block's decor part (block-slot order, then instance order) as { id, position,
  // quaternion, scale } in world space (block.matrixWorld x instanceMatrix, decomposed); a zero-scale instance (a
  // dash not yet sewn) is not drawn.
  function drawnDecor(key) {
    const out = [];
    const m = new THREE.Matrix4();
    const p = new THREE.Vector3();
    const q = new THREE.Quaternion();
    const s = new THREE.Vector3();
    for (const mesh of blocks.slice().sort((a, b) => a.userData.slot - b.userData.slot)) {
      const kind = decor[blocks.indexOf(mesh)].kinds[key];
      if (!kind || !shown(kind.meshes[0])) continue;
      kind.rest.forEach((_, k) => {
        if ((kind.type === 'stitches' ? kind.f[k] : kind.s) === 0) return;
        kind.meshes[0].getMatrixAt(k, m);
        m.premultiply(mesh.matrixWorld).decompose(p, q, s);
        out.push({ id: mesh.userData.id, position: p.toArray(), quaternion: q.toArray(), scale: s.toArray() });
      });
    }
    return out;
  }

  // The D18 contract, as plain JSON-safe arrays in world space:
  // { blocks: [{ slot, id, status, face, positions /*1681*3 flat: getVertexPosition(i).applyMatrix4(matrixWorld)*/,
  //              indices, uvs /*1681*2*/ }] (12, slot order),
  //   sashing: { positions, indices, uvs },
  //   pins: [{ id, position, quaternion, scale }],     // #10: each drawn pin once, from its shaft (its tip, +Y up it)
  //   stitches: [{ id, position, quaternion, scale }], // #10: each drawn dash (its centre, +X along the seam)
  //   stitchDash: { length, radius },                  // STITCH_DASH_LENGTH and STITCH_DASH_RADIUS
  //   (pins: [] and stitches: [] on a fresh build: the decor is built hidden)
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
      blocks: blocks.slice().sort((a, b) => a.userData.slot - b.userData.slot).map((mesh) => ({
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
      pins: drawnDecor('pins'),
      stitches: drawnDecor('stitches'),
      stitchDash: { length: STITCH_DASH_LENGTH, radius: STITCH_DASH_RADIUS },
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
    render, snapshot, project, dispose, placeBlock, reseam, blockBase, planePoint,
    revealStitches, popStitches, restorePins, popPins, setFace, stow, unstow, stowAll, unstowAll, unstowBlock, tick,
    setPaused, finishDecor, setHover, pickBlock,
    // #14: whether block i's tile was painted with the "New" label.
    isTagged: (i) => tags[i] === true,
    get decorIdle() { return decor.every(({ kinds }) => Object.values(kinds).every((k) => !k.anim)); },
  };
}
