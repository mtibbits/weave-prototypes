// The tour's words: reads window.BLAZEAHEAD_TOUR (tour-content.js), fills anything missing from the defaults
// below, and renders a stop's card. The 3D world has four stop scenes, so at most four stops are used.

import { TRAIL_COLORS } from './kbmap.js';

export const STOP_IDS = ['continuity', 'scaffolding', 'knowledge', 'in-flight'];

// The knowledge-base trail map (stop 3): what the kiosk, the still and the unfolded map show. The layout stays clean
// up to these limits; anything past them is left out, with one warning.
export const MAP_LIMITS = { trails: 5, destinations: 5, next: 2, stops: 25 };
export const isLink = (url) => typeof url === 'string' && /^https?:\/\/\S+$/i.test(url.trim());

const mapStop = (name, next = []) => ({ name, url: '', next: next.map((n) => ({ name: n, url: '' })) });
export const DEFAULT_MAP = {
  centre: 'blazeAhead',
  trails: [
    { name: 'Getting connected',
      destinations: [mapStop('Proxy'), mapStop('GitLab'), mapStop('Certificates'), mapStop('Access tokens')] },
    { name: 'Agentic workflow',
      destinations: [mapStop('devAgent'), mapStop('Jira'), mapStop('Claude skills'), mapStop('Claude plugins')] },
    { name: 'Language specific',
      destinations: [mapStop('Java', ['Artifactory']), mapStop('C++', ['SonarQube']), mapStop('Python', ['PyPI mirror'])] },
    { name: 'Infrastructure',
      destinations: [mapStop('Deployment', ['AWS account']), mapStop('Terraform'), mapStop('Kubernetes')] },
    { name: 'Corporate knowledge',
      destinations: [mapStop('Confluence'), mapStop('Onboarding'), mapStop('Security & policy')] },
  ],
};

export const DEFAULT_TOUR = {
  trailhead: { sign: 'Trailhead', tourSign: 'The tour' },
  end: { sign: 'Download' },
  stops: [
    {
      sign: 'Continuity',
      title: 'The continuity proxy',
      paragraphs: ['Our network gets busy. When a service answers with a 429 or a 503, an event stream hiccups, or a '
        + 'reply breaks off mid-stream, the continuity proxy absorbs it and carries on. Your Claude Code session keeps '
        + 'going instead of falling over.'],
      points: ['Absorbs 429 and 503 responses', 'Rides out SSE glitches and stream errors',
        'Keeps long sessions flowing'],
    },
    {
      sign: 'Scaffolding',
      title: 'Scaffold your environment',
      paragraphs: ['blazeAhead sets up your development environment and mints the personal access tokens you need, so '
        + 'you start the trail with every key already on the ring.'],
      points: ['Tokens for Jira, Confluence, GitLab and Artifactory', 'A development environment ready to work in'],
    },
    {
      sign: 'Knowledge',
      title: 'The knowledge base',
      paragraphs: ['Every internal tool, charted as trails from one trailhead. Step through the trails, or unfold the map and open a destination.'],
      points: [],
      map: DEFAULT_MAP,
    },
    {
      sign: 'In Flight',
      title: 'The In Flight queue',
      paragraphs: ['In Flight connects to Jira and runs prompts through the devAgent workflow straight from Jira '
        + 'issues. It isn’t about engineering one prompt; it’s about keeping hundreds of them moving.'],
      points: ['Reads your queue from Jira', 'Runs each issue through devAgent', 'Keeps hundreds of prompts moving'],
    },
  ],
  help: { signs: { left: 'Issues', right: 'Docs', ahead: 'Tour' } },
  rocks: ['429 Too Many Requests', '503 Service Unavailable', 'SSE glitch', 'Stream error', 'Timeout'],
};

const isObject = (v) => v !== null && typeof v === 'object' && !Array.isArray(v);
const text = (v, fallback) => (typeof v === 'string' && v.trim() ? v.trim() : fallback);
const strings = (v, fallback) => {
  if (!Array.isArray(v)) return fallback;
  const out = v.filter((s) => typeof s === 'string' && s.trim()).map((s) => s.trim());
  return out.length ? out : fallback;
};

// The owner's map, trimmed to the limits. Anything unusable falls back to the shipped map. What's left out (past the
// limits, unnamed, or a trail with no destinations) is reported in one warning.
function normalizeMap(raw, fallback) {
  const unusable = () => {
    if (raw !== undefined && typeof console !== 'undefined') {
      console.warn('blazeAhead: the knowledge-base map in tour-content.js is unusable (it needs a named trail with a '
        + 'named destination), so the shipped map is shown instead.');
    }
    return fallback;
  };
  if (!isObject(raw) || !Array.isArray(raw.trails)) return unusable();
  const L = MAP_LIMITS;
  const left = [];
  let unnamed = 0;
  let stops = 0;
  const link = (url) => (isLink(url) ? url.trim() : '');
  const named = (item) => {
    if (isObject(item) && text(item.name, '')) return true;
    unnamed += 1;
    return false;
  };
  const trails = [];
  for (const t of raw.trails) {
    if (!named(t)) continue;
    if (trails.length === L.trails) {
      left.push(`the trail "${text(t.name, '')}"`);
      continue;
    }
    const destinations = [];
    for (const d of Array.isArray(t.destinations) ? t.destinations : []) {
      if (!named(d)) continue;
      if (destinations.length === L.destinations || stops === L.stops) {
        left.push(`"${text(d.name, '')}"`);
        continue;
      }
      stops += 1;
      const next = [];
      for (const e of Array.isArray(d.next) ? d.next : []) {
        if (!named(e)) continue;
        if (next.length === L.next || stops === L.stops) {
          left.push(`"${text(e.name, '')}"`);
          continue;
        }
        stops += 1;
        next.push({ name: text(e.name, ''), url: link(e.url) });
      }
      destinations.push({ name: text(d.name, ''), url: link(d.url), next });
    }
    if (destinations.length) trails.push({ name: text(t.name, ''), destinations });
    else left.push(`the trail "${text(t.name, '')}"`);
  }
  if (!trails.length) return unusable();
  if (unnamed) left.push(`${unnamed} unnamed item${unnamed === 1 ? '' : 's'}`);
  if (left.length && typeof console !== 'undefined') {
    console.warn(`blazeAhead: the knowledge-base map keeps ${L.trails} trails, ${L.destinations} destinations on a `
      + `trail, ${L.next} onward stops per destination and ${L.stops} stops in all; left out: ${left.join(', ')}.`);
  }
  return { centre: text(raw.centre, fallback.centre), trails };
}

