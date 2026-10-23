// The Help page's hero (#18): one corner of the quilt coming apart, with loose threads swaying, a needle and a spool
// of thread beside it, and the pointer stirring the threads. It follows E1's hero contract (main.js): the load-time
// decision first, then Three.js and the scene through import() on the live path only, so the still path never
// requests them. It never loads panels.js: the corner's fabrics are constants here, so the Help still never goes
// stale from a panels.js edit.
import { readHooks, setPaused, showLiveControls } from './dom.js';
import { decideMode, FrameWatchdog, readEnvironment } from './eligibility.js';

const LOAD_FAILED = 'WEAVE: the frayed corner could not load, so the still image stays.';
const WEBGL_FAILED = 'WEAVE: WebGL setup failed, so the still image stays.';

const hooks = readHooks(window.location.search);
const stage = document.querySelector('[data-hero]');
const controls = document.querySelector('[data-controls]');
const pause = document.querySelector('[data-pause]');

// The one writer of the stage's state attributes. Help has no hint line, so dom.js's setHeroState (which writes one)
// is not used.
function setHeroState(state, reason) {
  stage.dataset.heroState = state;
  stage.dataset.heroReason = reason;
}

async function startHero() {
  const decision = decideMode(readEnvironment(window));
  if (!decision.live) {
    setHeroState('still', decision.reason);
    return;
  }
  setHeroState('still', 'loading');
  let modules;
  try {
    const [THREE, scene, needle, spool, fabric, layout, random, fray] = await Promise.all([import('three'),
      import('./scene.js'), import('./needle.js'), import('./spool.js'), import('./fabric.js'), import('./layout.js'),
      import('./random.js'), import('./fray.js')]);
    modules = { THREE, scene, needle, spool, fabric, layout, random, fray };
  } catch (err) {
    console.warn(LOAD_FAILED, err);
    setHeroState('still', 'load-failed');
    return;
  }
  startLive(modules);
}

function startLive() {}

startHero();
