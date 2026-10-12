// WEAVE's block faces and dashboard tiles, the name rule they share, and the wait for the web fonts.
// Painters draw onto the canvas they are handed and nothing else; see fabric.js for the canvas rules.
import { NO_SAMPLE } from './dom.js';
import { beginPaint, contextOf, makeCanvas, paintFabric } from './fabric.js';
import { iconFor } from './icons.js';
import { rngFor } from './random.js';

// Every face font: the names and labels are Sans 700, and the chalk "?" is Serif Italic.
export const FONT_SPECS = ['700 48px "Instrument Sans"', '400 48px "Instrument Serif"',
  'italic 400 48px "Instrument Serif"'];

// Resolves true once every face font has loaded, false when one fails or the wait runs out; never rejects.
// It warns once, when the outcome is decided, and ignores whatever settles later. The timeout is a timer,
// never a clock reading, so a frozen clock cannot stall it.
export function fontsReady({ timeoutMs = 3000 } = {}) {
  return new Promise((resolve) => {
    let decided = false;
    let timer;
    const decide = (ok, warnings) => {
      if (decided) return;
      decided = true;
      clearTimeout(timer);
      warnings.forEach((warning) => console.warn(warning));
      resolve(ok);
    };
    timer = setTimeout(() => decide(false, [`WEAVE: the web fonts had not loaded after ${timeoutMs / 1000} s, `
      + 'so the faces are painted in the fallback font.']), timeoutMs);
    Promise.allSettled(FONT_SPECS.map((spec) => document.fonts.load(spec))).then((results) => {
      // A load that matches no @font-face resolves to an empty list: that is a failure too.
      const failed = FONT_SPECS.filter((_, i) => results[i].status === 'rejected' || results[i].value.length === 0);
      decide(failed.length === 0, failed.map((spec) => `WEAVE: the web font ${spec} could not load, `
        + 'so the faces are painted in the fallback font.'));
    });
  });
}

// --- The name rule, shared by faces and tiles. Sizes are at 512 px and scale by s = canvas.width / 512. ---

export const NAME_PX = 48;
export const NAME_MAX = 0.6; // of the block
export const TILE_PAD = 40;
export const TILE_NAME_PX = 40;
export const TILE_NAME_MAX = 0.8; // of the tile's text column (the tile minus its padding)

export const nameFont = (px) => `700 ${px}px "Instrument Sans", system-ui, sans-serif`;

// The smallest size a name is ever set at; below it, the text is drawn compressed into its width.
export const nameFloor = (basePx) => Math.max(8, Math.round(basePx / 4));

// The one rule: a name that fits at basePx is one line; a single word is one line, shrunk; otherwise line 1
// is the longest word prefix (at least one word) that fits at basePx and line 2 is the rest. px is the
// largest whole size, no larger than basePx and no smaller than the floor, at which every line fits; both
// lines share it. Measures with ctx and leaves its font as it was.
export function fitName(ctx, name, maxWidth, basePx) {
  const saved = ctx.font;
  const width = (text, px) => {
    ctx.font = nameFont(px);
    return ctx.measureText(text).width;
  };
  const words = String(name).trim().split(/\s+/);
  const whole = words.join(' ');
  let lines = [whole];
  if (words.length > 1 && width(whole, basePx) > maxWidth) {
    let n = 1;
    while (n < words.length - 1 && width(words.slice(0, n + 1).join(' '), basePx) <= maxWidth) n += 1;
    lines = [words.slice(0, n).join(' '), words.slice(n).join(' ')];
  }
  const floor = nameFloor(basePx);
  let px = basePx;
  while (px > floor && lines.some((line) => width(line, px) > maxWidth)) px -= 1;
  ctx.font = saved;
  return { lines, px };
}

// --- Faces and tiles. Both draw in a 512 design space scaled to the canvas. ---

export const FACE_KINDS = ['sewn', 'planned', 'suggest', 'filler'];
export const SAMPLE_CAPTION = 'sample';
export const OPEN_CUE = 'Open →';
export const TILE_SOON = 'Coming soon';
export const FACE_SOON = 'coming soon';
export const SUGGEST_TEXT = 'Suggest a panel';

