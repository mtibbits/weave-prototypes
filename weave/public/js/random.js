// Seeded randomness for WEAVE's painters. Painters draw only from rngFor, never from an ambient source,
// so every canvas is a pure function of its inputs and #20 can hash it. Hashes are comparable only within
// one machine and one Playwright/Chromium build.
//
// Seed labels, as rngFor(id, purpose):
//   paintFabric(c, fabric, seedId) -> (seedId, 'fabric'); a filler block is ('filler', 'fabric').
//   Face extras (stitch jitter, chalk wobble) -> (entry.id, 'face'). Tile bars -> (entry.id, 'bars').
//   Textures -> ('sashing', 'speckle'), ('wood', 'grain'), ('weave-normal', 'weave'), ('shadow', 'soft').
//   A planned block's askew tilt (#7) -> (entry.id, 'tilt'). #10 adds its own purposes.
// A panel whose id is 'filler' shares the filler's stream, which is harmless.

// Copied unchanged from coalesce/public/js/motion.js. The WEAVE copy is frozen for hash stability
// (#7, #10 and #20 depend on it): if the two ever differ, decide deliberately, never re-sync blindly.
export function mulberry32(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// FNV-1a 32-bit over the UTF-16 code units of a JSON key, so ('a|b', 'c') and ('a', 'b|c') never collide.
export function seedFor(id, purpose) {
  const key = JSON.stringify([String(id), String(purpose)]);
  let h = 0x811c9dc5;
  for (let i = 0; i < key.length; i += 1) {
    h ^= key.charCodeAt(i);
    h = Math.imul(h, 0x01000193) >>> 0;
  }
  return h;
}

// A fresh stream on every call.
export function rngFor(id, purpose) {
  return mulberry32(seedFor(id, purpose));
}
