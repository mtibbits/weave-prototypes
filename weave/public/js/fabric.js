// WEAVE's cloth painters: the fabric prints, the sashing and the scene textures, drawn onto a canvas they
// are handed. No DOM writes beyond that canvas, no ambient inputs (randomness comes only from rngFor).
// Any canvas passed to a painter and later read back or hashed (by #7, #18 or #20) must come from
// makeCanvas. Hashes are comparable only within one machine and one Playwright/Chromium build.
//
// Painters never resize the canvas they are given: they draw in a fixed design space and scale it to the
// canvas, making the same rngFor draws in the same order at every size, so one canvas is one block (or one
// texture) at any resolution. Each starts from a cleared canvas and leaves its state as it found it, so a
// repaint into the same canvas is byte-identical.
import { rngFor } from './random.js';

// The one context door, and the only getContext call in the painters. Chromium rasters a default 2D canvas
// on the GPU and silently demotes it to software after several readbacks, which changes its bytes; asking
// for willReadFrequently on the first call keeps the canvas in software from the first stroke, so a canvas
// that is read back or hashed always gives the same bytes. (A canvas whose context was already made
// elsewhere keeps that context: hence the rule above about where canvases come from.)
export function contextOf(canvas) {
  return canvas.getContext('2d', { willReadFrequently: true });
}

// The one canvas door: a canvas whose context is software-rastered from the start.
export function makeCanvas(width, height = width) {
  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  contextOf(canvas);
  return canvas;
}

// Save, reset to a known state and clear (unless `clear` is false, for a layer drawn over a fresh paint);
// every painter pairs this with ctx.restore().
export function beginPaint(canvas, { clear = true } = {}) {
  const ctx = contextOf(canvas);
  ctx.save();
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.globalAlpha = 1;
  ctx.globalCompositeOperation = 'source-over';
  ctx.shadowColor = 'transparent';
  ctx.shadowBlur = 0;
  ctx.shadowOffsetX = 0;
  ctx.shadowOffsetY = 0;
  ctx.filter = 'none';
  ctx.imageSmoothingEnabled = true;
  ctx.imageSmoothingQuality = 'low';
  ctx.lineWidth = 1;
  ctx.lineCap = 'butt';
  ctx.lineJoin = 'miter';
  ctx.miterLimit = 10;
  ctx.setLineDash([]);
  ctx.lineDashOffset = 0;
  ctx.font = '10px sans-serif';
  ctx.direction = 'ltr';
  ctx.textAlign = 'start';
  ctx.textBaseline = 'alphabetic';
  ctx.letterSpacing = '0px';
  ctx.wordSpacing = '0px';
  ctx.fontKerning = 'auto';
  ctx.fontStretch = 'normal';
  ctx.fontVariantCaps = 'normal';
  ctx.textRendering = 'auto';
  if (clear) ctx.clearRect(0, 0, canvas.width, canvas.height);
  return ctx;
}

function deepFreeze(value) {
  if (value && typeof value === 'object') {
    Object.values(value).forEach(deepFreeze);
    Object.freeze(value);
  }
  return value;
}

export const FABRIC_KINDS = Object.freeze(['calico', 'gingham', 'dots', 'stripe', 'chambray', 'plaid', 'solid', 'people']);

// colors[0] is always the ground; the rest are the print's inks.
export const FABRICS = deepFreeze({
  'coalesce-people': { kind: 'people', colors: ['#E9E2D3', '#1D5E5B', '#C4623A', '#D9A441', '#5C625F'] },
  'mustard-calico': { kind: 'calico', colors: ['#D9A441', '#7A4E12', '#F3EEE4'] },
  'indigo-dots': { kind: 'dots', colors: ['#2E3F73', '#F3EEE4'] },
  'rose-gingham': { kind: 'gingham', colors: ['#F6E3E3', '#C25A6B'] },
  'sage-stripe': { kind: 'stripe', colors: ['#B9C7A8', '#6E8460', '#F3EEE4'] },
  'sky-chambray': { kind: 'chambray', colors: ['#9DB8D3', '#5F7FA3'] },
  'plum-plaid': { kind: 'plaid', colors: ['#6B3A5B', '#A86B91', '#E0C36A'] },
  'brick-solid': { kind: 'solid', colors: ['#A2462E'] },
  'olive-calico': { kind: 'calico', colors: ['#7C7A3A', '#3F3D1A', '#E8DFC0'] },
  'navy-dots': { kind: 'dots', colors: ['#1F2B47', '#E9E2D3'] },
  'terracotta-gingham': { kind: 'gingham', colors: ['#F4E1D2', '#C4623A'] },
  muslin: { kind: 'solid', colors: ['#EFE6D2'] },
});

