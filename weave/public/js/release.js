// WEAVE's release rules (#12): which panels are new for this visitor today, which wear a "New" tag, and the card's
// heading. Pure: no imports, no DOM, no clock, never throws. The boot hands in `today` as YYYY-MM-DD and reaches
// storage only through a getter, so the tests can call every rule with any day and any storage.

const VERSION_RE = /^\d+(\.\d+)*$/;
const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;
const DAY_MS = 86400000;
export const LAST_SEEN_KEY = 'weave.lastSeenRelease';
export const SIM_KEY = 'weave.lastSeenRelease.sim';

const W_VERSION = "WEAVE: news: release.version in panels.js must be a version string such as '1.1', "
  + 'so no panel is new.';
const W_DATE = 'WEAVE: news: release.date in panels.js must be a real day written YYYY-MM-DD, so no panel is new.';
const W_WINDOW = 'WEAVE: news: newsWindowDays in panels.js must be a whole number from 1 to 60, so no panel is new.';
const W_NOW = 'WEAVE: news: ?now= must be a real day written YYYY-MM-DD, so it is ignored and today is the local date.';
const sinceWarning = (id) => `WEAVE: news: the live panel '${id}' has a malformed since (write a string such as `
  + "'1.1'), so it is never new.";

const isObject = (v) => v !== null && typeof v === 'object' && !Array.isArray(v);
const pad = (n, width) => String(n).padStart(width, '0');

export const isVersion = (v) => typeof v === 'string' && VERSION_RE.test(v);

// A well-formed day: YYYY-MM-DD naming a real date (Date.UTC maps years below 100 to 19xx, which fails the check).
export function isDate(s) {
  if (typeof s !== 'string' || !DATE_RE.test(s)) return false;
  const [y, m, d] = s.split('-').map(Number);
  const t = new Date(Date.UTC(y, m - 1, d));
  return t.getUTCFullYear() === y && t.getUTCMonth() === m - 1 && t.getUTCDate() === d;
}

// Whole UTC day numbers, so daylight saving never enters the arithmetic. A date string is never parsed by Date
// itself: that reads it as UTC midnight, the evening before in EDT. NaN for a non-string.
export function dayNumber(s) {
  if (typeof s !== 'string') return NaN;
  const [y, m, d] = s.split('-').map(Number);
  return Date.UTC(y, m - 1, d) / DAY_MS;
}

// The local calendar date of `date` as YYYY-MM-DD ('' for anything but a valid Date), from its local fields: the
// ISO string is the UTC date, already tomorrow on a US evening.
export function localDate(date) {
  if (!(date instanceof Date) || Number.isNaN(date.getTime())) return '';
  return `${pad(date.getFullYear(), 4)}-${pad(date.getMonth() + 1, 2)}-${pad(date.getDate(), 2)}`;
}

// One dot segment against another, exactly (no Number, so a 25-digit segment still compares): leading zeros
// stripped, then the longer is larger, then the lexicographic order of equal-length digit strings.
function compareSegments(a, b) {
  const x = a.replace(/^0+(?=\d)/, '');
  const y = b.replace(/^0+(?=\d)/, '');
  if (x.length !== y.length) return x.length < y.length ? -1 : 1;
  if (x === y) return 0;
  return x < y ? -1 : 1;
}

// -1, 0 or 1. A missing segment counts as '0', so '1.1.0' equals '1.1'; a non-version reads as '0'.
export function compareVersions(a, b) {
  const x = (isVersion(a) ? a : '0').split('.');
  const y = (isVersion(b) ? b : '0').split('.');
  for (let i = 0; i < Math.max(x.length, y.length); i += 1) {
    const c = compareSegments(x[i] ?? '0', y[i] ?? '0');
    if (c !== 0) return c;
  }
  return 0;
}

const goodWindow = (n) => Number.isInteger(n) && n >= 1 && n <= 60;
const wellFormed = (release, windowDays) => isObject(release) && isVersion(release.version)
  && isDate(release.date) && goodWindow(windowDays);
// The live entries of E1's validated list, in order; a missing or malformed since counts as '0'.
const candidates = (panels) => (Array.isArray(panels) ? panels.filter((p) => isObject(p) && p.status === 'live') : []);
const since = (panel) => (isVersion(panel.since) ? panel.since : '0');
// The window has opened: today is a real day on or after the release date.
const opened = (today, release) => isDate(today) && dayNumber(release.date) <= dayNumber(today);
const inWindow = (today, release, windowDays) => opened(today, release)
  && dayNumber(today) < dayNumber(release.date) + windowDays;
// The first release: no candidate arrived before the current version.
const isFirstRelease = (live, version) => !live.some((p) => compareVersions(since(p), version) < 0);
const ids = (panels) => panels.map((p) => p.id);
const atVersion = (live, version) => live.filter((p) => compareVersions(since(p), version) === 0);

