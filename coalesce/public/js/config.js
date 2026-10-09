// Reads the owner's settings (window.COALESCE_SITE, from site-config.js) and wires them into the page:
//   [data-link="key"]      gets the resolved URL, or turns into "Link coming soon" when there isn't one
//   [data-text="key"]      gets the text value (teamName, version, releaseDate)
//   [data-requires="key"]  stays hidden while that value is empty

export const MISSING_LABEL = 'Link coming soon';
export const DEFAULT_TEAM = 'the Coalesce team';
const SAFE_URL = /^(https?:\/\/|mailto:|\/|\.\.?\/)/i;

const trimmed = (value) => (typeof value === 'string' ? value.trim() : '');

export function safeUrl(value) {
  const url = trimmed(value);
  return SAFE_URL.test(url) ? url : '';
}

export function resolveConfig(cfg = {}) {
  const links = cfg.links || {};
  const project = safeUrl(cfg.gitlabProjectUrl).replace(/\/+$/, '');
  const onGitLab = /^https?:\/\//i.test(project);
  const file = trimmed(cfg.xlamFileName) || 'Coalesce.xlam';
  const latest = `${project}/-/releases/permalink/latest`;
  let download = '';
  if (onGitLab) download = cfg.downloadLink === 'direct' ? `${latest}/downloads/${encodeURIComponent(file)}` : latest;
  return {
    teamName: trimmed(cfg.teamName) || DEFAULT_TEAM,
    version: trimmed(cfg.version),
    releaseDate: trimmed(cfg.releaseDate),
    urls: {
      docs: safeUrl(links.docs),
      tutorial: safeUrl(links.tutorial),
      serviceDesk: safeUrl(links.serviceDesk),
      access: safeUrl(links.access),
      project: onGitLab ? project : '',
      releases: onGitLab ? `${project}/-/releases` : '',
      download,
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
  applyConfig(win.document, resolveConfig(win.COALESCE_SITE || {}));
}
