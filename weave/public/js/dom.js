// The page's DOM writers. Panel strings reach the DOM only through textContent and setAttribute.

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

export function setHeroState() {}
