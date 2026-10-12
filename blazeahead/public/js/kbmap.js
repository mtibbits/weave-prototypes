// The knowledge-base trail map. layoutMap() places the tree from tour-content.js on the kiosk's board, and drawMap()
// draws it through a painter: svgPainter() for the page (the unfolded map, and the map laid over the still image) or
// canvasPainter() for the 3D kiosk's texture. Board units are the real board's millimetres: 1380 x 880.

export const BOARD = { w: 1380, h: 880, margin: 30 };
export const TRAIL_COLORS = ['#2F6FA3', '#B8452A', '#3E7D4C', '#74509C', '#A0721A'];
export const PAPER = '#DCCDA6';      // the Blender paper's albedo, so the live board and the still match
export const MIN_SCALE = 0.6;
const INK = '#3B2A1C';
const CENTRE_FILL = '#E88E1F';
const PIN = '#C0392B';
const HERE_INK = '#7A2A20';
const RIM = '#F4EBD3';
const FADE = 0.26;                   // the other trails, while one is lit
const SIZES = { hub: 26, dest: 27, next: 25, centre: 30, here: 24 };
const NAME_FONT = 'Fraunces, Georgia, serif';
const PILL_FONT = 'Figtree, system-ui, sans-serif';
const CENTRE = [690, 455];
// where each hub stands (fractions of the board) and which way its destinations fan out (degrees, y down)
const SLOT = { top: [0.5, 0.29, 270], upperLeft: [0.27, 0.34, 205], upperRight: [0.73, 0.34, 335],
  lowerRight: [0.73, 0.73, 25], lowerLeft: [0.27, 0.73, 155] };
const SLOT_ORDER = ['top', 'upperLeft', 'upperRight', 'lowerRight', 'lowerLeft'];
const FAN_REACH = 115;      // from a hub pill's edge out to its destinations
const STAGGER = 55;         // with five destinations, every other one stands this much further out
const STEP_OUT = 45;        // a destination whose label clashes steps out this far (twice at most) before type shrinks
const NEXT_REACH = 130;     // from a destination out to its onward stops
const TURNS = [0, -30, 30, -60, 60, -90, 90];   // how an onward stop bends away from the board's edge (degrees)
const DOT = { dest: 12, next: 9 };
const GAP = 7;              // clear space kept around every label
const DEG = Math.PI / 180;
const D = Math.SQRT1_2;
// where a label may sit around its dot, and the direction each place faces
const SIDES = { above: [0, -1], below: [0, 1], left: [-1, 0], right: [1, 0], aboveRight: [D, -D], aboveLeft: [-D, -D],
  belowRight: [D, D], belowLeft: [-D, D] };

const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));
const overlap = (a, b) => a[0] < b[2] && b[0] < a[2] && a[1] < b[3] && b[1] < a[3];
const onBoard = (b) => b[0] >= BOARD.margin && b[1] >= BOARD.margin && b[2] <= BOARD.w - BOARD.margin
  && b[3] <= BOARD.h - BOARD.margin;

export const shortName = (name) => (name.length > 32 ? `${name.slice(0, 31).trimEnd()}…` : name);

function slotsFor(n) {
  if (n === 4) return ['upperLeft', 'upperRight', 'lowerRight', 'lowerLeft'];
  return SLOT_ORDER.slice(0, n);
}

// does the segment [x1, y1, x2, y2] cross the box? (Liang-Barsky)
function crosses(s, b) {
  let t0 = 0;
  let t1 = 1;
  const dx = s[2] - s[0];
  const dy = s[3] - s[1];
  for (const [p, q] of [[-dx, s[0] - b[0]], [dx, b[2] - s[0]], [-dy, s[1] - b[1]], [dy, b[3] - s[1]]]) {
    if (p === 0) {
      if (q < 0) return false;
    } else {
      const r = q / p;
      if (p < 0) t0 = Math.max(t0, r);
      else t1 = Math.min(t1, r);
      if (t0 > t1) return false;
    }
  }
  return true;
}

// do two segments cross?
function cut(a, b) {
  const side = (p, q, r) => Math.sign((q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0]));
  const a1 = [a[0], a[1]];
  const a2 = [a[2], a[3]];
  const b1 = [b[0], b[1]];
  const b2 = [b[2], b[3]];
  return side(a1, a2, b1) * side(a1, a2, b2) < 0 && side(b1, b2, a1) * side(b1, b2, a2) < 0;
}