// The one door: unknown, absent, non-string and prototype keys all get muslin.
export function fabricFor(name) {
  return typeof name === 'string' && Object.hasOwn(FABRICS, name) ? FABRICS[name] : FABRICS.muslin;
}

const DESIGN = 512;
const TAU = Math.PI * 2;

function disc(ctx, x, y, r) {
  ctx.beginPath();
  ctx.arc(x, y, r, 0, TAU);
  ctx.fill();
}

const PRINTS = {
  solid() {},
  calico(ctx, [, ink, eye], rng) {
    for (let row = 0; row < 8; row += 1) {
      for (let col = 0; col < 8; col += 1) {
        const x = col * 64 + 32 + (rng() - 0.5) * 36;
        const y = row * 64 + 32 + (rng() - 0.5) * 36;
        const turn = rng() * TAU;
        ctx.fillStyle = ink;
        for (let p = 0; p < 5; p += 1) {
          const a = turn + (p * TAU) / 5;
          disc(ctx, x + Math.cos(a) * 9, y + Math.sin(a) * 9, 7);
        }
        ctx.fillStyle = eye;
        disc(ctx, x, y, 4.5);
      }
    }
  },
  gingham(ctx, [, ink], rng) {
    const phase = Math.floor(rng() * 64);
    ctx.fillStyle = ink;
    ctx.globalAlpha = 0.45;
    for (let i = -1; i < 9; i += 1) {
      ctx.fillRect(i * 64 + phase, 0, 32, DESIGN);
      ctx.fillRect(0, i * 64 + phase, DESIGN, 32);
    }
    ctx.globalAlpha = 1;
  },
  dots(ctx, [, ink], rng) {
    const phase = rng() * 64;
    ctx.fillStyle = ink;
    for (let row = -1; row < 9; row += 1) {
      for (let col = -1; col < 9; col += 1) disc(ctx, col * 64 + (row % 2 ? 32 : 0) + phase, row * 64 + 32, 11);
    }
  },
  stripe(ctx, [, ink, thread], rng) {
    const phase = Math.floor(rng() * 64);
    for (let i = -1; i < 9; i += 1) {
      ctx.fillStyle = ink;
      ctx.fillRect(i * 64 + phase, 0, 22, DESIGN);
      ctx.fillStyle = thread;
      ctx.fillRect(i * 64 + phase + 36, 0, 4, DESIGN);
    }
  },
  chambray(ctx, [, ink], rng) {
    ctx.fillStyle = ink;
    for (let y = 0; y < DESIGN; y += 4) {
      ctx.globalAlpha = 0.15 + rng() * 0.2;
      ctx.fillRect(0, y, DESIGN, 2);
    }
    ctx.fillStyle = '#FFFFFF';
    ctx.globalAlpha = 0.12;
    for (let x = 0; x < DESIGN; x += 6) ctx.fillRect(x, 0, 2, DESIGN);
    ctx.globalAlpha = 1;
  },
  plaid(ctx, [, ink, thread], rng) {
    const phase = Math.floor(rng() * 128);
    ctx.fillStyle = ink;
    ctx.globalAlpha = 0.4;
    for (let i = -1; i < 5; i += 1) {
      ctx.fillRect(i * 128 + phase, 0, 44, DESIGN);
      ctx.fillRect(0, i * 128 + phase, DESIGN, 44);
    }
    ctx.globalAlpha = 0.85;
    ctx.fillStyle = thread;
    for (let i = -1; i < 5; i += 1) {
      ctx.fillRect(i * 128 + phase + 80, 0, 4, DESIGN);
      ctx.fillRect(0, i * 128 + phase + 80, DESIGN, 4);
    }
    ctx.globalAlpha = 1;
  },
  // Coalesce's crowd: rows of small people in the brand inks.
  people(ctx, [, ...inks], rng) {
    for (let row = 0; row < 10; row += 1) {
      for (let col = 0; col < 12; col += 1) {
        const x = col * 44 + (row % 2 ? 22 : 0) + (rng() - 0.5) * 10;
        const y = row * 54 + 18 + (rng() - 0.5) * 8;
        ctx.fillStyle = inks[Math.floor(rng() * inks.length)];
        disc(ctx, x, y, 6.5);
        ctx.beginPath();
        ctx.moveTo(x - 10, y + 30);
        ctx.quadraticCurveTo(x - 10, y + 10, x, y + 10);
        ctx.quadraticCurveTo(x + 10, y + 10, x + 10, y + 30);
        ctx.closePath();
        ctx.fill();
      }
    }
  },
};

