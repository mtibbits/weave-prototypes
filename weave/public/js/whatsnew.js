// #15's what's-new card: a non-modal card listing the panels new for this visit, under #12's heading. No imports, so the
// still path never pulls in Three.js through it, and it never throws (a missing region skips the card's DOM only).
// It owns the stage's data-release-state and data-new-panels and both of #12's recordSeen() call sites: when the card
// shows (rule a), and at boot when nothing is new (rule b). On the live path the card waits for the first weave:mode
// entry into quilt; on the still path, and on any fall-back to the still while it waits, it shows at once. Every
// string goes in through textContent. On the still path the card's DOM is appended one task after boot, so the empty
// polite region is already in the page when the card lands in it (whether a screen reader announces so early a change
// is untested).

export const GOT_IT = 'Got it';
// #16 adds 'sewing' between pending and card.
export const RELEASE_STATES = Object.freeze(['none', 'pending', 'card', 'done']);

const el = (tag, className, text) => {
  const node = document.createElement(tag);
  node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
};

// The card for #12's heading: the heading, then each group's names (under its version when the panels span
// versions), then the close button.
function buildCard(heading) {
  const card = el('div', 'whatsnew-card');
  card.append(el('h2', 'whatsnew-heading', heading.text));
  for (const group of heading.groups) {
    if (heading.kind === 'since-last-visit') card.append(el('p', 'whatsnew-version', `v${group.version}`));
    const list = el('ul', 'whatsnew-list');
    for (const name of group.names) list.append(el('li', 'whatsnew-name', name));
    card.append(list);
  }
  const close = el('button', 'whatsnew-close', GOT_IT);
  close.type = 'button';
  card.append(close);
  return card;
}

// Focus can go back here: a rendered, connected element outside any [hidden] subtree, never body.
const usable = (node) => node instanceof HTMLElement && node !== document.body && node.isConnected
  && !node.closest('[hidden]') && node.getClientRects().length > 0 && getComputedStyle(node).visibility !== 'hidden';

export function createNews({ stage, region, heading, newIds, recordSeen, live, focusFallbacks = [] }) {
  let state = null;
  let card = null;
  let returnTo = null;
  let appendTimer = 0;

  // The one writer of data-release-state.
  const setState = (next) => {
    state = next;
    stage.dataset.releaseState = next;
  };

  const record = () => {
    try {
      recordSeen();
    } catch (err) {
      console.error(err);
    }
  };

  const onFocusIn = (event) => {
    if (!card || !card.contains(event.target)) returnTo = event.target;
  };
  const onKeyDown = (event) => {
    if (event.key === 'Escape') close();
  };

  // A pointer close (a click's detail counts its presses; Enter and Escape give 0) returns focus without scrolling,
  // so a phone visitor who tapped "Got it" far down the page stays where they are.
  function close(event) {
    if (state !== 'card' || !card) return;
    const preventScroll = event?.detail > 0;
    const inside = card.contains(document.activeElement);
    clearTimeout(appendTimer);
    region.replaceChildren();
    document.removeEventListener('focusin', onFocusIn, true);
    document.removeEventListener('keydown', onKeyDown);
    card = null;
    setState('done');
    if (inside) [returnTo, ...focusFallbacks].find(usable)?.focus({ preventScroll });
  }

  // Shows the card once: the state first (so a re-entry is a no-op), the card (appended now, or one task later at
  // boot), then rule (a). It never moves focus.
  function show({ defer = false } = {}) {
    setState('card');
    stage.removeEventListener('weave:mode', onMode);
    if (region) {
      try {
        card = buildCard(heading);
        card.querySelector('.whatsnew-close').addEventListener('click', close);
        returnTo = document.activeElement;
        document.addEventListener('focusin', onFocusIn, true);
        document.addEventListener('keydown', onKeyDown);
        if (defer) appendTimer = setTimeout(() => region.append(card), 0);
        else region.append(card);
      } catch (err) {
        console.error(err);
      }
    }
    record();
  }

  const onMode = (event) => {
    if (state === 'pending' && event.detail?.mode === 'quilt') show();
  };

  stage.dataset.newPanels = heading ? newIds.join(' ') : '';
  if (!heading) {
    setState('none');
    record();
  } else if (!live) {
    show({ defer: true });
  } else {
    setState('pending');
    stage.addEventListener('weave:mode', onMode);
  }

  return {
    get state() { return state; },
    // A fall-back to the still: the card shows at once if it was still waiting for the quilt.
    fallBack() {
      if (state === 'pending') show();
    },
  };
}
