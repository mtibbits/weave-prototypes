// The page's DOM writers. Panel strings reach the DOM only through textContent and setAttribute.
import { cleanPanels } from './catalog.js';

export const LOAD_MESSAGE = "The panel list couldn't be loaded.";
export const NONE_YET = 'None yet.';
export const NO_SAMPLE = 'No sample yet';

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

function panelItem(panel) {
  const li = element('li', 'panel');
  li.append(element('span', 'panel-name', panel.name));
  if (panel.status === 'live') li.append(element('span', 'panel-figure', figureText(panel.sample)));
  if (typeof panel.blurb === 'string') li.append(element('p', 'panel-blurb', panel.blurb));
  return li;
}

// Fill #panels from a cleanPanels result: the load message on error, else both groups and the suggest line.
export function renderPanels(section, result) {
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
    const items = entries.length ? entries.map(panelItem) : [element('li', 'panel-none', NONE_YET)];
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

// The one writer of the stage's state attributes and of the hint: #7 reuses it for live/ok and the runtime
// reasons, and #8 extends it (for example with an optional hint argument) to write the live hint, rather than
// writing the hint around it.
export function setHeroState(stage, hint, state, reason) {
  stage.dataset.heroState = state;
  stage.dataset.heroReason = reason;
  hint.textContent = state === 'still' && reason !== 'loading' ? STILL_HINT : '';
}

// --- The live hero's controls and URL hooks (#7). ---

export const PAUSE_LABEL = 'Pause motion';
export const PLAY_LABEL = 'Play motion';

// The one writer of Pause's pressed state and label.
export function setPaused(button, paused) {
  button.setAttribute('aria-pressed', String(paused));
  button.textContent = paused ? PLAY_LABEL : PAUSE_LABEL;
}

// Shows or hides the controls row and Pause together.
export function showLiveControls(controls, pause, live) {
  controls.hidden = !live;
  pause.hidden = !live;
}

// The page's URL hooks, read once at start: ?nowatchdog, ?watchdogLimitMs=<ms> (Coalesce's form: an absent key
// keeps 45, never Number(null) === 0), ?pose=rest and ?frame=still.
export function readHooks(search) {
  const params = new URLSearchParams(search);
  return {
    watchdog: !params.has('nowatchdog'),
    limitMs: params.has('watchdogLimitMs') ? Number(params.get('watchdogLimitMs')) : 45,
    rest: params.get('pose') === 'rest',
    still: params.get('frame') === 'still',
  };
}

export const QUILT_SLOTS = 12;

// The quilt's 12 slots: the first 12 entries that pass #5's validation, in file order, padded with null (a
// filler); anything that is not an array of panels gives 12 fillers.
export function fillSlots(panels) {
  const valid = Array.isArray(panels) ? cleanPanels({ panels }).panels.slice(0, QUILT_SLOTS) : [];
  return [...valid, ...new Array(QUILT_SLOTS - valid.length).fill(null)];
}