const DESIGN = 512;
const INK = '#1E2422';
const MUTED = '#5C625F';
const TEAL = '#1D5E5B';
const PAPER = '#FFFDF8';
const LABEL = '#FBF7EE';
const CHALK = '#3E6A8A';
const MUSLIN = '#EFE6D2';
const THREAD = '#2A2420';
const FLOSS = '#F7F1E3';
const FELT = { base: '#1D5E5B', accent: '#C4623A', light: '#F3EEE4' };
const chalkMark = (px) => `italic 400 ${px}px "Instrument Serif", Georgia, serif`;
const sans = (px, weight = 700) => `${weight} ${px}px "Instrument Sans", system-ui, sans-serif`;

// A face's kind from its entry's status: live is sewn, and no entry is a filler.
export function faceKind(entry) {
  if (!entry) return 'filler';
  if (entry.status === 'live') return 'sewn';
  return entry.status === 'planned' || entry.status === 'suggest' ? entry.status : 'filler';
}

// A tile's bar heights (each 0.25-1), drawn from the panel id alone, so the sample never moves them.
export function barHeights(id) {
  const rng = rngFor(id, 'bars');
  return Array.from({ length: 7 }, () => 0.25 + 0.75 * rng());
}

function startDesign(canvas, clear) {
  const ctx = beginPaint(canvas, { clear });
  ctx.scale(canvas.width / DESIGN, canvas.height / DESIGN);
  return ctx;
}

// Draws fitName's lines from `top` (each line's em box stacked at 1.1 px). At the floor the text is drawn
// compressed into maxWidth, so it always fits.
function setLines(ctx, { lines, px }, x, top, maxWidth, basePx, font = nameFont) {
  ctx.font = font(px);
  lines.forEach((line, i) => {
    const y = top + px * (0.9 + i * 1.1);
    if (px === nameFloor(basePx)) ctx.fillText(line, x, y, maxWidth);
    else ctx.fillText(line, x, y);
  });
}

// One line, shrunk to fit by the name rule's floor; never wrapped. `y` is its baseline at basePx.
function fitLine(ctx, text, x, y, maxWidth, basePx, weight = 700) {
  const font = (px) => sans(px, weight);
  let px = basePx;
  ctx.font = font(px);
  while (px > nameFloor(basePx) && ctx.measureText(text).width > maxWidth) {
    px -= 1;
    ctx.font = font(px);
  }
  setLines(ctx, { lines: [text], px }, x, y - px * 0.9, maxWidth, basePx, font);
}

// The satin-stitch sheen laid over an embroidered name: fine diagonal floss.
function satin(ctx) {
  const tile = makeCanvas(6);
  const t = contextOf(tile);
  t.strokeStyle = 'rgba(255, 255, 255, 0.3)';
  t.lineWidth = 1.2;
  t.beginPath();
  t.moveTo(-1, 7);
  t.lineTo(7, -1);
  t.stroke();
  return ctx.createPattern(tile, 'repeat');
}

// The felt appliqué: tone fills with a soft drop shadow, a blanket stitch round each piece, then the running
// stitch. Shadows ignore the transform, so they are scaled by hand (k device pixels per icon unit).
function drawFelt(ctx, icon, x, y, size, k, dashOffset) {
  ctx.save();
  ctx.translate(x, y);
  ctx.scale(size / 100, size / 100);
  ctx.shadowColor = 'rgba(30, 36, 34, 0.35)';
  ctx.shadowBlur = 3 * k;
  ctx.shadowOffsetX = 1.2 * k;
  ctx.shadowOffsetY = 1.6 * k;
  for (const { d, tone } of icon.felt) {
    ctx.fillStyle = FELT[tone];
    ctx.fill(new Path2D(d));
  }
  ctx.shadowColor = 'transparent';
  ctx.strokeStyle = THREAD;
  ctx.globalAlpha *= 0.7;
  ctx.lineWidth = 0.8;
  ctx.setLineDash([2.4, 1.8]);
  ctx.lineDashOffset = dashOffset;
  for (const { d } of icon.felt) ctx.stroke(new Path2D(d));
  ctx.strokeStyle = FLOSS;
  ctx.lineWidth = 1.1;
  ctx.setLineDash([3.5, 2.5]);
  for (const d of icon.stitch) ctx.stroke(new Path2D(d));
  ctx.restore();
}

