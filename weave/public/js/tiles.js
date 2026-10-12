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
