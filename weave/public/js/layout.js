// WEAVE's quilt geometry in scene units: the block and tile grids, the puff and the fold, the rod and the
// shadow plane, and the slot maths #9's drag builds on. Pure: no imports, no DOM, nothing built on import.

// cols, rows, block, sashing and border are #6's geometry names: paintSashing, sashingSize and quiltSize read
// them straight off LAYOUT, so these five must keep their names and meaning.
const cols = 4;
const rows = 3;
const block = 1.0;
const sashing = 0.14;
const border = 0.14;
const tileGutter = 0.24;
const quiltW = cols * block + (cols - 1) * sashing + 2 * border;
const quiltH = rows * block + (rows - 1) * sashing + 2 * border;
const rodRadius = 0.035;

const BASE = {
  cols, rows, block, sashing, border,
  slots: cols * rows,
  segments: 40,
  tileGutter,
  quiltW,
  quiltH,
  pitch: block + sashing,
  tilePitch: block + tileGutter,
  tilesW: cols * block + (cols - 1) * tileGutter,
  tilesH: rows * block + (rows - 1) * tileGutter,
  // The puff's height at a block's centre.
  puff: 0.05,
  // The fold's three ripple amplitudes; they sum to at most 0.5, which bounds |foldZ|.
  fold: Object.freeze([0.06, 0.035, 0.02]),
  // The hanging rod sits just above the top edge; its end caps are spheres larger than the rod.
  rod: Object.freeze({ y: quiltH / 2 + 0.05, radius: rodRadius, capRadius: 0.06, halfLength: quiltW / 2 + 0.12 }),
  // The ambient motion's amplitude ceilings in radians: sway about the rod, the pointer tilt about x and y.
  ambientMax: Object.freeze({ sway: 0.03, tiltX: 0.025, tiltY: 0.06 }),
  maxTiltDeg: 2.5,
};

const rotX = ([x, y, z], a) => [x, Math.cos(a) * y - Math.sin(a) * z, Math.sin(a) * y + Math.cos(a) * z];
const rotY = ([x, y, z], a) => [Math.cos(a) * x + Math.sin(a) * z, y, -Math.sin(a) * x + Math.cos(a) * z];

// The largest |dz| of any quilt corner under the ambient rotations about the rod pivot (0, rod.y, 0): the sway
// about x, then the tilts about x and y (R = Ry(tiltY) Rx(tiltX) Rx(sway)), each at -max, 0 and +max.
export function maxExcursion(layout = BASE) {
  const { quiltW: W, quiltH: H, rod, ambientMax: amp } = layout;
  const span = (a) => [-a, 0, a];
  let worst = 0;
  for (const cx of [-W / 2, W / 2]) {
    for (const cy of [-H / 2, H / 2]) {
      for (const sway of span(amp.sway)) {
        for (const tiltX of span(amp.tiltX)) {
          for (const tiltY of span(amp.tiltY)) {
            const v = rotY(rotX(rotX([cx, cy - rod.y, 0], sway), tiltX), tiltY);
            worst = Math.max(worst, Math.abs(v[2]));
          }
        }
      }
    }
  }
  return worst;
}

// shadowZ clears the deepest fold (|foldZ| <= 0.5) at full sway and tilt, with 0.1 to spare.
export const LAYOUT = Object.freeze({ ...BASE, shadowZ: -(0.5 + maxExcursion(BASE) + 0.1) });

// Slot i's centre, row-major from the top left: the quilt grid at pitch 1.14, or the tile grid at 1.24.
export function slotCentre(i, mode = 'quilt') {
  const col = i % cols;
  const row = Math.floor(i / cols);
  if (mode === 'tiles') {
    const { tilesW, tilesH, tilePitch } = LAYOUT;
    return [-tilesW / 2 + block / 2 + col * tilePitch, tilesH / 2 - block / 2 - row * tilePitch];
  }
  const { pitch } = LAYOUT;
  return [-quiltW / 2 + border + block / 2 + col * pitch, quiltH / 2 - border - block / 2 - row * pitch];
}

// A block's puff at (u, v) in [0, 1]^2: a polynomial, so it is exactly 0 on every edge.
export function puffZ(u, v) {
  return LAYOUT.puff * 16 * u * (1 - u) * v * (1 - v);
}

// #21's seam (D10): #21 owns the installer that sets this and the bilinear sampling of its drape; until then
// it stays null and foldZ draws the hand-written fold. foldZ never fetches.
let drape = null;

// The quilt's fold: three vertical ripples, faded in from 0 at the top edge (so the edge stays straight under
// the rod) to full at the bottom. |z| <= the sum of LAYOUT.fold <= 0.5 everywhere.
export function foldZ(x, y) {
  if (drape) return drape(x, y);
  const t = Math.min(1, Math.max(0, (quiltH / 2 - y) / quiltH));
  const fall = t * t * (3 - 2 * t);
  const [a, b, c] = LAYOUT.fold;
  return fall * (a * Math.sin(2.1 * x + 0.4) + b * Math.sin(4.3 * x + 0.6 * y + 1.7) + c * Math.sin(7.9 * x + 1.3 * y - 0.9));
}

// A new order with the item at `from` moved to `to`; the input is untouched.
export function moveItem(order, from, to) {
  const next = order.slice();
  const [item] = next.splice(from, 1);
  next.splice(to, 0, item);
  return next;
}

// The slot whose centre is nearest (x, y) in that mode's grid; ties go to the lower index, an unknown mode
// counts as 'quilt', and a point that compares with nothing (NaN) gives 0, so the result is always 0-11.
export function nearestSlot(x, y, mode = 'quilt') {
  const grid = mode === 'tiles' ? 'tiles' : 'quilt';
  let best = 0;
  let bestD = Infinity;
  for (let i = 0; i < LAYOUT.slots; i += 1) {
    const [cx, cy] = slotCentre(i, grid);
    const d = (x - cx) ** 2 + (y - cy) ** 2;
    if (d < bestD) {
      best = i;
      bestD = d;
    }
  }
  return best;
}