// distance from a pill's centre to its edge along a direction
function edge(w, h, ang) {
  const c = Math.abs(Math.cos(ang));
  const s = Math.abs(Math.sin(ang));
  return Math.min(c > 1e-6 ? w / 2 / c : Infinity, s > 1e-6 ? h / 2 / s : Infinity);
}

// a label's box and text anchor, for one of the SIDES around a dot of radius r
function labelBox(side, x, y, r, tw, size) {
  const a = size * 0.78;
  const d = size * 0.24;
  if (side === 'above') return { box: [x - tw / 2, y - r - 6 - a - d, x + tw / 2, y - r - 6], tx: x, ty: y - r - 6 - d, anchor: 'middle' };
  if (side === 'below') return { box: [x - tw / 2, y + r + 6, x + tw / 2, y + r + 6 + a + d], tx: x, ty: y + r + 6 + a, anchor: 'middle' };
  if (side === 'left') return { box: [x - r - 9 - tw, y - (a + d) / 2, x - r - 9, y + (a + d) / 2], tx: x - r - 9, ty: y - (a + d) / 2 + a, anchor: 'end' };
  if (side === 'right') return { box: [x + r + 9, y - (a + d) / 2, x + r + 9 + tw, y + (a + d) / 2], tx: x + r + 9, ty: y - (a + d) / 2 + a, anchor: 'start' };
  const k = r + 4;          // diagonal: the label's near corner sits just clear of the dot
  const right = side.endsWith('Right');
  const x0 = right ? x + k : x - k - tw;
  const y0 = side.startsWith('above') ? y - k - a - d : y + k;
  return { box: [x0, y0, x0 + tw, y0 + a + d], tx: right ? x0 : x0 + tw, ty: y0 + a, anchor: right ? 'start' : 'end' };
}

