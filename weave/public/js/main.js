// WEAVE's boot module: the panel lists first, then the load-time half of the hero contract.
import { cleanPanels } from './catalog.js';
import { renderPanels, setStageLabel } from './dom.js';

const result = cleanPanels(window.WEAVE_PANELS);
if (result.error) console.error(result.error);
result.warnings.forEach((warning) => console.warn(warning));
renderPanels(document.getElementById('panels'), result);
// A broken file keeps the static label from the HTML.
if (!result.error) setStageLabel(document.querySelector('[data-hero]'), result.panels);