// The panels new for this visit, in list order (issue #12's rules 1 to 5, in order).
export function newPanelIds(input) {
  const { panels, release, lastSeen, today, windowDays, force } = input ?? {};
  if (!wellFormed(release, windowDays)) return [];
  const live = candidates(panels);
  const current = release.version;
  if (force === true) return ids(atVersion(live, current));
  if (!inWindow(today, release, windowDays)) return [];
  if (!isVersion(lastSeen)) return isFirstRelease(live, current) ? [] : ids(atVersion(live, current));
  return ids(live.filter((p) => compareVersions(lastSeen, since(p)) < 0 && compareVersions(since(p), current) <= 0));
}

// The panels wearing a "New" tag: inside the window, except on the first release, those at the current version.
export function taggedPanelIds(input) {
  const { panels, release, today, windowDays } = input ?? {};
  if (!wellFormed(release, windowDays) || !inWindow(today, release, windowDays)) return [];
  const live = candidates(panels);
  return isFirstRelease(live, release.version) ? [] : ids(atVersion(live, release.version));
}

// The card's heading for `newIds`, or null for no card. Groups hold versions equal by compareVersions, spelled as
// first met in list order, oldest first, with names in list order.
export function cardHeading(input) {
  const { panels, newIds, release } = input ?? {};
  if (!Array.isArray(newIds) || newIds.length === 0 || !isObject(release) || !isVersion(release.version)) return null;
  const wanted = new Set(newIds);
  const fresh = candidates(panels).filter((p) => wanted.has(p.id));
  if (fresh.length === 0) return null;
  const groups = [];
  for (const panel of fresh) {
    const group = groups.find((g) => compareVersions(g.version, since(panel)) === 0);
    if (group) group.names.push(panel.name);
    else groups.push({ version: since(panel), names: [panel.name] });
  }
  groups.sort((a, b) => compareVersions(a.version, b.version));
  if (fresh.every((p) => compareVersions(since(p), release.version) === 0)) {
    const { label } = release;
    const suffix = typeof label === 'string' && label !== '' ? ` (${label})` : '';
    return { kind: 'release', text: `New this release · v${release.version}${suffix}`, groups };
  }
  return { kind: 'since-last-visit', text: 'New since your last visit', groups };
}

// The warnings for fields that are present and malformed, in order; absent fields stay silent.
export function releaseWarnings(input) {
  const { panels, release, windowDays } = input ?? {};
  const warnings = [];
  if (isObject(release)) {
    if (release.version !== undefined && !isVersion(release.version)) warnings.push(W_VERSION);
    if (release.date !== undefined && !isDate(release.date)) warnings.push(W_DATE);
  } else if (release !== undefined) {
    // A present release that is no object (null, '1.1', an array) has neither field.
    warnings.push(W_VERSION, W_DATE);
  }
  if (windowDays !== undefined && !goodWindow(windowDays)) warnings.push(W_WINDOW);
  for (const panel of candidates(panels)) {
    if (panel.since !== undefined && !isVersion(panel.since)) warnings.push(sinceWarning(panel.id));
  }
  return warnings;
}

// The stored lastSeen under `key`, or null when it is absent, not a version, or storage throws. getStorage is called
// inside the try: reading window.localStorage itself throws where site data is blocked.
export function readLastSeen(getStorage, key) {
  try {
    const value = getStorage().getItem(key);
    return isVersion(value) ? value : null;
  } catch {
    return null;
  }
}

// Stores `version` under `key`; true only when it is a version and the write succeeded.
export function writeLastSeen(getStorage, key, version) {
  try {
    if (!isVersion(version)) return false;
    getStorage().setItem(key, version);
    return true;
  } catch {
    return false;
  }
}

// The boot's release object (stage.__weaveRelease), from every input the boot reads: the ?now=, ?whatsnew and
// ?pose=rest hooks, the raw WEAVE_PANELS (null when cleanPanels reported an error), E1's cleaned panels, the Date
// at boot, the storage getter and a warning sink. The sets are computed once; recordSeen() is the only writer.
export function createRelease(input) {
  const { now = null, whatsnew = false, rest = false, raw = null, panels, date, getStorage, warn } = input ?? {};
  const say = typeof warn === 'function' ? warn : () => {};
  const asked = now !== null;
  if (asked && !isDate(now)) say(W_NOW);
  const today = isDate(now) ? now : localDate(date);
  const force = whatsnew === true;
  // A simulated visit (any ?now=, even an ignored one; ?whatsnew; ?pose=rest) never touches the real key.
  const key = asked || force || rest === true ? SIM_KEY : LAST_SEEN_KEY;
  const source = isObject(raw) ? raw : {};
  const { release, newsWindowDays: windowDays } = source;
  releaseWarnings({ panels, release, windowDays }).forEach(say);
  const lastSeen = readLastSeen(getStorage, key);
  const newIds = newPanelIds({ panels, release, lastSeen, today, windowDays, force });
  const taggedIds = taggedPanelIds({ panels, release, today, windowDays });
  // Never before the window opens, so a panels.js pushed the evening before doesn't spend early visitors' sequence.
  const recordSeen = () => (wellFormed(release, windowDays) && opened(today, release)
    ? writeLastSeen(getStorage, key, release.version) : false);
  return { today, force, key, lastSeen, newIds, taggedIds, recordSeen };
}
