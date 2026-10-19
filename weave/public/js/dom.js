// The page's DOM writers. Panel strings reach the DOM only through textContent and setAttribute.
import { cleanPanels } from './catalog.js';

export const LOAD_MESSAGE = "The panel list couldn't be loaded.";
export const NONE_YET = 'None yet.';
export const NO_SAMPLE = 'No sample yet';
// #14's tag on a panel new in the release: the list badge and the tile label.
export const NEW_TAG = 'New';

// A cleaned sample ({ value, unit } or null) as its list figure.
export function figureText(sample) {
  if (!sample) return NO_SAMPLE;
  return sample.unit === '' ? `${sample.value} (sample)` : `${sample.value} ${sample.unit} (sample)`;
}

const namesOf = (panels, status) => panels.filter((p) => p.status === status).map((p) => p.name).join(', ') || 'none yet';

// The stage's aria-label, always over 40 characters, even for an empty list.
export function stageLabel(panels) {
  return `WEAVE's dashboard panels as a quilt. Sewn in: ${namesOf(panels, 'live')}. `
    + `Pinned for later: ${namesOf(panels, 'planned')}.`;
}

function element(tag, className, text) {
  const el = document.createElement(tag);
  el.className = className;
  if (text !== undefined) el.textContent = text;
  return el;
}

// A tagged panel (#14) wears the "New" badge as its name's next sibling, never inside it, so the name reads alone.
function panelItem(panel, tagged) {
  const li = element('li', tagged ? 'panel is-new' : 'panel');
  li.append(element('span', 'panel-name', panel.name));
  if (tagged) li.append(element('span', 'panel-new', NEW_TAG));
  if (panel.status === 'live') li.append(element('span', 'panel-figure', figureText(panel.sample)));
  if (typeof panel.blurb === 'string') li.append(element('p', 'panel-blurb', panel.blurb));
  return li;
}

// Fill #panels from a cleanPanels result: the load message on error, else both groups and the suggest line. `tagged`
// (#14) is the ids of the live panels that wear the "New" badge; anything but an array tags nothing.
export function renderPanels(section, result, tagged = []) {
  const wanted = new Set(Array.isArray(tagged) ? tagged : []);
  const status = section.querySelector('[data-panels-status]');
  const suggest = section.querySelector('[data-suggest]');
  if (result.error) {
    status.textContent = LOAD_MESSAGE;
    status.hidden = false;
    section.querySelectorAll('[data-group]').forEach((group) => { group.hidden = true; });
    suggest.hidden = true;
    return;
  }
  for (const group of ['live', 'planned']) {
    const entries = result.panels.filter((p) => p.status === group);
    const items = entries.length ? entries.map((p) => panelItem(p, group === 'live' && wanted.has(p.id)))
      : [element('li', 'panel-none', NONE_YET)];
    section.querySelector(`[data-list="${group}"]`).replaceChildren(...items);
  }
  // The first suggest entry fills the line; later ones are ignored.
  const idea = result.panels.find((p) => p.status === 'suggest');
  if (idea) {
    suggest.textContent = typeof idea.blurb === 'string' ? idea.blurb : idea.name;
    suggest.hidden = false;
  }
}

export function setStageLabel(stage, panels) {
  stage.setAttribute('aria-label', stageLabel(panels));
}

export const STILL_HINT = 'Your browser shows a picture of the quilt. The panels below have everything.';

// --- The toggle and the live hint (#8): the label names what a press would do now, and the hint keeps in step. ---

export const UNSTITCH_LABEL = 'Unstitch';
export const SEW_LABEL = 'Sew it back';
export const toggleLabel = (mode) => (mode === 'unstitching' || mode === 'tiles' ? SEW_LABEL : UNSTITCH_LABEL);
export const QUILT_HINT = 'Click the quilt, or press Unstitch, to lay its blocks out as a dashboard; in the dashboard, drag a tile to move it.';
export const TILES_HINT = 'Click the background, or press Sew it back, to sew the quilt together again.';
export const liveHint = (mode) => (toggleLabel(mode) === SEW_LABEL ? TILES_HINT : QUILT_HINT);

// The one writer of the stage's state attributes and of the hint: #7's live/ok and runtime reasons, and the still
// hint. The live path starts in `intro` (in `quilt` at `?pose=rest`), and `data-mode` reads `quilt` from the first
// entry, so live writes QUILT_HINT; setToggle keeps it in step after that.
export function setHeroState(stage, hint, state, reason) {
  stage.dataset.heroState = state;
  stage.dataset.heroReason = reason;
  if (state === 'live') hint.textContent = QUILT_HINT;
  else hint.textContent = reason !== 'loading' ? STILL_HINT : '';
}

