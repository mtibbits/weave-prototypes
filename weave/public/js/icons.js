// Drawn for this repo (WEAVE). No third-party icon paths: every shape below was drawn here, in a 100 x 100 box.
// Each icon is felt (filled shapes, each in one of three tones: base, accent, light) plus stitch paths
// (strokes the painters sew as running or blanket stitch). Coordinates are absolute, inside 0-100.

const circle = (cx, cy, r) => `M${cx - r} ${cy} A${r} ${r} 0 1 0 ${cx + r} ${cy} A${r} ${r} 0 1 0 ${cx - r} ${cy} Z`;

const felt = (tone, d) => ({ d, tone });

function deepFreeze(value) {
  if (value && typeof value === 'object') {
    Object.values(value).forEach(deepFreeze);
    Object.freeze(value);
  }
  return value;
}

export const ICONS = deepFreeze({
  people: {
    felt: [
      felt('accent', 'M8 86 C8 70 15 64 24 64 C33 64 40 70 40 86 Z'), felt('accent', circle(24, 50, 9)),
      felt('light', 'M60 86 C60 70 67 64 76 64 C85 64 92 70 92 86 Z'), felt('light', circle(76, 50, 9)),
      felt('base', 'M30 88 C30 66 40 58 50 58 C60 58 70 66 70 88 Z'), felt('base', circle(50, 40, 12)),
    ],
    stitch: ['M34 86 C34 68 42 62 50 62 C58 62 66 68 66 86'],
  },
  'person-plus': {
    felt: [
      felt('base', 'M14 88 C14 64 26 56 40 56 C54 56 66 64 66 88 Z'), felt('base', circle(40, 34, 12)),
      felt('light', 'M32 58 L40 70 L48 58 Z'),
      felt('accent', 'M74 26 H82 V38 H94 V46 H82 V58 H74 V46 H62 V38 H74 Z'),
    ],
    stitch: ['M18 86 C18 66 28 60 40 60 C52 60 62 66 62 86', 'M78 30 V54', 'M66 42 H90'],
  },
  mortarboard: {
    felt: [
      felt('light', 'M26 46 L26 66 C26 76 74 76 74 66 L74 46 L50 56 Z'),
      felt('base', 'M50 18 L94 36 L50 54 L6 36 Z'),
      felt('accent', 'M82 40 H86 V68 L92 82 H76 L82 68 Z'),
    ],
    stitch: ['M50 24 L84 36 L50 48 L16 36 Z', 'M30 66 C34 72 66 72 70 66'],
  },
  ribbon: {
    felt: [
      felt('accent', 'M36 56 L24 92 L36 86 L44 94 L50 64 Z'), felt('accent', 'M64 56 L76 92 L64 86 L56 94 L50 64 Z'),
      felt('base', circle(50, 40, 26)),
      felt('light', circle(50, 40, 14)),
    ],
    stitch: [circle(50, 40, 20)],
  },
  chevrons: {
    felt: [
      felt('light', 'M50 6 L58 14 L50 22 L42 14 Z'),
      felt('base', 'M14 50 L50 24 L86 50 L86 64 L50 38 L14 64 Z'),
      felt('accent', 'M14 70 L50 44 L86 70 L86 84 L50 58 L14 84 Z'),
    ],
    stitch: ['M20 54 L50 32 L80 54', 'M20 74 L50 52 L80 74'],
  },
  airplane: {
    felt: [
      felt('accent', 'M10 54 L46 36 L54 36 L90 54 L90 62 L54 54 L46 54 L10 62 Z'),
      felt('light', 'M34 88 L46 78 L54 78 L66 88 L66 92 L34 92 Z'),
      felt('base', 'M46 10 C46 4 54 4 54 10 L54 86 C54 90 46 90 46 86 Z'),
    ],
    stitch: ['M50 14 V82', 'M16 57 L46 44', 'M84 57 L54 44'],
  },
  speech: {
    felt: [
      felt('accent', 'M60 74 H94 V92 H74 L66 98 L68 92 H60 Z'),
      felt('base', 'M10 20 C10 12 16 8 24 8 L76 8 C84 8 90 12 90 20 L90 56 C90 64 84 68 76 68 L40 68 L20 88 '
        + 'L24 68 C16 68 10 64 10 56 Z'),
      felt('light', circle(32, 38, 5)), felt('light', circle(50, 38, 5)), felt('light', circle(68, 38, 5)),
    ],
    stitch: ['M18 20 C18 16 20 14 24 14 L76 14 C80 14 84 16 84 20 L84 56 C84 60 80 62 76 62 L38 62'],
  },
  checklist: {
    felt: [
      felt('light', 'M18 14 H82 V94 H18 Z'),
      felt('base', 'M36 6 H64 V20 H36 Z'),
      felt('accent', 'M26 36 L32 42 L42 30 L46 34 L32 50 L22 40 Z'),
      felt('accent', 'M26 62 L32 68 L42 56 L46 60 L32 76 L22 66 Z'),
    ],
    stitch: ['M52 40 H74', 'M52 66 H74', 'M22 24 V90 H78 V24'],
  },
  magnifier: {
    felt: [
      felt('accent', 'M58 64 L66 56 L92 82 C94 84 94 88 92 90 L90 92 C88 94 84 94 82 92 Z'),
      felt('base', circle(40, 40, 28)),
      felt('light', circle(40, 40, 20)),
    ],
    stitch: ['M26 40 A14 14 0 0 1 40 26', 'M64 64 L86 86'],
  },
  key: {
    felt: [
      felt('accent', 'M48 36 H92 V44 H86 V56 H78 V44 H72 V52 H64 V44 H48 Z'),
      felt('base', circle(30, 40, 20)),
      felt('light', circle(30, 40, 7)),
    ],
    stitch: ['M52 40 H88', 'M14 40 A16 16 0 0 1 46 40'],
  },
  desk: {
    felt: [
      felt('accent', 'M12 50 H20 V90 H12 Z'), felt('accent', 'M60 50 H88 V90 H60 Z'),
      felt('base', 'M6 40 H94 V50 H6 Z'),
      felt('light', 'M64 56 H84 V68 H64 Z'), felt('light', 'M64 72 H84 V84 H64 Z'),
    ],
    stitch: ['M10 45 H90', 'M70 62 H78', 'M70 78 H78'],
  },
  fallback: {
    felt: [
      felt('base', 'M18 18 H82 V82 H18 Z'),
      felt('accent', 'M50 26 L74 50 L50 74 L26 50 Z'),
      felt('light', 'M42 42 H58 V58 H42 Z'),
    ],
    stitch: ['M24 24 H76 V76 H24 Z'],
  },
});

// The one door: unknown, absent, non-string and prototype keys all get the fallback.
export function iconFor(name) {
  return typeof name === 'string' && Object.hasOwn(ICONS, name) ? ICONS[name] : ICONS.fallback;
}
