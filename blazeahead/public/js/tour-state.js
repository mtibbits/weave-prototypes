// The tour as a small state machine, independent of any page or renderer.
// index: -1 is the trailhead, 0..count-1 the stops. One walk at a time: requests made while walking are queued,
// and only the latest one counts.
import { STOP_IDS } from './content.js';

export class TourState {
  constructor(count) {
    this.count = Math.max(1, Math.min(Number(count) || 0, STOP_IDS.length));
    this.index = -1;
    this.from = -1;
    this.walking = false;
    this.queued = null;
    this.cardIndex = 0;
    this.lastOutcome = null;
  }

  resolve(target) {
    if (target === 'next') return this.index + 1;
    if (target === 'prev') return this.index - 1;
    const n = Number(target);
    return Number.isFinite(n) ? Math.max(-1, Math.min(this.count - 1, Math.trunc(n))) : this.index;
  }

  // 'walk' (started), 'queued', 'none' (already there), 'exit-start' (back past stop 1) or 'exit-end' (past the last)
  request(target) {
    if (this.walking) {
      this.queued = target;
      return 'queued';
    }
    const to = this.resolve(target);
    if (to >= this.count) return 'exit-end';
    if (to < 0 && target === 'prev') return 'exit-start';
    if (to === this.index) return 'none';
    this.walking = true;
    this.from = this.index;
    this.index = to;
    this.cardIndex = 0;
    return 'walk';
  }

  // Call when a walk ends. Returns the index of the next walk if a queued request started one, else null.
  // lastOutcome keeps what the queued request did, so the page can act on a queued exit.
  arrive() {
    this.walking = false;
    const queued = this.queued;
    this.queued = null;
    this.lastOutcome = queued === null ? null : this.request(queued);
    return this.lastOutcome === 'walk' ? this.index : null;
  }

  hashFor(index) {
    return index >= 0 && index < this.count ? `#${STOP_IDS[index]}` : '';
  }

  indexForHash(hash) {
    const i = STOP_IDS.indexOf(String(hash || '').replace(/^#/, ''));
    return i >= 0 && i < this.count ? i : -1;
  }

  // Where a page opened with this hash should land: -1 (no hash: start at the trailhead), or a stop.
  // An unknown or out-of-range stop opens stop 1.
  static fromHash(hash, count) {
    const h = String(hash || '').replace(/^#/, '');
    if (!h) return -1;
    const i = STOP_IDS.indexOf(h);
    return i >= 0 && i < count ? i : 0;
  }

  nextCard(cards) {
    this.cardIndex = Math.max(0, Math.min(cards - 1, this.cardIndex + 1));
    return this.cardIndex;
  }

  prevCard() {
    this.cardIndex = Math.max(0, this.cardIndex - 1);
    return this.cardIndex;
  }
}