// The one writer of the toggle's label and the live hint, together, on every mode the director enters. The hint is
// aria-live, so it is rewritten only when its text changes: a settle that keeps the text is not announced again.
export function setToggle(button, hint, mode) {
  button.textContent = toggleLabel(mode);
  const text = liveHint(mode);
  if (hint.textContent !== text) hint.textContent = text;
}

// The one writer of data-mode: the settled mode on the live path; null removes it (the still path has none).
export function setDataMode(stage, mode) {
  if (mode === null) delete stage.dataset.mode;
  else stage.dataset.mode = mode;
}

// --- The hover tooltip (#10): live only, built at go-live and removed at teardown. aria-hidden, since the stage label
// and the panel lists already name every block; written with textContent only. ---

// The status line, by the block's drawn face.
export const HOVER_STATUS = Object.freeze({ sewn: 'Sewn in', planned: 'Pinned for later', suggest: 'Have an idea for a panel?' });
const TIP_GAP = 12;

export function createTooltip(stage) {
  const tip = element('div', 'hero-tip');
  tip.dataset.tooltip = '';
  tip.setAttribute('aria-hidden', 'true');
  tip.hidden = true;
  tip.append(element('span', 'hero-tip-name'), element('span', 'hero-tip-status'));
  stage.append(tip);
  return tip;
}

// Shows the tooltip for block { name, face } beside the pointer at (x, y) in stage px: TIP_GAP right of and below it,
// flipped to its left or above it on any axis where it would overflow the stage (which clips: overflow hidden).
export function showTooltip(tip, { name, face }, x, y) {
  const [nameEl, statusEl] = tip.children;
  nameEl.textContent = name;
  statusEl.textContent = HOVER_STATUS[face] ?? '';
  tip.hidden = false;
  // Measured at the stage's origin: left where it was, an absolute box shrink-wraps to the room left there.
  tip.style.left = '0px';
  tip.style.top = '0px';
  const stage = tip.parentElement;
  const place = (at, size, room) => {
    const after = at + TIP_GAP;
    return after + size <= room ? after : Math.max(0, at - TIP_GAP - size);
  };
  tip.style.left = `${place(x, tip.offsetWidth, stage.clientWidth)}px`;
  tip.style.top = `${place(y, tip.offsetHeight, stage.clientHeight)}px`;
}

export function hideTooltip(tip) {
  tip.hidden = true;
}

// --- The live hero's controls and URL hooks (#7). ---

export const PAUSE_LABEL = 'Pause motion';
export const PLAY_LABEL = 'Play motion';

// The one writer of Pause's pressed state and label.
export function setPaused(button, paused) {
  button.setAttribute('aria-pressed', String(paused));
  button.textContent = paused ? PLAY_LABEL : PAUSE_LABEL;
}

// Shows or hides the controls row and its buttons (Pause and the toggle) together.
export function showLiveControls(controls, buttons, live) {
  controls.hidden = !live;
  for (const button of buttons) button.hidden = !live;
}

// The page's URL hooks, read once at start: ?nowatchdog, ?watchdogLimitMs=<ms> (Coalesce's form: an absent key
// keeps 45, never Number(null) === 0), ?pose=rest, ?frame=still, and #12's test-only ?now=YYYY-MM-DD (the raw value,
// or null when absent; release.js checks it) and ?whatsnew (present means on, whatever its value).
export function readHooks(search) {
  const params = new URLSearchParams(search);
  return {
    watchdog: !params.has('nowatchdog'),
    limitMs: params.has('watchdogLimitMs') ? Number(params.get('watchdogLimitMs')) : 45,
    rest: params.get('pose') === 'rest',
    still: params.get('frame') === 'still',
    now: params.has('now') ? params.get('now') : null,
    whatsnew: params.has('whatsnew'),
  };
}

export const QUILT_SLOTS = 12;

// The quilt's 12 slots: the first 12 entries that pass #5's validation, in file order, padded with null (a
// filler); anything that is not an array of panels gives 12 fillers.
export function fillSlots(panels) {
  const valid = Array.isArray(panels) ? cleanPanels({ panels }).panels.slice(0, QUILT_SLOTS) : [];
  return [...valid, ...new Array(QUILT_SLOTS - valid.length).fill(null)];
}
