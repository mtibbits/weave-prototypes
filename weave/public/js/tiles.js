// WEAVE's block faces and dashboard tiles, the name rule they share, and the wait for the web fonts.
// Painters draw onto the canvas they are handed and nothing else; see fabric.js for the canvas rules.

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
