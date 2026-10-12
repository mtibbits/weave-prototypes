// WEAVE's cloth painters: the fabric prints, the sashing and the scene textures, drawn onto a canvas they
// are handed. No DOM writes beyond that canvas, no ambient inputs (randomness comes only from rngFor).
// Any canvas passed to a painter and later read back or hashed (by #7, #18 or #20) must come from
// makeCanvas. Hashes are comparable only within one machine and one Playwright/Chromium build.

// The one canvas door. Chromium rasters a default 2D canvas on the GPU and silently demotes it to software
// after several readbacks, which changes its bytes; asking for willReadFrequently up front keeps every canvas
// in software from the first stroke, so a canvas that is read back or hashed always gives the same bytes.
export function makeCanvas(width, height = width) {
  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  canvas.getContext('2d', { willReadFrequently: true });
  return canvas;
}
