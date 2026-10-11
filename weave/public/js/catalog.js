// Pure cleaner for WEAVE's panel list (window.WEAVE_PANELS from panels.js).
// No DOM, no window, never throws, never mutates its input: the page and the tests share it.

const STATUSES = ['live', 'planned', 'suggest'];
const QUILT_BLOCKS = 12;

const E1 = 'WEAVE: the panel list (window.WEAVE_PANELS from panels.js) is missing or is not an object. '
  + 'Check panels.js for a syntax error.';
const E2 = 'WEAVE: WEAVE_PANELS.panels in panels.js is not an array.';

const isObject = (v) => v !== null && typeof v === 'object' && !Array.isArray(v);
const isFilled = (v) => typeof v === 'string' && v.trim() !== '';

function entryProblem(entry) {
  if (!isObject(entry)) return 'it is not an object';
  if (!isFilled(entry.id)) return 'its id must be a non-empty string';
  if (!isFilled(entry.name)) return 'its name must be a non-empty string';
  if (!STATUSES.includes(entry.status)) return "its status must be 'live', 'planned' or 'suggest'";
  return null;
}

// A sample is { value, unit } with a finite number or non-blank string value and a string unit; else null.
function cleanSample(sample) {
  if (!isObject(sample)) return null;
  const { value, unit } = sample;
  const goodValue = (typeof value === 'number' && Number.isFinite(value)) || isFilled(value);
  return goodValue && typeof unit === 'string' ? { value, unit } : null;
}

export function cleanPanels(raw) {
  if (!isObject(raw)) return { panels: [], warnings: [], error: E1 };
  if (!Array.isArray(raw.panels)) return { panels: [], warnings: [], error: E2 };

  const panels = [];
  const warnings = [];
  const seen = new Set();
  // An index loop, not forEach, so a hole in the array reads as a non-object entry.
  for (let i = 0; i < raw.panels.length; i += 1) {
    const n = i + 1;
    const entry = raw.panels[i];
    const problem = entryProblem(entry);
    if (problem) {
      warnings.push(`WEAVE: panels.js entry ${n} was skipped: ${problem}.`);
      continue;
    }
    const id = entry.id.trim();
    if (seen.has(id)) {
      warnings.push(`WEAVE: panels.js entry ${n} was skipped: the id '${id}' is already used (the first one is kept).`);
      continue;
    }
    seen.add(id);
    const sample = cleanSample(entry.sample);
    if (entry.status === 'live' && sample === null && entry.sample !== null) {
      warnings.push(`WEAVE: the live panel '${id}' has no valid sample, so it reads "No sample yet".`);
    }
    panels.push({ ...entry, id, name: entry.name.trim(), sample });
  }
  if (panels.length > QUILT_BLOCKS) {
    warnings.push(`WEAVE: panels.js has ${panels.length} valid panels; the quilt draws the first ${QUILT_BLOCKS}.`);
  }
  return { panels, warnings };
}