function place(map, measure, scale, skips) {
  const sz = (k) => Math.round(SIZES[k] * scale * 10) / 10;
  const nameFont = (k) => `600 ${sz(k)}px ${NAME_FONT}`;
  const fixed = [];         // boxes nothing may overlap: pills, dots and the labels placed so far
  const segments = [];      // every line on the map
  const cw = measure(shortName(map.centre), nameFont('centre')) + 52;
  const centre = { name: map.centre, x: CENTRE[0], y: CENTRE[1], w: cw, h: 60 * Math.max(scale, 0.8), size: sz('centre') };
  const pills = [[centre.x - cw / 2, centre.y - centre.h / 2, centre.x + cw / 2, centre.y + centre.h / 2]];
  fixed.push(pills[0]);
  const here = { x: CENTRE[0], y: CENTRE[1] + 58, r: 10, tx: CENTRE[0], ty: CENTRE[1] + 98, size: sz('here') };
  const hereW = measure('you are here', `italic 500 ${here.size}px ${NAME_FONT}`);
  fixed.push([here.x - here.r, here.y - here.r, here.x + here.r, here.y + here.r]);
  fixed.push([here.tx - hereW / 2, here.ty - here.size * 0.78, here.tx + hereW / 2, here.ty + here.size * 0.24]);
  const slots = slotsFor(map.trails.length);
  const trails = map.trails.map((t, i) => {
    const [fx, fy, facing] = SLOT[slots[i]];
    const x = fx * BOARD.w;
    const y = fy * BOARD.h;
    const w = measure(shortName(t.name), `700 ${sz('hub')}px ${PILL_FONT}`) + 62;
    const h = 48 * Math.max(scale, 0.8);
    pills.push([x - w / 2, y - h / 2, x + w / 2, y + h / 2]);
    fixed.push(pills[pills.length - 1]);
    segments.push([CENTRE[0], CENTRE[1], x, y]);
    const n = t.destinations.length;
    const spread = Math.min(130, 40 * (n - 1)) * DEG;
    const destinations = t.destinations.map((d, j) => {
      const key = `${i}.${j}`;
      const ang = n > 1 ? facing * DEG - spread / 2 + (spread * j) / (n - 1) : facing * DEG;
      const reach = edge(w, h, ang) + FAN_REACH + (n >= 5 && j % 2 ? STAGGER : 0)
        + STEP_OUT * Math.min(2, skips.get(key) || 0);
      // keep the dot far enough in that its label fits centred above or below it
      const half = measure(shortName(d.name), nameFont('dest')) / 2 + 4;
      const dx = clamp(x + Math.cos(ang) * reach, BOARD.margin + half, BOARD.w - BOARD.margin - half);
      const dy = clamp(y + Math.sin(ang) * reach, BOARD.margin + 50, BOARD.h - BOARD.margin - 50);
      const dotBox = [dx - DOT.dest, dy - DOT.dest, dx + DOT.dest, dy + DOT.dest];
      fixed.push(dotBox);
      segments.push([x, y, dx, dy]);
      const own = Math.atan2(dy - y, dx - x);
      const m = d.next.length;
      const nspread = 40 * (m - 1) * DEG;
      const next = d.next.map((e, k) => {
        const nkey = `${key}.${k}`;
        const base = m > 1 ? own - nspread / 2 + (nspread * k) / (m - 1) : own;
        const tw = measure(shortName(e.name), nameFont('next'));
        let skip = skips.get(nkey) || 0;
        let spot = null;
        // straight on if there's room; otherwise bend away from the board's edge and from the other lines
        for (const turn of TURNS) {
          const a = base + turn * DEG;
          const px = dx + Math.cos(a) * NEXT_REACH;
          const py = dy + Math.sin(a) * NEXT_REACH;
          const spur = [dx, dy, px, py];
          const fits = onBoard([px - DOT.next, py - DOT.next, px + DOT.next, py + DOT.next])
            // its label must fit on a side that doesn't face back along the spur (that would hide the spur)
            && Object.entries(SIDES).some(([side, v]) => v[0] * Math.cos(a) + v[1] * Math.sin(a) >= 0
              && onBoard(labelBox(side, px, py, DOT.next, tw, sz('next')).box))
            && !segments.some((o) => !(o[2] === dx && o[3] === dy) && !(o[0] === dx && o[1] === dy) && cut(o, spur));
          if (fits && skip > 0) {
            skip -= 1;
          } else if (fits) {
            spot = [px, py];
            break;
          }
        }
        if (!spot) {
          spot = [clamp(dx + Math.cos(base) * NEXT_REACH, BOARD.margin + 20, BOARD.w - BOARD.margin - 20),
            clamp(dy + Math.sin(base) * NEXT_REACH, BOARD.margin + 20, BOARD.h - BOARD.margin - 20)];
        }
        const [ex, ey] = spot;
        const nextBox = [ex - DOT.next, ey - DOT.next, ex + DOT.next, ey + DOT.next];
        fixed.push(nextBox);
        segments.push([dx, dy, ex, ey]);
        return { key: nkey, name: e.name, url: e.url, x: ex, y: ey, r: DOT.next, dotBox: nextBox, size: sz('next'),
          from: [dx, dy] };
      });
      return { key, name: d.name, url: d.url, x: dx, y: dy, r: DOT.dest, dotBox, size: sz('dest'), from: [x, y], next };
    });
    return { name: t.name, color: TRAIL_COLORS[i], x, y, w, h, size: sz('hub'), destinations };
  });
  // a pill (a hub or the centre) off the board, or touching another pill, clashes too: only smaller type clears it.
  // Pills count as touching once their rims (3 units wide, half outside the pill) meet.
  const rim = (b) => [b[0] - 2, b[1] - 2, b[2] + 2, b[3] + 2];
  let clashes = pills.filter((b) => !onBoard(b)).length;
  pills.forEach((a, i) => {
    clashes += pills.slice(i + 1).filter((b) => overlap(rim(a), rim(b))).length;
  });
  // labels, one at a time: each takes the free place that best faces away from where its line comes in
  for (const node of trails.flatMap((t) => t.destinations.flatMap((d) => [d, ...d.next]))) {
    const text = shortName(node.name);
    const tw = measure(text, `600 ${node.size}px ${NAME_FONT}`);
    const ox = node.x - node.from[0];
    const oy = node.y - node.from[1];
    const len = Math.hypot(ox, oy) || 1;
    const facing = ([, v]) => (v[0] * ox + v[1] * oy) / len;
    // hiding the node's own line (in from its parent, or out to its own stops) blurs what leads where
    const ownLine = (sg) => (sg[2] === node.x && sg[3] === node.y) || (sg[0] === node.x && sg[1] === node.y);
    let best = null;
    Object.entries(SIDES).sort((a, b) => facing(b) - facing(a)).forEach(([side], rank) => {
      const lb = labelBox(side, node.x, node.y, node.r, tw, node.size);
      const room = [lb.box[0] - GAP, lb.box[1] - GAP, lb.box[2] + GAP, lb.box[3] + GAP];
      const hard = fixed.filter((b) => b !== node.dotBox && overlap(b, room)).length + (onBoard(lb.box) ? 0 : 1);
      const soft = segments.filter((sg) => crosses(sg, lb.box)).reduce((sum, sg) => sum + (ownLine(sg) ? 40 : 4), 0);
      const score = hard * 100 + soft + rank;
      if (!best || score < best.score) best = { ...lb, side, hard, score };
    });
    clashes += best.hard;
    node.label = { text, x: best.tx, y: best.ty, anchor: best.anchor, box: best.box, side: best.side, clash: best.hard > 0 };
    fixed.push(best.box);
  }
  for (const node of trails.flatMap((t) => t.destinations.flatMap((d) => [d, ...d.next]))) delete node.dotBox;
  return { scale, clashes, centre, here, trails, boxes: fixed };
}