// A fine plain-weave overlay: light weft and dark warp threads every 4 design units.
function weaveOverlay(ctx) {
  ctx.fillStyle = '#FFFFFF';
  ctx.globalAlpha = 0.07;
  for (let y = 1; y < DESIGN; y += 4) ctx.fillRect(0, y, DESIGN, 1);
  ctx.fillStyle = '#000000';
  ctx.globalAlpha = 0.05;
  for (let x = 3; x < DESIGN; x += 4) ctx.fillRect(x, 0, 1, DESIGN);
  ctx.globalAlpha = 1;
}

// The cloth alone: the print plus the weave, with no icon or name (D1). Fixed name and signature for #18.
export function paintFabric(canvas, fabric, seedId) {
  const { kind, colors } = fabricFor(fabric);
  const rng = rngFor(seedId, 'fabric');
  const ctx = beginPaint(canvas);
  ctx.scale(canvas.width / DESIGN, canvas.height / DESIGN);
  ctx.fillStyle = colors[0];
  ctx.fillRect(0, 0, DESIGN, DESIGN);
  PRINTS[kind](ctx, colors, rng);
  weaveOverlay(ctx);
  ctx.restore();
}

// --- The sashing. ---
// Geometry is { cols, rows, block, sashing, border } in quilt units; extra fields are ignored.
// Contract note for #7: LAYOUT carries these five names.

export const SASHING_COLORS = Object.freeze({ muslin: '#EFE6D2', cornerstone: '#C4623A', binding: '#1D5E5B' });

export function quiltSize({ cols, rows, block, sashing, border }) {
  return [cols * block + (cols - 1) * sashing + 2 * border, rows * block + (rows - 1) * sashing + 2 * border];
}

export function sashingSize(geometry, pxPerUnit = 256) {
  return quiltSize(geometry).map((side) => Math.ceil(side * pxPerUnit));
}

// Muslin, cornerstones at the interior crossings, and the binding band over the border. Fixed name and
// signature for #18. Mapping: pixel (px, py) <-> u = px / width, v = 1 - py / height, with the quilt filling
// the canvas, so quilt point (x, y) about the centre sits at u = (x + W/2) / W, v = (y + H/2) / H for quilt
// size W x H. Row 0 is the top, which matches three.js's default flipY.
export function paintSashing(canvas, geometry) {
  const { cols, rows, block, sashing, border } = geometry;
  const [qw, qh] = quiltSize(geometry);
  const rng = rngFor('sashing', 'speckle');
  const ctx = beginPaint(canvas);
  ctx.scale(canvas.width / qw, canvas.height / qh);
  ctx.fillStyle = SASHING_COLORS.binding;
  ctx.fillRect(0, 0, qw, qh);
  ctx.fillStyle = SASHING_COLORS.muslin;
  ctx.fillRect(border, border, qw - 2 * border, qh - 2 * border);
  ctx.fillStyle = '#786446';
  ctx.globalAlpha = 0.18;
  for (let i = 0; i < 900; i += 1) {
    const x = border + rng() * (qw - 2 * border);
    const y = border + rng() * (qh - 2 * border);
    disc(ctx, x, y, 0.003 + rng() * 0.004);
  }
  ctx.globalAlpha = 1;
  ctx.fillStyle = SASHING_COLORS.cornerstone;
  for (let i = 1; i < cols; i += 1) {
    for (let j = 1; j < rows; j += 1) {
      ctx.fillRect(border + i * block + (i - 1) * sashing, border + j * block + (j - 1) * sashing, sashing, sashing);
    }
  }
  ctx.restore();
}

