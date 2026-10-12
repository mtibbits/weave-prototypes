// Mounts the live 3D scene on a page, or leaves the still image in place when 3D shouldn't or can't run.
// Three.js and the world download only after the device qualifies. The element reports what happened in
// data-stage-state ('live' or 'still') and data-stage-reason.
import { readEnvironment, decideMode } from './eligibility.js';

export function setStageState(el, state, reason) {
  el.dataset.stageState = state;
  el.dataset.stageReason = reason;
  return { state, reason };
}

export async function mountStage(el, options = {}) {
  if (!el) return { state: 'still', reason: 'no-stage' };
  const decision = decideMode(readEnvironment(window));
  if (!decision.live) return setStageState(el, 'still', decision.reason);
  setStageState(el, 'still', 'loading');
  let live;
  try {
    live = await import('./stage-live.js');
  } catch (err) {
    console.warn('blazeAhead: the 3D scene could not load, so the still image stays.', err);
    return setStageState(el, 'still', 'load-failed');
  }
  return live.startLive(el, options, setStageState);
}