// Lay out at full size if it fits. A stop whose label clashes steps out (a destination) or bends (an onward stop)
// first; only then does all the lettering shrink, 5 % at a time, down to MIN_SCALE. `crowded` means even that
// didn't clear every clash.
export function layoutMap(map, measure) {
  let laid = null;
  for (let scale = 1; scale >= MIN_SCALE; scale *= 0.95) {
    const skips = new Map();
    for (let round = 0; round < 6; round += 1) {
      laid = place(map, measure, scale, skips);
      if (!laid.clashes) return { ...laid, crowded: false };
      const stuck = laid.trails.flatMap((t) => t.destinations.flatMap((d) => [d, ...d.next])).filter((s) => s.label.clash);
      if (!stuck.length) break;       // only pills clash: moving stops won't help
      for (const s of stuck) skips.set(s.key, (skips.get(s.key) || 0) + 1);
    }
  }
  return { ...laid, crowded: true };
}

// ---- painting

export function drawMap(p, laid, { focus = null, links = false, paper = true } = {}) {
  if (paper) p.rect(0, 0, BOARD.w, BOARD.h, 0, { fill: PAPER });
  const fade = (i) => (focus === null || focus === i ? 1 : FADE);
  const glow = (i, color) => (focus === i ? color : null);
  laid.trails.forEach((t, i) => {
    p.line(laid.centre.x, laid.centre.y, t.x, t.y, { color: t.color, width: 9, alpha: fade(i), glow: glow(i, t.color) });
    for (const d of t.destinations) {
      p.line(t.x, t.y, d.x, d.y, { color: t.color, width: 5.5, alpha: fade(i), glow: glow(i, t.color) });
      for (const e of d.next) {
        p.line(d.x, d.y, e.x, e.y, { color: t.color, width: 4, dash: [11, 8], alpha: fade(i), glow: glow(i, t.color) });
      }
    }
  });
  laid.trails.forEach((t, i) => {
    for (const node of t.destinations.flatMap((d) => [d, ...d.next])) {
      const paint = () => {
        const b = node.label.box;
        // a backing the colour of the paper (white when multiplied onto a still) hides any line running under the name
        p.rect(b[0] - 4, b[1] - 2, b[2] - b[0] + 8, b[3] - b[1] + 4, 4, { fill: paper ? PAPER : '#FFFFFF' });
        p.circle(node.x, node.y, node.r, { fill: t.color, stroke: RIM, width: 3.5, alpha: fade(i) });
        p.text(node.label.text, node.label.x, node.label.y, { font: NAME_FONT, size: node.size, weight: 600, color: INK,
          anchor: node.label.anchor, alpha: fade(i), underline: links && Boolean(node.url) });
      };
      // a name cut short on the map shows in full as a tooltip
      const draw = node.label.text === node.name ? paint : () => p.titled(node.name, paint);
      if (links && node.url) p.link(node.url, node.name, draw);
      else draw();
    }
  });
  laid.trails.forEach((t, i) => {
    p.rect(t.x - t.w / 2, t.y - t.h / 2, t.w, t.h, t.h / 2, { fill: t.color, stroke: RIM, width: 3, alpha: fade(i),
      glow: glow(i, t.color) });
    p.rect(t.x - t.w / 2 + 16, t.y - t.h / 4, 11, t.h / 2, 2, { fill: '#FFFFFF', alpha: fade(i) * 0.9 });
    p.text(shortName(t.name), t.x + 12, t.y + t.size * 0.35, { font: PILL_FONT, size: t.size, weight: 700,
      color: '#FFFFFF', anchor: 'middle', alpha: fade(i) });
  });
  const c = laid.centre;
  p.rect(c.x - c.w / 2, c.y - c.h / 2, c.w, c.h, c.h / 2, { fill: CENTRE_FILL, stroke: RIM, width: 3.5 });
  p.text(shortName(c.name), c.x, c.y + c.size * 0.34, { font: NAME_FONT, size: c.size, weight: 600, color: '#1B1204',
    anchor: 'middle' });
  const h = laid.here;
  p.circle(h.x, h.y, h.r, { fill: PIN, stroke: RIM, width: 3 });
  p.text('you are here', h.tx, h.ty, { font: NAME_FONT, size: h.size, weight: 500, style: 'italic', color: HERE_INK,
    anchor: 'middle' });
}

