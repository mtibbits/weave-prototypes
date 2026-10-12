// The tour page: signposts and keys move between four stops. Live, the camera walks the path (Task: stage-live);
// as stills, the images cross-fade. The page's DOM carries the whole tour, so it works with or without 3D.
import { loadTour, cardHtml, pageCount } from './content.js';
import { TourState } from './tour-state.js';
import { BOARD, layoutMap, drawMap, svgPainter, canvasMeasure, loadMapFonts, quadMatrix3d } from './kbmap.js';

const STILLS = '../assets/stills/';
const HOME = '../';
const INSTALL = '../#install';
const FADE_MS = 400;
const GRACE_MS = 4000;   // how long a first visit waits at the trailhead for the 3D walk before setting off on stills
const DESCRIPTIONS = {
  trailhead: 'A trailhead at night: a log signpost points down a torch-lit forest path.',
  continuity: 'A stream at night. Small lights ride the current and swirl around the rocks without stopping.',
  scaffolding: 'Base camp: a tent glowing from inside, a gear crate, a lantern and a rack of four tagged keys.',
  knowledge: 'A trail kiosk headed Knowledge Base, with a map of coloured trails leading from blazeAhead to the company’s tools.',
  'in-flight': 'A clearing under the stars: lights lift off a board of issue tags and stream away over the trees.',
};

function q(root, sel) {
  return root.querySelector(sel);
}

