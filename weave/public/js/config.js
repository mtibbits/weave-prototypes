// Reads the owner's settings (window.WEAVE_SITE, from site-config.js) and wires them into the page. Ported from
// Coalesce's config.js, cut down to the team name and the Help page's three links:
//   [data-link="key"]      gets the resolved URL, or turns into "Link coming soon" when there isn't one
//   [data-text="key"]      gets the text value (teamName)
//   [data-requires="key"]  stays hidden while that value is empty
// Every write is text or an attribute; nothing here parses HTML.

export const MISSING_LABEL = 'Link coming soon';
export const DEFAULT_TEAM = 'the WEAVE team';
const SAFE_URL = /^(https?:\/\/|mailto:|\/|\.\.?\/)/i;

const trimmed = (value) => (typeof value === 'string' ? value.trim() : '');

export function safeUrl(value) {
  const url = trimmed(value);
  return SAFE_URL.test(url) ? url : '';
}

export function resolveConfig(cfg = {}) {
  const links = cfg.links || {};
  return {
    teamName: trimmed(cfg.teamName) || DEFAULT_TEAM,
    urls: {
      serviceDesk: safeUrl(links.serviceDesk),
      tutorial: safeUrl(links.tutorial),
      docs: safeUrl(links.docs),
    },
  };
}

export function applyConfig(root, resolved) {
  for (const el of root.querySelectorAll('[data-link]')) {
    const url = resolved.urls[el.dataset.link] || '';
    if (url) {
      el.setAttribute('href', url);
      el.removeAttribute('aria-disabled');
      el.classList.remove('is-missing');
      continue;
    }
    el.removeAttribute('href');
    el.setAttribute('aria-disabled', 'true');
    el.classList.add('is-missing');
    const cta = el.querySelector('[data-cta]');
    if (cta) cta.textContent = MISSING_LABEL;
    else el.setAttribute('title', MISSING_LABEL);
  }
  for (const el of root.querySelectorAll('[data-text]')) {
    const value = resolved[el.dataset.text];
    if (typeof value === 'string' && value) el.textContent = value;
  }
  for (const el of root.querySelectorAll('[data-requires]')) {
    el.hidden = !resolved[el.dataset.requires];
  }
}

export function boot(win = window) {
  applyConfig(win.document, resolveConfig(win.WEAVE_SITE || {}));
}