const NS = 'http://www.w3.org/2000/svg';
let svgCount = 0;      // keeps each SVG's filter ids unique on a page that shows two maps

export function svgPainter(doc) {
  svgCount += 1;
  const prefix = `kb${svgCount}`;
  const svg = doc.createElementNS(NS, 'svg');
  svg.setAttribute('viewBox', `0 0 ${BOARD.w} ${BOARD.h}`);
  const defs = doc.createElementNS(NS, 'defs');
  svg.append(defs);
  const filters = new Map();
  let parent = svg;
  const el = (tag, attrs) => {
    const e = doc.createElementNS(NS, tag);
    for (const [k, v] of Object.entries(attrs)) if (v !== null && v !== undefined) e.setAttribute(k, v);
    parent.append(e);
    return e;
  };
  const glowUrl = (color) => {
    if (!color) return null;
    if (!filters.has(color)) {
      const id = `${prefix}-glow-${filters.size}`;
      const f = doc.createElementNS(NS, 'filter');
      for (const [k, v] of Object.entries({ id, x: '-20%', y: '-20%', width: '140%', height: '140%' })) f.setAttribute(k, v);
      const s = doc.createElementNS(NS, 'feDropShadow');
      for (const [k, v] of Object.entries({ dx: 0, dy: 0, stdDeviation: 7, 'flood-color': color, 'flood-opacity': 0.6 })) {
        s.setAttribute(k, v);
      }
      f.append(s);
      defs.append(f);
      filters.set(color, id);
    }
    return `url(#${filters.get(color)})`;
  };
  return {
    svg,
    line(x1, y1, x2, y2, o) {
      el('line', { x1, y1, x2, y2, stroke: o.color, 'stroke-width': o.width, 'stroke-linecap': 'round',
        'stroke-dasharray': o.dash ? o.dash.join(' ') : null, opacity: o.alpha ?? 1, filter: glowUrl(o.glow) });
    },
    circle(cx, cy, r, o) {
      el('circle', { cx, cy, r, fill: o.fill, stroke: o.stroke, 'stroke-width': o.width, opacity: o.alpha ?? 1 });
    },
    rect(x, y, w, h, r, o) {
      el('rect', { x, y, width: w, height: h, rx: r, fill: o.fill, stroke: o.stroke, 'stroke-width': o.width,
        opacity: o.alpha ?? 1, filter: glowUrl(o.glow) });
    },
    text(str, x, y, o) {
      const t = el('text', { x, y, 'font-family': o.font, 'font-size': o.size, 'font-weight': o.weight,
        'font-style': o.style || null, fill: o.color, 'text-anchor': o.anchor, opacity: o.alpha ?? 1,
        'text-decoration': o.underline ? 'underline' : null });
      t.textContent = str;
    },
    link(url, title, paint) {
      const a = el('a', { href: url, target: '_blank', rel: 'noopener noreferrer', 'aria-label': title });
      const outer = parent;
      parent = a;
      paint();
      parent = outer;
    },
    titled(title, paint) {
      const g = el('g', {});
      const outer = parent;
      parent = g;
      el('title', {}).textContent = title;
      paint();
      parent = outer;
    },
  };
}