function normalizeStop(raw, fallback, id) {
  const r = isObject(raw) ? raw : {};
  const stop = {
    id,
    sign: text(r.sign, fallback.sign),
    title: text(r.title, fallback.title),
    paragraphs: strings(r.paragraphs, fallback.paragraphs),
    points: Array.isArray(r.points) ? strings(r.points, []) : fallback.points,
    map: fallback.map ? normalizeMap(r.map, fallback.map) : null,
  };
  return stop;
}

export function normalizeTour(raw) {
  const r = isObject(raw) ? raw : {};
  const d = DEFAULT_TOUR;
  let stops = d.stops;
  if (Array.isArray(r.stops) && r.stops.length) {
    if (r.stops.length > STOP_IDS.length && typeof console !== 'undefined') {
      console.warn(`blazeAhead: the tour has ${STOP_IDS.length} stop scenes; stops after the ${STOP_IDS.length}th are ignored.`);
    }
    stops = r.stops.slice(0, STOP_IDS.length);
  }
  const help = isObject(r.help) && isObject(r.help.signs) ? r.help.signs : {};
  return {
    stops: stops.map((s, i) => normalizeStop(s, d.stops[i], STOP_IDS[i])),
    trailheadSign: text(isObject(r.trailhead) ? r.trailhead.sign : '', d.trailhead.sign),
    tourSign: text(isObject(r.trailhead) ? r.trailhead.tourSign : '', d.trailhead.tourSign),
    endSign: text(isObject(r.end) ? r.end.sign : '', d.end.sign),
    help: {
      left: text(help.left, d.help.signs.left),
      right: text(help.right, d.help.signs.right),
      ahead: text(help.ahead, d.help.signs.ahead),
    },
    rocks: strings(r.rocks, d.rocks),
  };
}

// The words on a signpost, by the label key the world uses.
export function signText(tour, key) {
  if (key === 'trailhead') return tour.trailheadSign;
  if (key === 'download') return tour.endSign;
  if (key === 'tour') return tour.tourSign;
  if (key === 'left' || key === 'right' || key === 'ahead') return tour.help[key];
  const i = STOP_IDS.indexOf(key);
  if (i < 0) return '';
  return tour.stops[i] ? tour.stops[i].sign : DEFAULT_TOUR.stops[i].sign;
}

export function escapeHtml(value) {
  return String(value).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

// How many pages a stop's card has: the knowledge stop has an overview and one page per trail.
export const pageCount = (stop) => (stop && stop.map ? stop.map.trails.length + 1 : 1);

function mapItem(s) {
  return s.url
    ? `<a href="${escapeHtml(s.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(s.name)}</a>`
    : `<span class="kb-plain">${escapeHtml(s.name)}</span>`;
}

// The card body for a stop: its title (focus lands here on arrival), paragraphs and points. The knowledge stop adds
// its current page: the trails at a glance, or one trail's destinations as links.
export function cardHtml(stop, page = 0) {
  const parts = [`<h2 class="card-title" data-card-heading tabindex="-1">${escapeHtml(stop.title)}</h2>`];
  for (const p of stop.paragraphs || []) parts.push(`<p>${escapeHtml(p)}</p>`);
  if (stop.points && stop.points.length) {
    parts.push(`<ul class="card-points">${stop.points.map((p) => `<li>${escapeHtml(p)}</li>`).join('')}</ul>`);
  }
  if (stop.map) {
    const trails = stop.map.trails;
    const i = Math.max(0, Math.min(trails.length, page));
    if (i === 0) {
      parts.push(`<ul class="kb-chips" aria-label="The trails">${trails.map((t, k) => `<li class="kb-chip" `
        + `style="--trail:${TRAIL_COLORS[k]}"><span class="kb-blaze" aria-hidden="true"></span>${escapeHtml(t.name)}</li>`)
        .join('')}</ul>`);
    } else {
      const t = trails[i - 1];
      parts.push(`<section class="kb-trail" style="--trail:${TRAIL_COLORS[i - 1]}" `
        + `aria-label="${escapeHtml(t.name)}: trail ${i} of ${trails.length}">`
        + `<h3><span class="kb-blaze" aria-hidden="true"></span>${escapeHtml(t.name)}</h3><ul class="kb-dests">`
        + t.destinations.map((d) => `<li>${mapItem(d)}${d.next.map((e) => `<span class="kb-then" aria-hidden="true">›</span>${mapItem(e)}`).join('')}</li>`).join('')
        + '</ul></section>');
    }
  }
  return parts.join('');
}

export function loadTour(win = window) {
  return normalizeTour(win.BLAZEAHEAD_TOUR);
}