// Tailor's chalk: each piece's outline, traced twice with a seeded wobble.
function drawChalk(ctx, icon, x, y, size, rng) {
  ctx.save();
  ctx.translate(x, y);
  ctx.scale(size / 100, size / 100);
  ctx.strokeStyle = CHALK;
  ctx.lineWidth = 1.6;
  ctx.lineCap = 'round';
  for (const pass of [0.85, 0.45]) {
    ctx.globalAlpha = pass;
    for (const { d } of icon.felt) {
      ctx.save();
      ctx.translate((rng() - 0.5) * 1.4, (rng() - 0.5) * 1.4);
      ctx.stroke(new Path2D(d));
      ctx.restore();
    }
  }
  ctx.restore();
}

const ICON_AT = { x: 156, y: 176, size: 240 };
const NAME_AT = { x: 48, y: 44 };

function paintSewn(canvas, entry, rng) {
  paintFabric(canvas, entry.fabric, entry.id);
  const ctx = startDesign(canvas, false);
  const k = canvas.width / DESIGN;
  ctx.strokeStyle = FLOSS;
  ctx.globalAlpha = 0.8;
  ctx.lineWidth = 2.5;
  ctx.setLineDash([10, 7]);
  ctx.lineDashOffset = rng() * 17;
  ctx.strokeRect(16, 16, DESIGN - 32, DESIGN - 32);
  ctx.globalAlpha = 1;
  ctx.setLineDash([]);
  const limit = NAME_MAX * DESIGN;
  const fit = fitName(ctx, entry.name, limit, NAME_PX);
  ctx.font = nameFont(fit.px);
  const widest = Math.min(limit, Math.max(...fit.lines.map((line) => ctx.measureText(line).width)));
  ctx.fillStyle = LABEL;
  ctx.beginPath();
  ctx.roundRect(NAME_AT.x - 14, NAME_AT.y - 10, widest + 28, fit.px * (fit.lines.length * 1.1 + 0.2) + 20, 8);
  ctx.fill();
  ctx.fillStyle = INK;
  setLines(ctx, fit, NAME_AT.x, NAME_AT.y, limit, NAME_PX);
  ctx.fillStyle = satin(ctx);
  setLines(ctx, fit, NAME_AT.x, NAME_AT.y, limit, NAME_PX);
  drawFelt(ctx, iconFor(entry.icon), ICON_AT.x, ICON_AT.y, ICON_AT.size, k * (ICON_AT.size / 100), rng() * 4);
  ctx.restore();
}

function paintPlanned(canvas, entry, rng) {
  paintFabric(canvas, entry.fabric, entry.id);
  const ctx = startDesign(canvas, false);
  ctx.fillStyle = MUSLIN;
  ctx.globalAlpha = 0.62;
  ctx.fillRect(0, 0, DESIGN, DESIGN);
  ctx.globalAlpha = 1;
  drawChalk(ctx, iconFor(entry.icon), ICON_AT.x, ICON_AT.y, ICON_AT.size, rng);
  const limit = NAME_MAX * DESIGN;
  ctx.fillStyle = CHALK;
  setLines(ctx, fitName(ctx, entry.name, limit, NAME_PX), NAME_AT.x, NAME_AT.y, limit, NAME_PX);
  ctx.font = nameFont(28);
  ctx.fillText(FACE_SOON, NAME_AT.x, 468);
  ctx.restore();
}

function paintSuggest(canvas, entry) {
  paintFabric(canvas, 'muslin', entry.id);
  const ctx = startDesign(canvas, false);
  ctx.fillStyle = CHALK;
  ctx.textAlign = 'center';
  ctx.globalAlpha = 0.85;
  ctx.font = chalkMark(240);
  ctx.fillText('?', DESIGN / 2, 320);
  ctx.globalAlpha = 1;
  const limit = NAME_MAX * DESIGN;
  setLines(ctx, fitName(ctx, SUGGEST_TEXT, limit, 36), DESIGN / 2, 372, limit, 36);
  ctx.restore();
}

// Paints one block face. `kind` wins over the entry's status (#10's setFace); an unknown kind, or no entry,
// paints as a filler, which is exactly paintFabric(canvas, 'muslin', 'filler').
export function paintFace(canvas, entry, kind) {
  const k = entry && FACE_KINDS.includes(kind) ? kind : 'filler';
  if (k === 'filler') {
    paintFabric(canvas, 'muslin', 'filler');
    return;
  }
  const rng = rngFor(entry.id, 'face');
  if (k === 'sewn') paintSewn(canvas, entry, rng);
  else if (k === 'planned') paintPlanned(canvas, entry, rng);
  else paintSuggest(canvas, entry);
}