export function canvasPainter(ctx, scale = 1) {
  const styled = (o, fn) => {
    ctx.save();
    ctx.setTransform(scale, 0, 0, scale, 0, 0);
    ctx.globalAlpha = o.alpha ?? 1;
    if (o.glow) {
      ctx.shadowColor = o.glow;
      ctx.shadowBlur = 14 * scale;     // shadows ignore the transform
    }
    fn();
    ctx.restore();
  };
  const outline = (o) => {
    if (!o.stroke) return;
    ctx.shadowBlur = 0;
    ctx.strokeStyle = o.stroke;
    ctx.lineWidth = o.width;
    ctx.stroke();
  };
  return {
    line(x1, y1, x2, y2, o) {
      styled(o, () => {
        ctx.strokeStyle = o.color;
        ctx.lineWidth = o.width;
        ctx.lineCap = 'round';
        ctx.setLineDash(o.dash || []);
        ctx.beginPath();
        ctx.moveTo(x1, y1);
        ctx.lineTo(x2, y2);
        ctx.stroke();
      });
    },
    circle(cx, cy, r, o) {
      styled(o, () => {
        ctx.beginPath();
        ctx.arc(cx, cy, r, 0, Math.PI * 2);
        ctx.fillStyle = o.fill;
        ctx.fill();
        outline(o);
      });
    },
    rect(x, y, w, h, r, o) {
      styled(o, () => {
        ctx.beginPath();
        ctx.roundRect(x, y, w, h, r);
        ctx.fillStyle = o.fill;
        ctx.fill();
        outline(o);
      });
    },
    text(str, x, y, o) {
      styled(o, () => {
        ctx.font = `${o.style || 'normal'} ${o.weight} ${o.size}px ${o.font}`;
        ctx.fillStyle = o.color;
        ctx.textAlign = { middle: 'center', end: 'right', start: 'left' }[o.anchor] || 'left';
        ctx.textBaseline = 'alphabetic';
        ctx.fillText(str, x, y);
      });
    },
    link(url, title, paint) {
      paint();
    },
    titled(title, paint) {
      paint();
    },
  };
}

export function canvasMeasure(doc) {
  const ctx = doc.createElement('canvas').getContext('2d');
  return (text, font) => {
    ctx.font = font;
    return ctx.measureText(text).width;
  };
}

// The map's fonts, before anything is measured. Never fails: without them the map measures and draws with whichever
// font did render, and still fits.
export async function loadMapFonts(doc) {
  if (!doc.fonts || typeof doc.fonts.load !== 'function') return;
  try {
    await Promise.all(['600 27px Fraunces', 'italic 500 24px Fraunces', '700 26px Figtree'].map((f) => doc.fonts.load(f)));
  } catch {
    // measured with the fallback fonts instead
  }
}

// The CSS transform that lays a w x h box (origin at its top-left) onto four points, clockwise from its top-left
// corner: the 8 unknowns of the projective map, by Gauss-Jordan elimination.
export function quadMatrix3d(w, h, quad) {
  const src = [[0, 0], [w, 0], [w, h], [0, h]];
  const rows = [];
  for (let i = 0; i < 4; i += 1) {
    const [x, y] = src[i];
    const [u, v] = quad[i];
    rows.push([x, y, 1, 0, 0, 0, -u * x, -u * y, u]);
    rows.push([0, 0, 0, x, y, 1, -v * x, -v * y, v]);
  }
  for (let c = 0; c < 8; c += 1) {
    let p = c;
    for (let r = c + 1; r < 8; r += 1) if (Math.abs(rows[r][c]) > Math.abs(rows[p][c])) p = r;
    [rows[c], rows[p]] = [rows[p], rows[c]];
    for (let r = 0; r < 8; r += 1) {
      if (r === c) continue;
      const f = rows[r][c] / rows[c][c];
      for (let k = c; k < 9; k += 1) rows[r][k] -= f * rows[c][k];
    }
  }
  const [a, b, c, d, e, f, g, k] = rows.map((r, i) => r[8] / r[i]);
  // exponential notation: plain decimal literals lose precision once parsed back out of a CSS string (observed in
  // Chromium, where e.g. "0.0000117434" round-trips through DOMMatrix as 0.0000117 - fine for a live transform, not
  // for the sub-pixel check in tests/test_kbmap.py)
  return `matrix3d(${[a, d, 0, g, b, e, 0, k, 0, 0, 1, 0, c, f, 0, 1].map((n) => n.toExponential(12)).join(',')})`;
}