// `live` is the stage from mountStage, or the promise of it: the tour starts at once on stills and the 3D scene
// takes over wherever the reader is when it has loaded.
export async function startTour({ win = window, live = null, grace = GRACE_MS } = {}) {
  const doc = win.document;
  const tour = loadTour(win);
  const count = tour.stops.length;
  const state = new TourState(count);
  const reduced = typeof win.matchMedia === 'function' && win.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const els = {
    main: q(doc, 'main'),
    stage: q(doc, '[data-stage]'),
    layers: [...doc.querySelectorAll('[data-stage] img.stage-still')],
    card: q(doc, '[data-tour-card]'),
    eyebrow: q(doc, '[data-card-eyebrow]'),
    body: q(doc, '[data-card-body]'),
    pager: q(doc, '[data-pager]'),
    prev: q(doc, '[data-card-prev]'),
    next: q(doc, '[data-card-next]'),
    counter: q(doc, '[data-card-count]'),
    left: q(doc, 'button[data-sign=left]'),
    right: q(doc, 'button[data-sign=right]'),
    map: q(doc, 'nav[data-trail-map] ol'),
    mapLabel: q(doc, '[data-map-label]'),
    hint: q(doc, '.tour-hint'),
    unfold: q(doc, '[data-kb-unfold]'),
    sheet: q(doc, '[data-kb-sheet]'),
    sheetMap: q(doc, '[data-kb-sheet-map]'),
    sheetClose: q(doc, '[data-kb-close]'),
    overlay: q(doc, '[data-kb-overlay]'),
  };
  let stillSigns = {};     // the sign boards' boxes in each still image (buttons appear once they are known)
  let shown = 0;           // which still layer is on top
  let stage = null;        // the live stage (set by attachLive), or null for stills
  const coming = els.stage.dataset.stageReason === 'loading' || Boolean(live && live.state === 'live');

  const idFor = (i) => (i < 0 ? 'trailhead' : tour.stops[i].id);
  const signWords = (i) => ({
    left: i <= 0 ? tour.trailheadSign : tour.stops[i - 1].sign,
    right: i >= count - 1 ? tour.endSign : tour.stops[i + 1].sign,
  });

  // ---- trail map: Trailhead, the stops, Download
  const marks = [{ goto: '-1', label: tour.trailheadSign }, ...tour.stops.map((s, i) => ({ goto: String(i), label: s.sign })),
    { goto: 'end', label: tour.endSign }];
  els.map.innerHTML = '';
  for (const m of marks) {
    const li = doc.createElement('li');
    const b = doc.createElement('button');
    b.type = 'button';
    b.dataset.goto = m.goto;
    b.setAttribute('aria-label', m.label);
    b.title = m.label;
    b.addEventListener('click', () => {
      if (m.goto === '-1') win.location.href = HOME;
      else if (m.goto === 'end') win.location.href = INSTALL;
      else go(Number(m.goto));
    });
    li.append(b);
    els.map.append(li);
  }

  // ---- card and signs
  function renderCard(i) {
    const stop = tour.stops[i];
    els.eyebrow.textContent = `Stop ${i + 1} of ${count}`;
    els.body.innerHTML = cardHtml(stop, state.cardIndex);
    const pages = pageCount(stop);
    els.pager.hidden = pages < 2;
    if (pages > 1) {
      els.counter.textContent = `${state.cardIndex + 1} of ${pages}`;
      els.prev.disabled = state.cardIndex === 0;
      els.next.disabled = state.cardIndex >= pages - 1;
    }
    els.unfold.hidden = !stop.map;
    els.hint.hidden = Boolean(stop.map);
    syncMap();
  }

  // ---- the knowledge-base map: the trail lit on the kiosk is the card's trail page, and none anywhere else
  function litTrail() {
    const stop = tour.stops[state.index];
    return stop && stop.map && state.cardIndex > 0 ? state.cardIndex - 1 : null;
  }

  let overlayReady = false;     // the still's map has been drawn at least once
  function syncMap() {
    const trail = litTrail();
    doc.body.dataset.kbTrail = trail === null ? '' : String(trail);
    mapLayout().then((laid) => {
      if (!laid) return;
      if (stage && stage.paintMap) {
        stage.paintMap(laid, litTrail());
      } else {
        const painter = svgPainter(doc);
        drawMap(painter, laid, { focus: litTrail(), paper: false });
        painter.svg.setAttribute('aria-hidden', 'true');
        els.overlay.replaceChildren(painter.svg);
        overlayReady = true;
      }
      placeOverlay();
    }).catch((err) => console.warn('blazeAhead: the knowledge-base map could not be drawn.', err));
  }

  // On the still image, the map is laid over the kiosk's board, warped onto its four corners and multiplied into the
  // picture so the still's lantern light shows through. Only at the knowledge stop, and not while walking.
  function placeOverlay() {
    const corners = (stillSigns.knowledge || {}).board;
    const stop = tour.stops[state.index];
    const img = els.layers[shown];
    const show = overlayReady && !stage && Boolean(stop && stop.map) && Array.isArray(corners) && Boolean(img)
      && doc.body.dataset.tourWalking !== 'true';
    els.overlay.hidden = !show;
    if (!show) return;
    const r = img.getBoundingClientRect();
    const m = els.main.getBoundingClientRect();
    const quad = corners.map(([fx, fy]) => [r.left - m.left + fx * r.width, r.top - m.top + fy * r.height]);
    els.overlay.style.transform = quadMatrix3d(BOARD.w, BOARD.h, quad);
  }
  els.overlay.addEventListener('click', () => openSheet(q(doc, '[data-card-heading]')));

  // laid out once, when first needed, after the fonts are in
  const mapStop = tour.stops.find((s) => s.map) || null;
  let laying = null;
  function mapLayout() {
    if (!mapStop) return Promise.resolve(null);
    if (!laying) {
      laying = loadMapFonts(doc).then(() => {
        const laid = layoutMap(mapStop.map, canvasMeasure(doc));
        if (laid.crowded) {
          console.warn('blazeAhead: the knowledge-base map is crowded, so some names may overlap. Try fewer or shorter names.');
        }
        return laid;
      });
    }
    return laying;
  }

  // The unfolded map: a modal dialog (Escape and Close shut it; focus goes back to whatever opened it). Only while
  // standing at the knowledge stop: a keyboard can still press the card's (faded) Unfold button during a walk.
  let sheetReturn = null;
  const atMap = () => !state.walking && Boolean(tour.stops[state.index] && tour.stops[state.index].map);
  function openSheet(returnTo) {
    if (!atMap()) return Promise.resolve();
    return mapLayout().then((laid) => {
      if (!laid || els.sheet.open || !atMap()) return;
      const painter = svgPainter(doc);
      drawMap(painter, laid, { links: true });
      painter.svg.setAttribute('role', 'group');
      painter.svg.setAttribute('aria-label', 'Knowledge base trail map');
      els.sheetMap.replaceChildren(painter.svg);
      sheetReturn = returnTo;
      els.sheet.showModal();
    }).catch((err) => console.warn('blazeAhead: the knowledge-base map could not be unfolded.', err));
  }
  // Restoring focus happens synchronously with the close, not from the dialog's own `close` event: that event is
  // queued a tick after `open` goes false, which races anything polling `.open` (a keyboard Escape from a target
  // that isn't already focused, such as the kiosk board, could lose that race and leave focus stuck in the dialog).
  function closeSheet() {
    if (!els.sheet.open) return;
    els.sheet.close();
    const back = sheetReturn;
    sheetReturn = null;
    if (back && back.isConnected && !back.hidden) back.focus({ preventScroll: true });
  }
  els.unfold.addEventListener('click', () => openSheet(els.unfold));
  els.sheetClose.addEventListener('click', closeSheet);
  els.sheet.addEventListener('cancel', (event) => {
    event.preventDefault();
    closeSheet();
  });

  function render(i) {
    renderCard(i);
    const words = signWords(i);
    els.left.setAttribute('aria-label', `Back: ${words.left}`);
    els.right.setAttribute('aria-label', `Next: ${words.right}`);
    for (const b of els.map.querySelectorAll('button')) {
      if (b.dataset.goto === String(i)) b.setAttribute('aria-current', 'step');
      else b.removeAttribute('aria-current');
    }
    els.mapLabel.textContent = tour.stops[i].sign;
    els.stage.setAttribute('aria-label', DESCRIPTIONS[idFor(i)] || '');
    doc.body.dataset.tourIndex = String(i);
    placeSigns();
  }

  // Sign buttons sit over the boards: projected from the live scene, or taken from the still image's boxes.
  function placeSigns() {
    const i = state.index;
    if (i < 0) return;
    const mainRect = els.main.getBoundingClientRect();
    for (const side of ['left', 'right']) {
      let box = null;
      if (stage && stage.signBox) box = stage.signBox(side);
      if (!box) {
        const frac = (stillSigns[idFor(i)] || {})[side];
        const img = els.layers[shown];
        if (frac && img) {
          const r = img.getBoundingClientRect();
          box = [r.left + frac[0] * r.width, r.top + frac[1] * r.height, r.left + frac[2] * r.width, r.top + frac[3] * r.height];
        }
      }
      const btn = side === 'left' ? els.left : els.right;
      if (!box) {
        btn.hidden = true;
        continue;
      }
      const x0 = Math.max(mainRect.left, box[0]);
      const y0 = Math.max(mainRect.top, box[1]);
      const x1 = Math.min(mainRect.right, box[2]);
      const y1 = Math.min(mainRect.bottom, box[3]);
      btn.hidden = false;
      btn.style.left = `${x0 - mainRect.left}px`;
      btn.style.top = `${y0 - mainRect.top}px`;
      btn.style.width = `${Math.max(24, x1 - x0)}px`;
      btn.style.height = `${Math.max(24, y1 - y0)}px`;
    }
    placeOverlay();
  }

  function setWalking(on) {
    doc.body.dataset.tourWalking = on ? 'true' : 'false';
    if (on) els.card.setAttribute('data-hidden', '');
    else els.card.removeAttribute('data-hidden');
    els.left.disabled = on;
    els.right.disabled = on;
    placeOverlay();
  }

  // ---- stills
  function showStill(id, instant) {
    const next = 1 - shown;
    const img = els.layers[next];
    const src = `${STILLS}${id}.webp`;
    return new Promise((resolve) => {
      const reveal = () => {
        img.classList.remove('is-hidden');
        els.layers[shown].classList.add('is-hidden');
        shown = next;
        if (instant) resolve();
        else win.setTimeout(resolve, FADE_MS);
      };
      if (img.getAttribute('src') === src && img.complete) {
        reveal();
        return;
      }
      img.onload = reveal;
      img.onerror = reveal;
      img.setAttribute('src', src);
    });
  }

  async function travel(from, to) {
    if (stage && stage.walk) {
      await stage.walk(from, to);
      return;
    }
    await showStill(idFor(to), reduced);
  }

  // ---- moving between stops
  let busy = false;

  async function go(target, { push = true, focus = true } = {}) {
    closeSheet();
    const outcome = state.request(target);
    if (outcome === 'exit-start') {
      win.location.href = HOME;
      return;
    }
    if (outcome === 'exit-end') {
      win.location.href = INSTALL;
      return;
    }
    if (outcome !== 'walk' || busy) return;
    busy = true;
    let pushHistory = push;
    for (;;) {
      const to = state.index;
      if (pushHistory) win.history.pushState(null, '', state.hashFor(to));
      else win.history.replaceState(null, '', state.hashFor(to));
      setWalking(true);
      syncMap();
      await travel(state.from, to);
      const next = state.arrive();
      if (next === null) break;
      pushHistory = true;
    }
    busy = false;
    render(state.index);
    setWalking(false);
    if (state.lastOutcome === 'exit-end') win.location.href = INSTALL;
    else if (state.lastOutcome === 'exit-start') win.location.href = HOME;
    else if (focus) {
      const heading = q(doc, '[data-card-heading]');
      if (heading) heading.focus({ preventScroll: true });
    }
  }

  els.left.addEventListener('click', () => go('prev'));
  els.right.addEventListener('click', () => go('next'));
  els.prev.addEventListener('click', () => {
    state.prevCard();
    renderCard(state.index);
  });
  els.next.addEventListener('click', () => {
    state.nextCard(pageCount(tour.stops[state.index]));
    renderCard(state.index);
  });
  win.addEventListener('keydown', (event) => {
    if (els.sheet.open) return;   // the dialog handles its own keys (Escape closes it)
    if (event.altKey || event.ctrlKey || event.metaKey || event.defaultPrevented) return;
    if (event.key === 'ArrowRight') {
      event.preventDefault();
      go('next');
    } else if (event.key === 'ArrowLeft') {
      event.preventDefault();
      go('prev');
    } else if (event.key === 'Escape') {
      win.location.href = HOME;
    }
  });
  win.addEventListener('hashchange', () => {
    const i = state.indexForHash(win.location.hash);
    if (i >= 0 && i !== state.index) go(i, { push: false });
  });
  win.addEventListener('resize', placeSigns);

  win.fetch('../assets/still-signs.json')
    .then((res) => (res.ok ? res.json() : {}))
    .then((boxes) => {
      stillSigns = boxes || {};
      placeSigns();
    })
    .catch(() => {});

  const api = {
    state,
    tour,
    go,
    placeSigns,
    // The 3D scene takes over at the current stop (a stage that has already stopped is ignored)
    attachLive(liveStage) {
      if (!liveStage || liveStage.state !== 'live' || stage === liveStage) return;
      stage = liveStage;
      stage.onstop = () => api.detachLive();
      if (state.index >= 0 && stage.show) stage.show(state.index);
      stage.onboard = () => openSheet(q(doc, '[data-card-heading]'));
      syncMap();
      placeSigns();
    },
    detachLive() {
      stage = null;
      showStill(idFor(Math.max(0, state.index)), true).then(() => {
        placeSigns();
        syncMap();
      });
    },
  };
  win.__tour = api;
  const arriving = Promise.resolve(live).catch(() => null);
  arriving.then(api.attachLive);

  // ---- start. A deep link, or a device without 3D, opens its stop at once. A first visit waits at the trailhead
  // for the 3D walk to stop 1, but only for `grace` ms; then it sets off on stills and the 3D joins later.
  const start = TourState.fromHash(win.location.hash, count);
  if (start >= 0 || !coming) {
    state.index = Math.max(0, start);
    win.history.replaceState(null, '', state.hashFor(state.index));
    await showStill(idFor(state.index), true);
    render(state.index);
    setWalking(false);
    return api;
  }
  state.index = -1;
  await showStill('trailhead', true);
  await Promise.race([arriving, new Promise((resolve) => { win.setTimeout(resolve, grace); })]);
  if (state.index === -1 && !busy) await go(0, { push: false, focus: false });
  return api;
}
