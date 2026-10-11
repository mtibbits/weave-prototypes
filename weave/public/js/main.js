// WEAVE's boot module: the panel lists first, then the load-time half of the hero contract.
import { cleanPanels } from './catalog.js';
import { renderPanels, setStageLabel, setHeroState } from './dom.js';
import { decideMode, readEnvironment } from './eligibility.js';

const result = cleanPanels(window.WEAVE_PANELS);
if (result.error) console.error(result.error);
result.warnings.forEach((warning) => console.warn(warning));
const stage = document.querySelector('[data-hero]');
renderPanels(document.getElementById('panels'), result);
// A broken file keeps the static label from the HTML.
if (!result.error) setStageLabel(stage, result.panels);

async function startHero() {
  const hint = document.querySelector('[data-hint]');
  const decision = decideMode(readEnvironment(window));
  if (!decision.live) {
    setHeroState(stage, hint, 'still', decision.reason);
    return;
  }
  setHeroState(stage, hint, 'still', 'loading');
  try {
    // Dynamic only: the still path must never request Three.js.
    await import('three');
  } catch (err) {
    console.warn('WEAVE: Three.js could not load, so the still image stays.', err);
    setHeroState(stage, hint, 'still', 'load-failed');
  }
  // On success there is no scene yet: the stage stays still/loading until #7 mounts it and sets live/ok.
}

startHero();
