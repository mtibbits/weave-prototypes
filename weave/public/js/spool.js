// The Help corner's spool of thread (#18), coded until E4's #22 swaps in a modelled one with the same frame and size.
// It is live-path only: it imports Three, so never import it statically from the boot. Importing it builds nothing.
// Units are E1's scene units, where a block is 1.0 (about 30 cm). The frame: the origin is the spool's centre and +Y its axis.
// The size: SPOOL_HEIGHT (0.17, about 5 cm) from flange to flange along the axis, and SPOOL_FLANGE_RADIUS (0.05) for both
// flanges, so the bounding box is 2 × SPOOL_FLANGE_RADIUS across x and z, centred on the origin.
// The children: `spool`, the lathe body (two flanges on a core), and `thread`, the wound thread between the flanges,
// tinted by createSpool({ threadColor }), default #C9A227, the needle tail's default (#13), so help.js passes one
// colour to both. E4's modelled Spool and SpoolThread nodes map onto `spool` and `thread`.
// Disposal: a spool owns every geometry and material in it, so dispose it by traversal.
import * as THREE from 'three';

export const SPOOL_HEIGHT = 0.17;
export const SPOOL_FLANGE_RADIUS = 0.05;
// A multiple of 4, so the lathe reaches ±SPOOL_FLANGE_RADIUS on both x and z and the bounds match the constant.
const SPOOL_SEGMENTS = 24;
const FLANGE = 0.012;
const CORE_RADIUS = 0.022;
const WOUND_RADIUS = 0.04;

// The body's half-profile (radius, height), from the bottom flange's centre out and up to the top flange's centre.
function makeBody() {
  const h = SPOOL_HEIGHT / 2;
  const r = SPOOL_FLANGE_RADIUS;
  const profile = [[0, -h], [r, -h], [r, -h + FLANGE], [CORE_RADIUS, -h + FLANGE], [CORE_RADIUS, h - FLANGE],
    [r, h - FLANGE], [r, h], [0, h]].map(([x, y]) => new THREE.Vector2(x, y));
  const material = new THREE.MeshStandardMaterial({ color: '#C8A27A', roughness: 0.6 });
  const body = new THREE.Mesh(new THREE.LatheGeometry(profile, SPOOL_SEGMENTS), material);
  body.name = 'spool';
  return body;
}

function makeThread(threadColor) {
  const height = SPOOL_HEIGHT - 2 * FLANGE - 0.004;
  const material = new THREE.MeshStandardMaterial({ color: threadColor, roughness: 0.85 });
  const thread = new THREE.Mesh(new THREE.CylinderGeometry(WOUND_RADIUS, WOUND_RADIUS, height, SPOOL_SEGMENTS), material);
  thread.name = 'thread';
  return thread;
}

export function createSpool({ threadColor = '#C9A227' } = {}) {
  const spool = new THREE.Group();
  spool.add(makeBody(), makeThread(threadColor));
  return spool;
}