const COLUMN = DESIGN - 2 * TILE_PAD;
const VALUE_WIDTH = 240; // the value, unit and caption share the tile with the bars on the right

function dashedCard(ctx) {
  ctx.strokeStyle = MUTED;
  ctx.lineWidth = 3;
  ctx.setLineDash([14, 10]);
  ctx.beginPath();
  ctx.roundRect(16, 16, DESIGN - 32, DESIGN - 32, 26);
  ctx.stroke();
  ctx.setLineDash([]);
}

function tileName(ctx, text, x = TILE_PAD, top = 176) {
  const limit = TILE_NAME_MAX * COLUMN;
  ctx.fillStyle = INK;
  setLines(ctx, fitName(ctx, text, limit, TILE_NAME_PX), x, top, limit, TILE_NAME_PX);
}

function liveTile(ctx, canvas, entry) {
  const swatch = makeCanvas(canvas.width);
  paintFabric(swatch, entry.fabric, entry.id);
  ctx.drawImage(swatch, 0, 0, swatch.width, (swatch.width * 120) / DESIGN, 0, 0, DESIGN, 120);
  ctx.fillStyle = LABEL;
  ctx.beginPath();
  ctx.arc(TILE_PAD + 40, 120, 46, 0, Math.PI * 2);
  ctx.fill();
  drawFelt(ctx, iconFor(entry.icon), TILE_PAD + 4, 84, 72, (canvas.width / DESIGN) * 0.72, 0);
  tileName(ctx, entry.name);
  if (entry.sample) {
    ctx.fillStyle = TEAL;
    fitLine(ctx, String(entry.sample.value), TILE_PAD, 340, VALUE_WIDTH, 96);
    if (entry.sample.unit !== '') {
      ctx.fillStyle = INK;
      fitLine(ctx, entry.sample.unit, TILE_PAD, 378, VALUE_WIDTH, 26, 600);
    }
    ctx.fillStyle = MUTED;
    ctx.font = sans(18, 600);
    ctx.fillText(SAMPLE_CAPTION, TILE_PAD, 406);
  } else {
    ctx.fillStyle = MUTED;
    fitLine(ctx, NO_SAMPLE, TILE_PAD, 340, VALUE_WIDTH, 30);
  }
  ctx.fillStyle = TEAL;
  ctx.globalAlpha = 0.85;
  barHeights(entry.id).forEach((h, i) => ctx.fillRect(304 + i * 25, 406 - h * 90, 18, h * 90));
  ctx.globalAlpha = 1;
  ctx.font = sans(22);
  ctx.textAlign = 'right';
  ctx.fillText(OPEN_CUE, DESIGN - TILE_PAD, 476);
}

function plannedTile(ctx, canvas, entry) {
  dashedCard(ctx);
  ctx.globalAlpha = 0.55;
  drawFelt(ctx, iconFor(entry.icon), TILE_PAD + 4, 60, 80, (canvas.width / DESIGN) * 0.8, 0);
  ctx.globalAlpha = 1;
  tileName(ctx, entry.name);
  ctx.fillStyle = MUTED;
  ctx.font = sans(26, 600);
  ctx.fillText(TILE_SOON, TILE_PAD, 406);
}

function suggestTile(ctx) {
  dashedCard(ctx);
  ctx.fillStyle = CHALK;
  ctx.textAlign = 'center';
  ctx.font = chalkMark(170);
  ctx.fillText('?', DESIGN / 2, 260);
  tileName(ctx, SUGGEST_TEXT, DESIGN / 2, 320);
}

const TILES = { live: liveTile, planned: plannedTile, suggest: suggestTile };

// Paints one dashboard tile: a rounded card with transparent corners. No entry (or an unknown status) leaves
// the canvas clear. Only the bars use fillRect.
export function paintTile(canvas, entry) {
  const ctx = startDesign(canvas, true);
  const paint = entry && Object.hasOwn(TILES, entry.status) ? TILES[entry.status] : null;
  if (paint) {
    const card = new Path2D();
    card.roundRect(4, 4, DESIGN - 8, DESIGN - 8, 36);
    ctx.fillStyle = PAPER;
    ctx.fill(card);
    ctx.clip(card);
    paint(ctx, canvas, entry);
  }
  ctx.restore();
}
