// WEAVE's Three.js scene: the renderer, lights, fabric material and camera fit that #8-#22 reuse, and
// buildQuilt, which builds the hanging quilt from LAYOUT and #6's painters. Importing it creates nothing.
import * as THREE from 'three';
import { makeCanvas, paintWeaveNormal } from './fabric.js';
import { LAYOUT } from './layout.js';

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
export function fabricMaterial({ map, normalMap = weaveNormalMap() } = {}) {
  if (map) map.colorSpace = THREE.SRGBColorSpace;
  normalMap.colorSpace = THREE.NoColorSpace;
  return new THREE.MeshPhysicalMaterial({
    map: map ?? null,
    normalMap,
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