// --- Scene textures. Each defines its own scale from the canvas it is given. ---

// A table top: grain lines across a 1024 x 256 design space.
export function paintWood(canvas) {
  const rng = rngFor('wood', 'grain');
  const ctx = beginPaint(canvas);
  ctx.scale(canvas.width / 1024, canvas.height / 256);
  ctx.fillStyle = '#8A5A36';
  ctx.fillRect(0, 0, 1024, 256);
  for (let i = 0; i < 40; i += 1) {
    const y0 = rng() * 256;
    const amp = 2 + rng() * 6;
    const freq = 0.004 + rng() * 0.01;
    const phase = rng() * TAU;
    ctx.strokeStyle = i % 2 ? '#6B4227' : '#A87650';
    ctx.globalAlpha = 0.35 + rng() * 0.25;
    ctx.lineWidth = 1 + rng() * 3;
    ctx.beginPath();
    for (let x = 0; x <= 1024; x += 32) {
      const y = y0 + amp * Math.sin(x * freq + phase);
      if (x === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();
  }
  ctx.restore();
}

// A tileable tangent-space normal map of a plain weave (data, not colour): rgb = n * 0.5 + 0.5, with a whole
// number of periods per side so it wraps without a seam.
export function paintWeaveNormal(canvas) {
  const { width: w, height: h } = canvas;
  const phase = rngFor('weave-normal', 'weave')();
  const periods = 16;
  const strength = 0.6;
  const ctx = beginPaint(canvas);
  const image = ctx.createImageData(w, h);
  for (let py = 0; py < h; py += 1) {
    const b = (TAU * periods * (py + 0.5)) / h;
    for (let px = 0; px < w; px += 1) {
      const a = (TAU * periods * (px + 0.5)) / w + phase * TAU;
      const gx = strength * Math.cos(a) * Math.sin(b);
      const gy = strength * Math.sin(a) * Math.cos(b);
      const len = Math.hypot(gx, gy, 1);
      const i = (py * w + px) * 4;
      image.data[i] = Math.round((-gx / len * 0.5 + 0.5) * 255);
      image.data[i + 1] = Math.round((-gy / len * 0.5 + 0.5) * 255);
      image.data[i + 2] = Math.round((1 / len * 0.5 + 0.5) * 255);
      image.data[i + 3] = 255;
    }
  }
  ctx.putImageData(image, 0, 0);
  ctx.restore();
}

// A soft elliptical contact shadow with fully transparent corners.
export function paintShadow(canvas) {
  const mid = 0.5 + rngFor('shadow', 'soft')() * 0.1;
  const ctx = beginPaint(canvas);
  ctx.translate(canvas.width / 2, canvas.height / 2);
  ctx.scale(canvas.width / 2, canvas.height / 2);
  const gradient = ctx.createRadialGradient(0, 0, 0, 0, 0, 1);
  gradient.addColorStop(0, 'rgba(0, 0, 0, 0.45)');
  gradient.addColorStop(mid, 'rgba(0, 0, 0, 0.2)');
  gradient.addColorStop(1, 'rgba(0, 0, 0, 0)');
  ctx.fillStyle = gradient;
  disc(ctx, 0, 0, 1);
  ctx.restore();
}
