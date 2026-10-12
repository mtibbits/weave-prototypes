# Knowledge-Base Trail Map Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give tour stop 3's kiosk a trail map of about 20 knowledge-base destinations (5 coloured trails, second- and third-level stops). The card steps through the trails and lights each one up; an unfold-the-map dialog makes every destination clickable. One browser module draws the map for the live 3D kiosk, the fallback still image and the dialog.

**Architecture:** The tree lives in `public/tour-content.js`, and `content.js` normalises it. `public/js/kbmap.js` lays it out on a 1380 × 880-unit board and draws it through a painter: SVG for the page, Canvas 2D for the 3D texture. The Blender build leaves the kiosk board blank and exports its 3D frame, a light grid and its four corners in the knowledge still. The live scene paints the map onto a panel at that frame; the still gets the SVG warped onto those corners with a CSS `matrix3d` and multiply-blended.

**Tech Stack:**
- Vanilla ES modules and Three.js (vendored), SVG and Canvas 2D.
- The Blender 5.2 Python build (`blender/`).
- pytest + Playwright (Chromium), run from the repo's `.venv`.

**Spec:** `docs/superpowers/specs/2026-09-25-kb-trail-map-design.md`. Read it with this plan. The main site spec is `docs/superpowers/specs/2026-09-25-blazeahead-site-design.md`.

**Prototype:** `.superpowers/brainstorm/kb-map/proto/` (gitignored). Its `kbmap.js` is where the layout in Task 2 was tuned and checked. The code in Task 2 is that prototype, cleaned up.

## Global Constraints

These values override the spec where they differ; Task 1 and Task 2 update the spec to match.

- **Map limits:**
  - 5 trails, 5 destinations per trail, 2 `next` stops per destination, 25 stops in all (third-level ones count).
  - Names longer than 32 characters are cut with `…` on the map only.
  - These replace the spec's 6 trails / 30 / 3. Six-trail and 30-stop layouts were tried in the prototype and don't stay clean.
- **Trail colours, in order:** `#2F6FA3`, `#B8452A`, `#3E7D4C`, `#74509C`, `#A0721A`.
- **Paper colour:** `#DCCDA6`, the Blender paper's albedo, so the live board and the still match. It replaces the spec's `#E3D2A9`.
- **Board:** 1380 × 880 units = the real 1.38 × 0.88 m board. The margin is 30 units. The type floor is `MIN_SCALE = 0.6`.
- **Links:**
  - A `url` becomes a link only if it matches `^https?://\S+$` after trimming.
  - Links use `target="_blank" rel="noopener noreferrer"`.
- **Copy:**
  - Button: **Unfold the map**.
  - Dialog title: **Knowledge base trail map**.
  - Crowded-map warning: `blazeAhead: the knowledge-base map is crowded, so some names may overlap. Try fewer or shorter names.`
- **No product logos** anywhere.
- **Budgets:** the existing page-weight budgets in `tools/verify.py` must still hold.
- **Running things (Windows).** Run from `C:\Programs\src\blazeahead-site` in Git Bash:
  - Tests: `.venv/Scripts/python.exe -m pytest <path> -q`.
  - Blender: `"/c/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b --factory-startup --python-exit-code 1 --python blender/build_blazeahead.py -- [options]`.
- **Commits.** Commit with `git commit -F - <<'EOF' … EOF`. End every message with the line `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`. Work happens on branch `feature/kb-trail-map` (already checked out).
- **Editing code with backslashes.** Write regex-heavy code with an editor tool, not a shell heredoc: heredocs mangle `\n`, `\0` and `\b`.

## Review Focus

These are the five inputs and conditions most likely to bite a real visitor or owner that the spec implies but doesn't spell out. Each has a test in the task named.

1. **Owner hand-edits the tree badly:** a destination without a name but with a URL, a trail with no destinations, `next` that isn't a list. Expected: those pieces are dropped, the rest shows, and nothing throws. (Task 1: `test_a_broken_map_falls_back_to_the_draft_and_other_stops_have_none`.)
2. **Names containing markup or `&`**, e.g. `<b>R&D</b>`. Expected: shown as literal words on the card and on the map, never as markup. (Task 3: `test_card_html_escapes_copy_and_pages_through_the_trails`; Task 4: `test_names_with_markup_stay_words`.)
3. **The window is resized while the still map is showing.** Expected: the map stays on the kiosk board. (Task 7: `test_the_still_map_follows_the_card_and_the_window`.)
4. **Browser Back is pressed while the unfolded map is open.** Expected: the dialog closes and the tour walks back, rather than a modal floating over another stop. (Task 4: `test_going_back_with_the_map_open_closes_it`.)
5. **The web fonts fail to load** (blocked or offline). Expected: the map still lays out and draws with fallback fonts, with no page errors. (Task 4: `test_the_map_still_draws_when_the_fonts_fail`.)

---

### Task 1: The trail map in the content model

**Files:**
- Modify: `public/js/content.js` (add `MAP_LIMITS`, `isLink`, `DEFAULT_MAP`, `normalizeMap`; the knowledge default gets `map`; `normalizeStop` sets `stop.map`)
- Modify: `public/tour-content.js` (add the `map` to the knowledge stop; keep `cards` for now, since Task 3 removes them)
- Modify: `docs/superpowers/specs/2026-09-25-kb-trail-map-design.md` (limits and colours)
- Test: `tests/test_content.py`

**Interfaces:**
- Produces, from `content.js`:
  - `MAP_LIMITS = { trails: 5, destinations: 5, next: 2, stops: 25 }`
  - `isLink(url) → boolean`
  - `DEFAULT_MAP`
  - `normalizeTour(raw).stops[i].map`, which is `null` for stops 0, 1 and 3, and for stop 2 is `{ centre: string, trails: [{ name: string, destinations: [{ name: string, url: string, next: [{ name: string, url: string }] }] }] }`. Every `url` is either `''` or a trimmed `http(s)` link.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_content.py`)

```python
def test_the_knowledge_stop_ships_the_draft_trail_map(js):
    r = content(js, """const m = C.normalizeTour(undefined).stops[2].map;
      const stops = m.trails.flatMap((t) => t.destinations.flatMap((d) => [d, ...d.next]));
      return [m.centre, m.trails.map((t) => t.name), stops.length, stops.every((s) => s.url === ''),
              m.trails[2].destinations.map((d) => [d.name, d.next.map((e) => e.name)])];""")
    centre, trails, count, unlinked, language = r
    assert centre == "blazeAhead"
    assert trails == ["Getting connected", "Agentic workflow", "Language specific", "Infrastructure",
                      "Corporate knowledge"]
    assert count == 21 and unlinked is True
    assert language == [["Java", ["Artifactory"]], ["C++", ["SonarQube"]], ["Python", ["PyPI mirror"]]]


def test_only_web_links_become_links(js):
    raw = {"stops": [{}, {}, {"map": {"centre": "Start", "trails": [{"name": "T", "destinations": [
        {"name": "a", "url": "https://wiki.example.com/a"}, {"name": "b", "url": "javascript:alert(1)"},
        {"name": "c", "url": "  http://x.example.com  "}, {"name": "d", "url": "www.example.com"},
        {"name": "e"}]}]}}]}
    r = content(js, f"return C.normalizeTour({json.dumps(raw)}).stops[2].map;")
    assert r["centre"] == "Start"
    assert [(d["name"], d["url"]) for d in r["trails"][0]["destinations"]] == [
        ("a", "https://wiki.example.com/a"), ("b", ""), ("c", "http://x.example.com"), ("d", ""), ("e", "")]


def test_the_map_keeps_to_its_limits_and_says_what_it_left_out(js):
    r = content(js, """const warned = []; const orig = console.warn; console.warn = (m) => warned.push(String(m));
      const one = (n) => ({name: n});
      const map = (trails) => C.normalizeTour({stops: [{}, {}, {map: {trails}}]}).stops[2].map;
      const a = map(Array.from({length: 7}, (_, i) => ({name: 'T' + i, destinations: [one('d' + i)]})));
      const b = map([{name: 'T', destinations: Array.from({length: 8}, (_, j) => one('d' + j))}]);
      const c = map([{name: 'T', destinations: [{name: 'd', next: [one('n1'), one('n2'), {name: 'n3'},
                                                                   {name: 'n4', next: [one('deep')]}]}]}]);
      const d = map(Array.from({length: 5}, (_, i) => ({name: 'T' + i,
        destinations: Array.from({length: 5}, (_, j) => ({name: `d${i}.${j}`, next: [one(`n${i}.${j}`)]}))})));
      console.warn = orig;
      const count = (m) => m.trails.flatMap((t) => t.destinations.flatMap((x) => [x, ...x.next])).length;
      return [a.trails.length, b.trails[0].destinations.length, c.trails[0].destinations[0].next.length,
              c.trails[0].destinations[0].next.some((e) => 'next' in e), count(d), warned.length,
              warned.every((w) => w.startsWith('blazeAhead: the knowledge-base map keeps'))];""")
    assert r == [5, 5, 2, False, 25, 4, True]


def test_a_broken_map_falls_back_to_the_draft_and_other_stops_have_none(js):
    r = content(js, """const bad = [undefined, 'map', {trails: 'x'},
        {trails: [{name: '', destinations: [{name: 'a'}]},
                  {name: 'T', destinations: [{url: 'https://x.example.com'}, 7, {name: 'ok', next: 'nope'}]},
                  {name: 'Empty', destinations: []}]}];
      const tours = bad.map((m) => C.normalizeTour({stops: [{map: {trails: [{name: 'X', destinations: [{name: 'y'}]}]}},
                                                            {}, {map: m}]}));
      const kept = tours[3].stops[2].map.trails;
      return [tours.slice(0, 3).map((t) => t.stops[2].map.trails.length), kept.map((t) => t.name),
              kept[0].destinations.map((d) => [d.name, d.next.length]), tours[0].stops[0].map];""")
    assert r == [[5, 5, 5], ["T"], [["ok", 0]], None]
```

Also update the last assertion of the existing `test_shipped_files_load_and_match_the_world`. Change the returned list to add the map's trail count:

```python
      return [typeof window.BLAZEAHEAD_SITE, t.stops.map((s) => s.sign), t.stops[2].cards.length, t.rocks.length,
              t.stops[2].map.trails.length];""")
    assert r == ["object", ["Continuity", "Scaffolding", "Knowledge", "In Flight"], 3, 5, 5]
```

- [ ] **Step 2: Run the tests to check they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_content.py -q`
Expected: the 4 new tests and `test_shipped_files_load_and_match_the_world` FAIL (`map` is undefined).

- [ ] **Step 3: Implement the map in `content.js`**

Add after `const PLACEHOLDER = …`:

```js
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
```

In `DEFAULT_TOUR.stops[2]` (the Knowledge stop), add `map: DEFAULT_MAP,` after `cards: [...]`.

Add after the `strings` helper:

```js
// The owner's map, trimmed to the limits. Anything unusable falls back to the shipped map.
function normalizeMap(raw, fallback) {
  if (!isObject(raw) || !Array.isArray(raw.trails)) return fallback;
  const L = MAP_LIMITS;
  const left = [];
  let stops = 0;
  const link = (url) => (isLink(url) ? url.trim() : '');
  const trails = [];
  for (const t of raw.trails) {
    if (!isObject(t) || !text(t.name, '')) continue;
    if (trails.length === L.trails) {
      left.push(`the trail "${text(t.name, '')}"`);
      continue;
    }
    const destinations = [];
    for (const d of Array.isArray(t.destinations) ? t.destinations : []) {
      if (!isObject(d) || !text(d.name, '')) continue;
      if (destinations.length === L.destinations || stops === L.stops) {
        left.push(`"${text(d.name, '')}"`);
        continue;
      }
      stops += 1;
      const next = [];
      for (const e of Array.isArray(d.next) ? d.next : []) {
        if (!isObject(e) || !text(e.name, '')) continue;
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
  }
  if (!trails.length) return fallback;
  if (left.length && typeof console !== 'undefined') {
    console.warn(`blazeAhead: the knowledge-base map keeps ${L.trails} trails, ${L.destinations} destinations on a `
      + `trail, ${L.next} onward stops per destination and ${L.stops} stops in all; left out: ${left.join(', ')}.`);
  }
  return { centre: text(raw.centre, fallback.centre), trails };
}
```

In `normalizeStop`, add `map: fallback.map ? normalizeMap(r.map, fallback.map) : null,` to the `stop` object literal (after `points`).

- [ ] **Step 4: Add the map to `public/tour-content.js`**

In the Knowledge stop, after `points: [],` and before the `cards` comment, add:

```js
      // The trail map on the kiosk: trails from the centre, each with its destinations. A destination can lead on to
      // more (`next`). Up to 5 trails, 5 destinations on a trail, 2 onward stops per destination, and 25 stops in all.
      // A `url` that starts with https:// makes the name a link on the card and on the unfolded map; leave it '' and
      // the name shows as plain text. The map lays itself out, so there is nothing to position.
      map: {
        centre: 'blazeAhead',
        trails: [
          { name: 'Getting connected', destinations: [
            { name: 'Proxy', url: '' },
            { name: 'GitLab', url: '' },
            { name: 'Certificates', url: '' },
            { name: 'Access tokens', url: '' },
          ] },
          { name: 'Agentic workflow', destinations: [
            { name: 'devAgent', url: '' },
            { name: 'Jira', url: '' },
            { name: 'Claude skills', url: '' },
            { name: 'Claude plugins', url: '' },
          ] },
          { name: 'Language specific', destinations: [
            { name: 'Java', url: '', next: [{ name: 'Artifactory', url: '' }] },
            { name: 'C++', url: '', next: [{ name: 'SonarQube', url: '' }] },
            { name: 'Python', url: '', next: [{ name: 'PyPI mirror', url: '' }] },
          ] },
          { name: 'Infrastructure', destinations: [
            { name: 'Deployment', url: '', next: [{ name: 'AWS account', url: '' }] },
            { name: 'Terraform', url: '' },
            { name: 'Kubernetes', url: '' },
          ] },
          { name: 'Corporate knowledge', destinations: [
            { name: 'Confluence', url: '' },
            { name: 'Onboarding', url: '' },
            { name: 'Security & policy', url: '' },
          ] },
        ],
      },
```

- [ ] **Step 5: Run the tests to check they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_content.py -q`
Expected: all PASS.

- [ ] **Step 6: Update the spec's limits and colours**

In `docs/superpowers/specs/2026-09-25-kb-trail-map-design.md`:

1. In §3.1, replace the colour line with: `- **Colours.** Each trail's colour comes from a fixed palette, in the trail's order: blue `#2F6FA3`, red `#B8452A`, green `#3E7D4C`, purple `#74509C`, ochre `#A0721A`.`
2. In §3.1, replace the limits sub-bullet with: `  - Only the first 5 trails, the first 5 destinations on a trail, the first 2 `next` stops per destination, and 25 stops in all are kept. Every named stop counts toward the 25, third-level ones included; the draft tree has 21. `next` inside `next` is ignored. (The prototype showed six trails, or more than about 25 stops, no longer lay out cleanly.)`
3. In §5.1's slot table, delete the `| 6 | …` row.

- [ ] **Step 7: Commit**

```bash
git add public/js/content.js public/tour-content.js tests/test_content.py docs/superpowers/specs/2026-09-25-kb-trail-map-design.md
git commit -F - <<'EOF'
feat: the knowledge-base trail map in the content model

The knowledge stop gains a map: five trails from blazeAhead, 21 stops,
some leading on to a third level. tour-content.js carries it as owner
copy; content.js trims it to 5 trails, 5 destinations a trail, 2 onward
stops and 25 in all, keeps only http(s) links, and falls back to the
shipped map when the owner's is unusable.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
EOF
```

---

### Task 2: The map module — layout and painters (`kbmap.js`)

**Files:**
- Create: `public/js/kbmap.js`
- Modify: `tests/blank.html` (load the site fonts, so layout tests measure real text)
- Modify: `tests/test_package.py` (`MUST_SHIP` gains `kbmap`)
- Modify: `docs/superpowers/specs/2026-09-25-kb-trail-map-design.md` (§5 describes the layout as built)
- Test: `tests/test_kbmap.py` (new)

**Interfaces:**
- Consumes: `DEFAULT_TOUR.stops[2].map` from Task 1 (in tests only).
- Produces (`public/js/kbmap.js`):
  - `BOARD = { w: 1380, h: 880, margin: 30 }`, `TRAIL_COLORS` (5 hex strings), `PAPER = '#DCCDA6'`, `MIN_SCALE = 0.6`.
  - `shortName(name) → string`.
  - `layoutMap(map, measure) → laid`:
    - `measure(text, cssFont) → width in board units`;
    - `laid = { scale, crowded, clashes, centre: {name,x,y,w,h,size}, here: {x,y,r,tx,ty,size}, trails: [{ name, color, x, y, w, h, size, destinations: [node] }], boxes: [[x0,y0,x1,y1]] }`;
    - each `node = { key, name, url, x, y, r, size, from: [x,y], label: {text,x,y,anchor,box,side,clash}, next: [node] }` (a `next` node has no `next`).
  - `drawMap(painter, laid, { focus = null, links = false, paper = true })`. `focus` is a trail index or `null`.
  - `svgPainter(document) → { svg, line, circle, rect, text, link }`.
  - `canvasPainter(ctx, scale) → { line, circle, rect, text, link }`.
  - `canvasMeasure(document) → measure`.
  - `loadMapFonts(document) → Promise<void>`. It never rejects.
  - `quadMatrix3d(w, h, quad) → 'matrix3d(...)'`. `quad` is 4 `[x, y]` points, clockwise from top-left.

- [ ] **Step 1: Load the fonts in the test harness page**

Replace `tests/blank.html` with:

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Test harness</title>
  <style>
    @font-face { font-family: 'Fraunces'; src: url('/public/fonts/Fraunces.woff2') format('woff2'); font-weight: 300 700; font-style: normal; }
    @font-face { font-family: 'Fraunces'; src: url('/public/fonts/Fraunces-Italic.woff2') format('woff2'); font-weight: 300 700; font-style: italic; }
    @font-face { font-family: 'Figtree'; src: url('/public/fonts/Figtree.woff2') format('woff2'); font-weight: 400 700; font-style: normal; }
  </style>
  <script type="importmap">
    { "imports": { "three": "/public/vendor/three/build/three.module.min.js", "three/addons/": "/public/vendor/three/examples/jsm/" } }
  </script>
</head>
<body></body>
</html>
```

- [ ] **Step 2: Write the failing tests** (`tests/test_kbmap.py`)

```python
import pytest


def kb(js, body):
    return js("""const K = await import('/public/js/kbmap.js');
      const C = await import('/public/js/content.js');
      await K.loadMapFonts(document);
      const measure = K.canvasMeasure(document);
      const draft = () => structuredClone(C.DEFAULT_TOUR.stops[2].map);
      const names = ['Build caches', 'Secrets', 'Code review', 'Design docs', 'Service catalog', 'Runbooks',
                     'Mirrors', 'On-call guide'];
      let k = 0;
      const nm = () => names[k++ % names.length];
      const stop = (name, next = []) => ({ name, url: '', next: next.map((n) => ({ name: n, url: '' })) });
      const tree = (trails, dests, spur) => ({ centre: 'blazeAhead', trails: Array.from({ length: trails }, (_, i) => ({
        name: `Trail number ${i + 1}`,
        destinations: Array.from({ length: dests }, (_, j) => (spur && j === 1 ? stop(nm(), [nm()]) : stop(nm()))) })) });
      // no box off the board's margin, no two boxes touching (labels, pills, dots), and the type scale reached
      const clean = (laid) => {
        const b = laid.boxes; const M = K.BOARD.margin; let hits = 0;
        const out = b.filter((x) => x[0] < M || x[1] < M || x[2] > K.BOARD.w - M || x[3] > K.BOARD.h - M).length;
        for (let i = 0; i < b.length; i++) for (let j = i + 1; j < b.length; j++)
          if (b[i][0] < b[j][2] && b[j][0] < b[i][2] && b[i][1] < b[j][3] && b[j][1] < b[i][3]) hits++;
        return [out, hits, laid.crowded, Math.round(laid.scale * 1000) / 1000];
      };
      """ + body)


def test_the_draft_map_fits_at_full_size(js):
    out, hits, crowded, scale = kb(js, "return clean(K.layoutMap(draft(), measure));")
    assert (out, hits, crowded) == (0, 0, False)
    assert scale >= 0.9


@pytest.mark.parametrize("build, floor", [
    ("k = 0; return clean(K.layoutMap(tree(5, 3, true), measure));", 0.85),       # 20 stops, a spur on every trail
    ("k = 3; return clean(K.layoutMap(tree(5, 5, false), measure));", 0.6),       # 25 stops, five on every trail
    ("const m = draft(); m.trails = m.trails.slice(0, 4); return clean(K.layoutMap(m, measure));", 0.6),
    ("return clean(K.layoutMap({ centre: 'x', trails: [{ name: 'Only', destinations: [stop('One')] }] }, measure));", 0.9),
])
def test_fuller_and_smaller_maps_still_fit(js, build, floor):
    out, hits, crowded, scale = kb(js, build)
    assert (out, hits, crowded) == (0, 0, False)
    assert scale >= floor


def test_lighting_a_trail_fades_the_others(js):
    lines = kb(js, """const laid = K.layoutMap(draft(), measure);
      const calls = [];
      const rec = new Proxy({}, { get: (_, kind) => (...a) => { if (kind === 'link') a[2](); else calls.push([kind, a[a.length - 1]]); } });
      K.drawMap(rec, laid, { focus: 2 });
      return calls.filter(([kind]) => kind === 'line').map(([, o]) => [o.color, o.alpha, Boolean(o.glow)]);""")
    assert lines
    for color, alpha, glow in lines:
        if color == "#3E7D4C":
            assert alpha == 1 and glow
        else:
            assert alpha == 0.26 and not glow


def test_the_svg_map_links_only_when_asked_and_keeps_names_as_text(js):
    r = kb(js, """const m = draft();
      m.trails[0].destinations[0] = { name: '<b>R&D</b>', url: 'https://x.example.com/', next: [] };
      const laid = K.layoutMap(m, measure);
      const plain = K.svgPainter(document); K.drawMap(plain, laid);
      const linked = K.svgPainter(document); K.drawMap(linked, laid, { links: true });
      const a = linked.svg.querySelector('a');
      return [plain.svg.querySelectorAll('a').length, linked.svg.querySelectorAll('a').length, a.getAttribute('href'),
              a.getAttribute('target'), a.getAttribute('rel'), linked.svg.querySelectorAll('b').length,
              [...linked.svg.querySelectorAll('text')].some((t) => t.textContent === '<b>R&D</b>'),
              plain.svg.getAttribute('viewBox'), plain.svg.querySelectorAll('circle').length];""")
    assert r == [0, 1, "https://x.example.com/", "_blank", "noopener noreferrer", 0, True, "0 0 1380 880", 22]


def test_the_canvas_painter_draws_paper_and_pills(js):
    paper, pill = kb(js, """const laid = K.layoutMap(draft(), measure);
      const c = document.createElement('canvas'); c.width = 1380; c.height = 880;
      const g = c.getContext('2d');
      K.drawMap(K.canvasPainter(g, 1), laid);
      const px = (x, y) => [...g.getImageData(Math.round(x), Math.round(y), 1, 1).data].slice(0, 3);
      return [px(5, 5), px(laid.centre.x - laid.centre.w / 2 + 12, laid.centre.y)];""")
    assert paper == [0xDC, 0xCD, 0xA6]
    assert pill == [0xE8, 0x8E, 0x1F]


def test_quad_matrix_lays_the_board_on_its_four_corners(js):
    got = kb(js, """const quad = [[512, 210], [890, 222], [884, 470], [505, 462]];
      const m = new DOMMatrix(K.quadMatrix3d(1380, 880, quad));
      const at = (x, y) => { const p = m.transformPoint(new DOMPoint(x, y, 0, 1)); return [p.x / p.w, p.y / p.w]; };
      return [at(0, 0), at(1380, 0), at(1380, 880), at(0, 880)];""")
    want = [[512, 210], [890, 222], [884, 470], [505, 462]]
    for (gx, gy), (wx, wy) in zip(got, want):
        assert abs(gx - wx) < 1e-6 and abs(gy - wy) < 1e-6, got


def test_long_names_are_cut_on_the_map(js):
    r = kb(js, "return [K.shortName('A'.repeat(40)), K.shortName('Short')];")
    assert len(r[0]) == 32 and r[0].endswith("…") and r[1] == "Short"
```

- [ ] **Step 3: Run the tests to check they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_kbmap.py -q`
Expected: FAIL (the module `/public/js/kbmap.js` doesn't exist).

- [ ] **Step 4: Write `public/js/kbmap.js`**

```js
// The knowledge-base trail map. layoutMap() places the tree from tour-content.js on the kiosk's board, and drawMap()
// draws it through a painter: svgPainter() for the page (the unfolded map, and the map laid over the still image) or
// canvasPainter() for the 3D kiosk's texture. Board units are the real board's millimetres: 1380 x 880.

export const BOARD = { w: 1380, h: 880, margin: 30 };
export const TRAIL_COLORS = ['#2F6FA3', '#B8452A', '#3E7D4C', '#74509C', '#A0721A'];
export const PAPER = '#DCCDA6';      // the Blender paper's albedo, so the live board and the still match
export const MIN_SCALE = 0.6;
const INK = '#3B2A1C';
const CENTRE_FILL = '#E88E1F';
const PIN = '#C0392B';
const HERE_INK = '#7A2A20';
const RIM = '#F4EBD3';
const FADE = 0.26;                   // the other trails, while one is lit
const SIZES = { hub: 26, dest: 27, next: 25, centre: 30, here: 24 };
const NAME_FONT = 'Fraunces, Georgia, serif';
const PILL_FONT = 'Figtree, system-ui, sans-serif';
const CENTRE = [690, 455];
// where each hub stands (fractions of the board) and which way its destinations fan out (degrees, y down)
const SLOT = { top: [0.5, 0.29, 270], upperLeft: [0.27, 0.34, 205], upperRight: [0.73, 0.34, 335],
  lowerRight: [0.73, 0.73, 25], lowerLeft: [0.27, 0.73, 155] };
const SLOT_ORDER = ['top', 'upperLeft', 'upperRight', 'lowerRight', 'lowerLeft'];
const FAN_REACH = 115;      // from a hub pill's edge out to its destinations
const STAGGER = 55;         // with five destinations, every other one stands this much further out
const STEP_OUT = 45;        // a destination whose label clashes steps out this far (twice at most) before type shrinks
const NEXT_REACH = 130;     // from a destination out to its onward stops
const TURNS = [0, -30, 30, -60, 60, -90, 90];   // how an onward stop bends away from the board's edge (degrees)
const DOT = { dest: 12, next: 9 };
const GAP = 7;              // clear space kept around every label
const DEG = Math.PI / 180;
const D = Math.SQRT1_2;
// where a label may sit around its dot, and the direction each place faces
const SIDES = { above: [0, -1], below: [0, 1], left: [-1, 0], right: [1, 0], aboveRight: [D, -D], aboveLeft: [-D, -D],
  belowRight: [D, D], belowLeft: [-D, D] };

const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));
const overlap = (a, b) => a[0] < b[2] && b[0] < a[2] && a[1] < b[3] && b[1] < a[3];
const onBoard = (b) => b[0] >= BOARD.margin && b[1] >= BOARD.margin && b[2] <= BOARD.w - BOARD.margin
  && b[3] <= BOARD.h - BOARD.margin;

export const shortName = (name) => (name.length > 32 ? `${name.slice(0, 31).trimEnd()}…` : name);

function slotsFor(n) {
  if (n === 4) return ['upperLeft', 'upperRight', 'lowerRight', 'lowerLeft'];
  return SLOT_ORDER.slice(0, n);
}

// does the segment [x1, y1, x2, y2] cross the box? (Liang-Barsky)
function crosses(s, b) {
  let t0 = 0;
  let t1 = 1;
  const dx = s[2] - s[0];
  const dy = s[3] - s[1];
  for (const [p, q] of [[-dx, s[0] - b[0]], [dx, b[2] - s[0]], [-dy, s[1] - b[1]], [dy, b[3] - s[1]]]) {
    if (p === 0) {
      if (q < 0) return false;
    } else {
      const r = q / p;
      if (p < 0) t0 = Math.max(t0, r);
      else t1 = Math.min(t1, r);
      if (t0 > t1) return false;
    }
  }
  return true;
}

// do two segments cross?
function cut(a, b) {
  const side = (p, q, r) => Math.sign((q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0]));
  const a1 = [a[0], a[1]];
  const a2 = [a[2], a[3]];
  const b1 = [b[0], b[1]];
  const b2 = [b[2], b[3]];
  return side(a1, a2, b1) * side(a1, a2, b2) < 0 && side(b1, b2, a1) * side(b1, b2, a2) < 0;
}

// distance from a pill's centre to its edge along a direction
function edge(w, h, ang) {
  const c = Math.abs(Math.cos(ang));
  const s = Math.abs(Math.sin(ang));
  return Math.min(c > 1e-6 ? w / 2 / c : Infinity, s > 1e-6 ? h / 2 / s : Infinity);
}

// a label's box and text anchor, for one of the SIDES around a dot of radius r
function labelBox(side, x, y, r, tw, size) {
  const a = size * 0.78;
  const d = size * 0.24;
  if (side === 'above') return { box: [x - tw / 2, y - r - 6 - a - d, x + tw / 2, y - r - 6], tx: x, ty: y - r - 6 - d, anchor: 'middle' };
  if (side === 'below') return { box: [x - tw / 2, y + r + 6, x + tw / 2, y + r + 6 + a + d], tx: x, ty: y + r + 6 + a, anchor: 'middle' };
  if (side === 'left') return { box: [x - r - 9 - tw, y - (a + d) / 2, x - r - 9, y + (a + d) / 2], tx: x - r - 9, ty: y - (a + d) / 2 + a, anchor: 'end' };
  if (side === 'right') return { box: [x + r + 9, y - (a + d) / 2, x + r + 9 + tw, y + (a + d) / 2], tx: x + r + 9, ty: y - (a + d) / 2 + a, anchor: 'start' };
  const k = r + 4;          // diagonal: the label's near corner sits just clear of the dot
  const right = side.endsWith('Right');
  const x0 = right ? x + k : x - k - tw;
  const y0 = side.startsWith('above') ? y - k - a - d : y + k;
  return { box: [x0, y0, x0 + tw, y0 + a + d], tx: right ? x0 : x0 + tw, ty: y0 + a, anchor: right ? 'start' : 'end' };
}

function place(map, measure, scale, skips) {
  const sz = (k) => Math.round(SIZES[k] * scale * 10) / 10;
  const nameFont = (k) => `600 ${sz(k)}px ${NAME_FONT}`;
  const fixed = [];         // boxes nothing may overlap: pills, dots and the labels placed so far
  const segments = [];      // every line on the map
  const cw = measure(map.centre, nameFont('centre')) + 52;
  const centre = { name: map.centre, x: CENTRE[0], y: CENTRE[1], w: cw, h: 60 * Math.max(scale, 0.8), size: sz('centre') };
  fixed.push([centre.x - cw / 2, centre.y - centre.h / 2, centre.x + cw / 2, centre.y + centre.h / 2]);
  const here = { x: CENTRE[0], y: CENTRE[1] + 58, r: 10, tx: CENTRE[0], ty: CENTRE[1] + 98, size: sz('here') };
  const hereW = measure('you are here', `italic 500 ${here.size}px ${NAME_FONT}`);
  fixed.push([here.x - here.r, here.y - here.r, here.x + here.r, here.y + here.r]);
  fixed.push([here.tx - hereW / 2, here.ty - here.size * 0.78, here.tx + hereW / 2, here.ty + here.size * 0.24]);
  const slots = slotsFor(map.trails.length);
  const trails = map.trails.map((t, i) => {
    const [fx, fy, facing] = SLOT[slots[i]];
    const x = fx * BOARD.w;
    const y = fy * BOARD.h;
    const w = measure(t.name, `700 ${sz('hub')}px ${PILL_FONT}`) + 62;
    const h = 48 * Math.max(scale, 0.8);
    fixed.push([x - w / 2, y - h / 2, x + w / 2, y + h / 2]);
    segments.push([CENTRE[0], CENTRE[1], x, y]);
    const n = t.destinations.length;
    const spread = Math.min(130, 40 * (n - 1)) * DEG;
    const destinations = t.destinations.map((d, j) => {
      const key = `${i}.${j}`;
      const ang = n > 1 ? facing * DEG - spread / 2 + (spread * j) / (n - 1) : facing * DEG;
      const reach = edge(w, h, ang) + FAN_REACH + (n >= 5 && j % 2 ? STAGGER : 0)
        + STEP_OUT * Math.min(2, skips.get(key) || 0);
      // keep the dot far enough in that its label fits centred above or below it
      const half = measure(shortName(d.name), nameFont('dest')) / 2 + 4;
      const dx = clamp(x + Math.cos(ang) * reach, BOARD.margin + half, BOARD.w - BOARD.margin - half);
      const dy = clamp(y + Math.sin(ang) * reach, BOARD.margin + 50, BOARD.h - BOARD.margin - 50);
      const dotBox = [dx - DOT.dest, dy - DOT.dest, dx + DOT.dest, dy + DOT.dest];
      fixed.push(dotBox);
      segments.push([x, y, dx, dy]);
      const own = Math.atan2(dy - y, dx - x);
      const m = d.next.length;
      const nspread = 40 * (m - 1) * DEG;
      const next = d.next.map((e, k) => {
        const nkey = `${key}.${k}`;
        const base = m > 1 ? own - nspread / 2 + (nspread * k) / (m - 1) : own;
        const tw = measure(shortName(e.name), nameFont('next'));
        let skip = skips.get(nkey) || 0;
        let spot = null;
        // straight on if there's room; otherwise bend away from the board's edge and from the other lines
        for (const turn of TURNS) {
          const a = base + turn * DEG;
          const px = dx + Math.cos(a) * NEXT_REACH;
          const py = dy + Math.sin(a) * NEXT_REACH;
          const spur = [dx, dy, px, py];
          const fits = onBoard([px - DOT.next, py - DOT.next, px + DOT.next, py + DOT.next])
            // its label must fit on a side that doesn't face back along the spur (that would hide the spur)
            && Object.entries(SIDES).some(([side, v]) => v[0] * Math.cos(a) + v[1] * Math.sin(a) >= 0
              && onBoard(labelBox(side, px, py, DOT.next, tw, sz('next')).box))
            && !segments.some((o) => !(o[2] === dx && o[3] === dy) && !(o[0] === dx && o[1] === dy) && cut(o, spur));
          if (fits && skip > 0) {
            skip -= 1;
          } else if (fits) {
            spot = [px, py];
            break;
          }
        }
        if (!spot) {
          spot = [clamp(dx + Math.cos(base) * NEXT_REACH, BOARD.margin + 20, BOARD.w - BOARD.margin - 20),
            clamp(dy + Math.sin(base) * NEXT_REACH, BOARD.margin + 20, BOARD.h - BOARD.margin - 20)];
        }
        const [ex, ey] = spot;
        const nextBox = [ex - DOT.next, ey - DOT.next, ex + DOT.next, ey + DOT.next];
        fixed.push(nextBox);
        segments.push([dx, dy, ex, ey]);
        return { key: nkey, name: e.name, url: e.url, x: ex, y: ey, r: DOT.next, dotBox: nextBox, size: sz('next'),
          from: [dx, dy] };
      });
      return { key, name: d.name, url: d.url, x: dx, y: dy, r: DOT.dest, dotBox, size: sz('dest'), from: [x, y], next };
    });
    return { name: t.name, color: TRAIL_COLORS[i], x, y, w, h, size: sz('hub'), destinations };
  });
  // labels, one at a time: each takes the free place that best faces away from where its line comes in
  let clashes = 0;
  for (const node of trails.flatMap((t) => t.destinations.flatMap((d) => [d, ...d.next]))) {
    const text = shortName(node.name);
    const tw = measure(text, `600 ${node.size}px ${NAME_FONT}`);
    const ox = node.x - node.from[0];
    const oy = node.y - node.from[1];
    const len = Math.hypot(ox, oy) || 1;
    const facing = ([, v]) => (v[0] * ox + v[1] * oy) / len;
    // hiding the node's own line (in from its parent, or out to its own stops) blurs what leads where
    const ownLine = (sg) => (sg[2] === node.x && sg[3] === node.y) || (sg[0] === node.x && sg[1] === node.y);
    let best = null;
    Object.entries(SIDES).sort((a, b) => facing(b) - facing(a)).forEach(([side], rank) => {
      const lb = labelBox(side, node.x, node.y, node.r, tw, node.size);
      const room = [lb.box[0] - GAP, lb.box[1] - GAP, lb.box[2] + GAP, lb.box[3] + GAP];
      const hard = fixed.filter((b) => b !== node.dotBox && overlap(b, room)).length + (onBoard(lb.box) ? 0 : 1);
      const soft = segments.filter((sg) => crosses(sg, lb.box)).reduce((sum, sg) => sum + (ownLine(sg) ? 40 : 4), 0);
      const score = hard * 100 + soft + rank;
      if (!best || score < best.score) best = { ...lb, side, hard, score };
    });
    clashes += best.hard;
    node.label = { text, x: best.tx, y: best.ty, anchor: best.anchor, box: best.box, side: best.side, clash: best.hard > 0 };
    fixed.push(best.box);
  }
  for (const node of trails.flatMap((t) => t.destinations.flatMap((d) => [d, ...d.next]))) delete node.dotBox;
  return { scale, clashes, centre, here, trails, boxes: fixed };
}

// Lay out at full size if it fits. A stop whose label clashes steps out (a destination) or bends (an onward stop)
// first; only then does all the lettering shrink, 5 % at a time, down to MIN_SCALE. `crowded` means even that
// didn't clear every clash.
export function layoutMap(map, measure) {
  let laid = null;
  for (let scale = 1; scale >= MIN_SCALE; scale *= 0.95) {
    const skips = new Map();
    for (let round = 0; round < 6; round += 1) {
      laid = place(map, measure, scale, skips);
      if (!laid.clashes) return { ...laid, crowded: false };
      const stuck = laid.trails.flatMap((t) => t.destinations.flatMap((d) => [d, ...d.next])).filter((s) => s.label.clash);
      for (const s of stuck) skips.set(s.key, (skips.get(s.key) || 0) + 1);
    }
  }
  return { ...laid, crowded: true };
}

// ---- painting

export function drawMap(p, laid, { focus = null, links = false, paper = true } = {}) {
  if (paper) p.rect(0, 0, BOARD.w, BOARD.h, 0, { fill: PAPER });
  const fade = (i) => (focus === null || focus === i ? 1 : FADE);
  const glow = (i, color) => (focus === i ? color : null);
  laid.trails.forEach((t, i) => {
    p.line(laid.centre.x, laid.centre.y, t.x, t.y, { color: t.color, width: 9, alpha: fade(i), glow: glow(i, t.color) });
    for (const d of t.destinations) {
      p.line(t.x, t.y, d.x, d.y, { color: t.color, width: 5.5, alpha: fade(i), glow: glow(i, t.color) });
      for (const e of d.next) {
        p.line(d.x, d.y, e.x, e.y, { color: t.color, width: 4, dash: [11, 8], alpha: fade(i), glow: glow(i, t.color) });
      }
    }
  });
  laid.trails.forEach((t, i) => {
    for (const node of t.destinations.flatMap((d) => [d, ...d.next])) {
      const paint = () => {
        const b = node.label.box;
        // a backing the colour of the paper (white when multiplied onto a still) hides any line running under the name
        p.rect(b[0] - 4, b[1] - 2, b[2] - b[0] + 8, b[3] - b[1] + 4, 4, { fill: paper ? PAPER : '#FFFFFF' });
        p.circle(node.x, node.y, node.r, { fill: t.color, stroke: RIM, width: 3.5, alpha: fade(i) });
        p.text(node.label.text, node.label.x, node.label.y, { font: NAME_FONT, size: node.size, weight: 600, color: INK,
          anchor: node.label.anchor, alpha: fade(i), underline: links && Boolean(node.url) });
      };
      if (links && node.url) p.link(node.url, node.name, paint);
      else paint();
    }
  });
  laid.trails.forEach((t, i) => {
    p.rect(t.x - t.w / 2, t.y - t.h / 2, t.w, t.h, t.h / 2, { fill: t.color, stroke: RIM, width: 3, alpha: fade(i),
      glow: glow(i, t.color) });
    p.rect(t.x - t.w / 2 + 16, t.y - t.h / 4, 11, t.h / 2, 2, { fill: '#FFFFFF', alpha: fade(i) * 0.9 });
    p.text(t.name, t.x + 12, t.y + t.size * 0.35, { font: PILL_FONT, size: t.size, weight: 700, color: '#FFFFFF',
      anchor: 'middle', alpha: fade(i) });
  });
  const c = laid.centre;
  p.rect(c.x - c.w / 2, c.y - c.h / 2, c.w, c.h, c.h / 2, { fill: CENTRE_FILL, stroke: RIM, width: 3.5 });
  p.text(c.name, c.x, c.y + c.size * 0.34, { font: NAME_FONT, size: c.size, weight: 600, color: '#1B1204', anchor: 'middle' });
  const h = laid.here;
  p.circle(h.x, h.y, h.r, { fill: PIN, stroke: RIM, width: 3 });
  p.text('you are here', h.tx, h.ty, { font: NAME_FONT, size: h.size, weight: 500, style: 'italic', color: HERE_INK,
    anchor: 'middle' });
}

const NS = 'http://www.w3.org/2000/svg';
let svgCount = 0;      // keeps each SVG's filter ids unique on a page that shows two maps

export function svgPainter(doc) {
  svgCount += 1;
  const prefix = `kb${svgCount}`;
  const svg = doc.createElementNS(NS, 'svg');
  svg.setAttribute('viewBox', `0 0 ${BOARD.w} ${BOARD.h}`);
  const defs = doc.createElementNS(NS, 'defs');
  svg.append(defs);
  const filters = new Map();
  let parent = svg;
  const el = (tag, attrs) => {
    const e = doc.createElementNS(NS, tag);
    for (const [k, v] of Object.entries(attrs)) if (v !== null && v !== undefined) e.setAttribute(k, v);
    parent.append(e);
    return e;
  };
  const glowUrl = (color) => {
    if (!color) return null;
    if (!filters.has(color)) {
      const id = `${prefix}-glow-${filters.size}`;
      const f = doc.createElementNS(NS, 'filter');
      for (const [k, v] of Object.entries({ id, x: '-20%', y: '-20%', width: '140%', height: '140%' })) f.setAttribute(k, v);
      const s = doc.createElementNS(NS, 'feDropShadow');
      for (const [k, v] of Object.entries({ dx: 0, dy: 0, stdDeviation: 7, 'flood-color': color, 'flood-opacity': 0.6 })) {
        s.setAttribute(k, v);
      }
      f.append(s);
      defs.append(f);
      filters.set(color, id);
    }
    return `url(#${filters.get(color)})`;
  };
  return {
    svg,
    line(x1, y1, x2, y2, o) {
      el('line', { x1, y1, x2, y2, stroke: o.color, 'stroke-width': o.width, 'stroke-linecap': 'round',
        'stroke-dasharray': o.dash ? o.dash.join(' ') : null, opacity: o.alpha ?? 1, filter: glowUrl(o.glow) });
    },
    circle(cx, cy, r, o) {
      el('circle', { cx, cy, r, fill: o.fill, stroke: o.stroke, 'stroke-width': o.width, opacity: o.alpha ?? 1 });
    },
    rect(x, y, w, h, r, o) {
      el('rect', { x, y, width: w, height: h, rx: r, fill: o.fill, stroke: o.stroke, 'stroke-width': o.width,
        opacity: o.alpha ?? 1, filter: glowUrl(o.glow) });
    },
    text(str, x, y, o) {
      const t = el('text', { x, y, 'font-family': o.font, 'font-size': o.size, 'font-weight': o.weight,
        'font-style': o.style || null, fill: o.color, 'text-anchor': o.anchor, opacity: o.alpha ?? 1,
        'text-decoration': o.underline ? 'underline' : null });
      t.textContent = str;
    },
    link(url, title, paint) {
      const a = el('a', { href: url, target: '_blank', rel: 'noopener noreferrer', 'aria-label': title });
      const outer = parent;
      parent = a;
      paint();
      parent = outer;
    },
  };
}

export function canvasPainter(ctx, scale = 1) {
  const styled = (o, fn) => {
    ctx.save();
    ctx.setTransform(scale, 0, 0, scale, 0, 0);
    ctx.globalAlpha = o.alpha ?? 1;
    if (o.glow) {
      ctx.shadowColor = o.glow;
      ctx.shadowBlur = 14 * scale;     // shadows ignore the transform
    }
    fn();
    ctx.restore();
  };
  const outline = (o) => {
    if (!o.stroke) return;
    ctx.shadowBlur = 0;
    ctx.strokeStyle = o.stroke;
    ctx.lineWidth = o.width;
    ctx.stroke();
  };
  return {
    line(x1, y1, x2, y2, o) {
      styled(o, () => {
        ctx.strokeStyle = o.color;
        ctx.lineWidth = o.width;
        ctx.lineCap = 'round';
        ctx.setLineDash(o.dash || []);
        ctx.beginPath();
        ctx.moveTo(x1, y1);
        ctx.lineTo(x2, y2);
        ctx.stroke();
      });
    },
    circle(cx, cy, r, o) {
      styled(o, () => {
        ctx.beginPath();
        ctx.arc(cx, cy, r, 0, Math.PI * 2);
        ctx.fillStyle = o.fill;
        ctx.fill();
        outline(o);
      });
    },
    rect(x, y, w, h, r, o) {
      styled(o, () => {
        ctx.beginPath();
        ctx.roundRect(x, y, w, h, r);
        ctx.fillStyle = o.fill;
        ctx.fill();
        outline(o);
      });
    },
    text(str, x, y, o) {
      styled(o, () => {
        ctx.font = `${o.style || 'normal'} ${o.weight} ${o.size}px ${o.font}`;
        ctx.fillStyle = o.color;
        ctx.textAlign = { middle: 'center', end: 'right', start: 'left' }[o.anchor] || 'left';
        ctx.textBaseline = 'alphabetic';
        ctx.fillText(str, x, y);
      });
    },
    link(url, title, paint) {
      paint();
    },
  };
}

export function canvasMeasure(doc) {
  const ctx = doc.createElement('canvas').getContext('2d');
  return (text, font) => {
    ctx.font = font;
    return ctx.measureText(text).width;
  };
}

// The map's fonts, before anything is measured. Never fails: without them the map measures and draws with whichever
// font did render, and still fits.
export async function loadMapFonts(doc) {
  if (!doc.fonts || typeof doc.fonts.load !== 'function') return;
  try {
    await Promise.all(['600 27px Fraunces', 'italic 500 24px Fraunces', '700 26px Figtree'].map((f) => doc.fonts.load(f)));
  } catch {
    // measured with the fallback fonts instead
  }
}

// The CSS transform that lays a w x h box (origin at its top-left) onto four points, clockwise from its top-left
// corner: the 8 unknowns of the projective map, by Gauss-Jordan elimination.
export function quadMatrix3d(w, h, quad) {
  const src = [[0, 0], [w, 0], [w, h], [0, h]];
  const rows = [];
  for (let i = 0; i < 4; i += 1) {
    const [x, y] = src[i];
    const [u, v] = quad[i];
    rows.push([x, y, 1, 0, 0, 0, -u * x, -u * y, u]);
    rows.push([0, 0, 0, x, y, 1, -v * x, -v * y, v]);
  }
  for (let c = 0; c < 8; c += 1) {
    let p = c;
    for (let r = c + 1; r < 8; r += 1) if (Math.abs(rows[r][c]) > Math.abs(rows[p][c])) p = r;
    [rows[c], rows[p]] = [rows[p], rows[c]];
    for (let r = 0; r < 8; r += 1) {
      if (r === c) continue;
      const f = rows[r][c] / rows[c][c];
      for (let k = c; k < 9; k += 1) rows[r][k] -= f * rows[c][k];
    }
  }
  const [a, b, c, d, e, f, g, k] = rows.map((r, i) => r[8] / r[i]);
  return `matrix3d(${[a, d, 0, g, b, e, 0, k, 0, 0, 1, 0, c, f, 0, 1].map((n) => Number(n.toFixed(10))).join(',')})`;
}
```

- [ ] **Step 5: Run the tests to check they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_kbmap.py tests/test_harness.py -q`
Expected: all PASS. If a layout test fails, compare with the prototype (`.superpowers/brainstorm/kb-map/proto/`, served from the repo root, `proto.html`), which prints the same checks. Don't loosen a floor to make it pass.

- [ ] **Step 6: Ship the module in the zip**

In `tests/test_package.py`, add `"kbmap"` to the `public/js/{m}.js` tuple in `MUST_SHIP`.

Run: `.venv/Scripts/python.exe -m pytest tests/test_package.py -q`
Expected: PASS. The packager ships all of `public/`.

- [ ] **Step 7: Bring the spec's §5 in line with what was built**

In `docs/superpowers/specs/2026-09-25-kb-trail-map-design.md`, replace the bullets from `- **Destinations.**` through the paragraph ending "…the invariants tested in section 8." with:

```markdown
- **Destinations.** Each hub's destinations fan out in a fixed direction per slot: top 270°, upper-left 205°, upper-right 335°, lower-right 25°, lower-left 155° (screen degrees, y down). They are spaced evenly across min(130°, 40° × (n − 1)), 115 units beyond the pill's edge. With five destinations, every other one stands 55 units further out. A dot is kept far enough in that its label fits centred above or below it.
- **Third-level stops.** They go 130 units beyond their destination, straight on if there's room. Otherwise they bend 30°, 60° or 90° either way, until the dot is on the board, the label fits on a side that doesn't face back along the spur, and the spur crosses no other line. They are drawn smaller, on dashed spurs.
- **Labels.** Each label goes in one of eight places around its dot: above, below, left, right, or a diagonal. It takes the place that best faces away from its incoming line, scoring:
  - overlaps with any pill, dot or earlier label (with a 7-unit gap), or running off the board: 100 each;
  - crossing its own line: 40;
  - crossing any other line: 4.

  Every label sits on a small paper-coloured backing, so a line running under it is hidden rather than struck through. (On the still overlay the backing is white, since it is multiplied.)
- **Fit pass.** While any label clashes, the layout tries again at the same size up to six times. Each time, every clashing destination steps out 45 units (twice at most), and every clashing third-level stop takes its next bend. Only then does all the lettering shrink by 5 %, down to 60 %. Starting sizes: hub 26, destination 27, third-level 25, centre 30 (units). The result reports the final `scale`, and `crowded` if clashes remain at 60 %. The page then logs a warning.
```

In §5.2, change `**Paper.** `paper` fills the board `#E3D2A9`.` to `**Paper.** `paper` fills the board `#DCCDA6`, the Blender paper's albedo, so the live board and the still match.`

In §8's layout bullet, replace the worst-case line with:

```markdown
  - For 20 stops with a spur on every trail, 25 stops with five on every trail, four trails, and a single stop: no overlaps, everything within the margin, and `scale` ≥ 0.85, 0.6, 0.6 and 0.9 respectively.
```

and replace `  - The SVG and canvas painters issue the same primitive sequence for one layout.` with `  - The SVG painter links only when asked and keeps names as text; the canvas painter paints the paper and the pills in their colours; `quadMatrix3d` lands the board's corners exactly.`

- [ ] **Step 8: Commit**

```bash
git add public/js/kbmap.js tests/test_kbmap.py tests/blank.html tests/test_package.py docs/superpowers/specs/2026-09-25-kb-trail-map-design.md
git commit -F - <<'EOF'
feat: kbmap.js lays out and draws the knowledge-base trail map

layoutMap places the tree on the 1380 x 880 board: hubs in fixed slots,
destinations fanned from each pill, onward stops that bend away from
the edge, and labels in the clearest of eight places around their dots.
Clashes are cured by stepping stops out first and shrinking type only
after, so the draft map lays out at full size. drawMap paints it through
an SVG or a canvas painter; quadMatrix3d fits the SVG onto the still.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
EOF
```

---

### Task 3: The card steps through the trails

**Files:**
- Modify: `public/js/content.js` (remove `cards`; add `pageCount`; `cardHtml` renders the overview and trail pages)
- Modify: `public/js/tour.js` (the pager uses `pageCount`; add `litTrail()` and `syncMap()`)
- Modify: `public/tour-content.js` (remove the knowledge `cards` block and its comment; new paragraph copy)
- Modify: `public/css/site.css` (trail chips and the trail panel, in place of `.kb-card`)
- Test: `tests/test_content.py`, `tests/test_pages.py`

**Interfaces:**
- Consumes: `stop.map` (Task 1); `TRAIL_COLORS` from `kbmap.js` (Task 2).
- Produces:
  - `pageCount(stop) → number`: trails + 1 for a stop with a map, otherwise 1.
  - `cardHtml(stop, page)`: page 0 is the overview, with `.kb-chip` items; page k is trail k−1, a `.kb-trail` section with `.kb-dests` links.
  - In `tour.js`: `litTrail() → number | null`, and `syncMap()`, which sets `document.body.dataset.kbTrail` to the lit trail index or `''`. Tasks 6 and 7 extend `syncMap()`.

- [ ] **Step 1: Write the failing tests**

In `tests/test_content.py`:

1. In `test_defaults_cover_four_stops_the_signs_and_help`, change `t.stops[2].cards.length` to `C.pageCount(t.stops[2])` and the final assert to `assert rocks >= 5 and cards == 6 and complete is True`.
2. Replace `test_card_html_escapes_copy_and_pages_through_knowledge_cards` with:

```python
def test_card_html_escapes_copy_and_pages_through_the_trails(js):
    r = content(js, """const s = {id: 'knowledge', title: '<b>x</b>', paragraphs: ['a & b'], points: [],
        map: {centre: 'c', trails: [
          {name: 'T<1>', destinations: [{name: 'R&D', url: 'https://x.example.com/?a=1&b="2"',
                                         next: [{name: 'Deep', url: ''}]}]},
          {name: 'Two', destinations: [{name: 'Plain', url: '', next: []}]}]}};
      return [C.pageCount(s), C.pageCount({title: 't', paragraphs: [], map: null}), C.cardHtml(s, 0),
              C.cardHtml(s, 1), C.cardHtml(s, 9)];""")
    pages, plain_pages, overview, first, clamped = r
    assert pages == 3 and plain_pages == 1
    assert "&lt;b&gt;x&lt;/b&gt;" in overview and "a &amp; b" in overview
    assert overview.count('class="kb-chip"') == 2 and "T&lt;1&gt;" in overview and "<a " not in overview
    assert 'href="https://x.example.com/?a=1&amp;b=&quot;2&quot;"' in first
    assert 'target="_blank"' in first and 'rel="noopener noreferrer"' in first
    assert ">R&amp;D</a>" in first and '<span class="kb-plain">Deep</span>' in first and "›" in first
    assert "Two" in clamped and '<span class="kb-plain">Plain</span>' in clamped
```

3. In `test_shipped_files_load_and_match_the_world`, replace `t.stops[2].cards.length` with `C.pageCount(t.stops[2])`, and change the expected list to `["object", ["Continuity", "Scaffolding", "Knowledge", "In Flight"], 6, 5, 5]`.

In `tests/test_pages.py`, replace `test_tour_deep_link_and_knowledge_cards` with:

```python
def test_tour_deep_link_steps_through_the_trails(make_page, browser_no_webgl, base_url):
    page, _ = open_page(make_page, base_url, "tour", browser_no_webgl, hash_="#knowledge")
    wait_stop(page, 2)
    assert page.locator("[data-card-count]").inner_text() == "1 of 6"
    assert page.locator("[data-card-body] .kb-chip").count() == 5
    assert page.eval_on_selector("body", "b => b.dataset.kbTrail") == ""
    page.locator("[data-card-next]").click()
    assert page.locator("[data-card-count]").inner_text() == "2 of 6"
    assert "Getting connected" in page.locator("[data-card-body] .kb-trail h3").inner_text()
    assert page.eval_on_selector("body", "b => b.dataset.kbTrail") == "0"
    for _ in range(4):
        page.locator("[data-card-next]").click()
    assert page.locator("[data-card-count]").inner_text() == "6 of 6"
    assert page.locator("[data-card-next]").is_disabled()
    page.locator("[data-card-prev]").click()
    assert page.eval_on_selector("body", "b => b.dataset.kbTrail") == "3"


def test_leaving_the_knowledge_stop_puts_the_trail_out(make_page, browser_no_webgl, base_url):
    page, _ = open_page(make_page, base_url, "tour", browser_no_webgl, hash_="#knowledge")
    wait_stop(page, 2)
    page.locator("[data-card-next]").click()
    page.keyboard.press("ArrowRight")
    wait_stop(page, 3)
    assert page.eval_on_selector("body", "b => b.dataset.kbTrail") == ""
    assert page.locator("[data-pager]").is_hidden()
```

- [ ] **Step 2: Run them to check they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_content.py tests/test_pages.py -q -k "trail or defaults or shipped"`
Expected: FAIL (`pageCount` is not a function; there are no `.kb-chip` elements).

- [ ] **Step 3: Implement the pages in `content.js`**

1. Add at the top, under the header comment: `import { TRAIL_COLORS } from './kbmap.js';`
2. Delete `const PLACEHOLDER = …` and the knowledge default's `cards: [...]`. Change the knowledge default's paragraph to: `paragraphs: ['Every internal tool, charted as trails from one trailhead. Step through the trails, or unfold the map and open a destination.'],`
3. In `normalizeStop`, delete `cards: [],` from the literal and the whole `const cards = …` block.
4. Replace the `cardHtml` comment and function with:

```js
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
```

- [ ] **Step 4: Update `tour.js`**

1. Change the import to `import { loadTour, cardHtml, pageCount } from './content.js';`
2. Replace `renderCard` with:

```js
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
    syncMap();
  }

  // ---- the knowledge-base map: the trail lit on the kiosk is the card's trail page, and none anywhere else
  function litTrail() {
    const stop = tour.stops[state.index];
    return stop && stop.map && state.cardIndex > 0 ? state.cardIndex - 1 : null;
  }

  function syncMap() {
    const trail = litTrail();
    doc.body.dataset.kbTrail = trail === null ? '' : String(trail);
  }
```

3. In `go()`, right after `setWalking(true);` inside the `for (;;)` loop, add `syncMap();` so the map goes dark as the walk leaves. `request()` has already reset `cardIndex`.
4. In the `els.next` click handler, change `state.nextCard(tour.stops[state.index].cards.length);` to `state.nextCard(pageCount(tour.stops[state.index]));`.

- [ ] **Step 5: Update `public/tour-content.js`**

In the Knowledge stop, delete the `// Each card is one page…` comment and the `cards: [...]` block. Replace its `paragraphs` with:

```js
      paragraphs: [
        'Every internal tool, charted as trails from one trailhead. Step through the trails, or unfold the map and '
        + 'open a destination.',
      ],
```

In the file's header comment, nothing mentions cards; leave it.

- [ ] **Step 6: Style the pages in `site.css`**

Replace the three `.tour-card .kb-card…` rules, and the two `.kb-card` rules inside `@media (max-height: 820px)`, with:

```css
.tour-card .kb-chips { display: flex; flex-wrap: wrap; gap: 8px; list-style: none; margin: 4px 0 8px; padding: 0; }
.tour-card .kb-chip { display: inline-flex; align-items: center; gap: 7px; padding: 5px 11px; border-radius: 999px; background: var(--panel-2); border: 1px solid var(--line); font-size: 14px; font-weight: 600; }
.tour-card .kb-blaze { display: inline-block; width: 9px; height: 15px; border-radius: 2px; background: var(--trail); flex: none; }
.tour-card .kb-trail { margin: 8px 0 6px; padding: 12px 14px; background: var(--panel-2); border-left: 4px solid var(--trail); border-radius: 8px; }
.tour-card .kb-trail h3 { display: flex; align-items: center; gap: 9px; margin: 0 0 6px; font-size: 17px; }
.tour-card .kb-trail h3 .kb-blaze { width: 12px; height: 20px; }
.tour-card .kb-dests { display: grid; grid-template-columns: 1fr 1fr; gap: 4px 18px; list-style: none; margin: 0; padding: 0; }
.tour-card .kb-dests a { color: var(--text); text-decoration: underline; text-decoration-color: rgba(238, 231, 216, 0.35); text-underline-offset: 3px; }
.tour-card .kb-dests a:hover { text-decoration-color: var(--amber); }
.tour-card .kb-plain { color: var(--muted); }
.tour-card .kb-then { color: var(--muted); margin: 0 6px; }
```

Inside `@media (max-height: 820px)`, add: `.tour-card .kb-trail { margin: 6px 0 4px; padding: 10px 12px; }`.

- [ ] **Step 7: Run the tests to check they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_content.py tests/test_pages.py tests/test_tour_state.py -q`
Expected: all PASS.

- [ ] **Step 8: Commit**

```bash
git add public/js/content.js public/js/tour.js public/tour-content.js public/css/site.css tests/test_content.py tests/test_pages.py
git commit -F - <<'EOF'
feat: the knowledge card steps through the trails

Stop 3's card has an overview of the five trails and then one page per
trail, its destinations as links ("Java > Artifactory"); unlinked names
show muted. The placeholder cards are gone. The page records the lit
trail on body[data-kb-trail] for the kiosk and the still to follow.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
EOF
```

---

### Task 4: The unfolded map (dialog)

**Files:**
- Modify: `public/tour/index.html` (Unfold button in the card footer; the `<dialog>`)
- Modify: `public/js/tour.js` (`mapLayout()`, `openSheet()`, the key guard, closing the sheet on navigation, button visibility)
- Modify: `public/css/site.css` (button and sheet)
- Test: `tests/test_pages.py`

**Interfaces:**
- Consumes: `layoutMap`, `drawMap`, `svgPainter`, `canvasMeasure`, `loadMapFonts` (Task 2); `syncMap`/`litTrail` and `renderCard` (Task 3).
- Produces, in `tour.js`:
  - `mapLayout() → Promise<laid | null>`: laid out once, then cached.
  - `openSheet(returnTo: Element)`: opens the dialog; focus goes back to `returnTo` on close.
- Markup: `[data-kb-unfold]`, `[data-kb-sheet]` (the dialog), `[data-kb-sheet-map]`, `[data-kb-close]`.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_pages.py`)

Add near the top of `tests/test_pages.py`:

```python
from pathlib import Path

TOUR_FILE = Path(__file__).resolve().parents[1] / "public" / "tour-content.js"


def with_tour_file(page, text):
    """Serve this text as tour-content.js, as if the owner had edited it."""
    page.route("**/tour-content.js", lambda route: route.fulfill(status=200, content_type="text/javascript", body=text))


def open_sheet(page):
    page.locator("[data-kb-unfold]").click()
    page.wait_for_function("() => document.querySelector('[data-kb-sheet]').open")
```

Then append:

```python
def test_the_map_unfolds_from_the_card_and_escape_only_closes_it(make_page, browser_no_webgl, base_url):
    page, errors = open_page(make_page, base_url, "tour", browser_no_webgl, hash_="#knowledge")
    wait_stop(page, 2)
    assert page.locator("[data-kb-unfold]").is_visible() and page.locator(".tour-hint").is_hidden()
    open_sheet(page)
    sheet = page.locator("[data-kb-sheet]")
    assert sheet.locator("h2").inner_text() == "Knowledge base trail map"
    assert sheet.locator("svg text", has_text="Artifactory").count() == 1
    assert sheet.locator("svg a").count() == 0          # the draft ships with no links yet
    page.keyboard.press("ArrowRight")
    page.wait_for_timeout(300)
    assert tour_index(page) == 2 and sheet.evaluate("d => d.open")
    page.keyboard.press("Escape")
    page.wait_for_function("() => !document.querySelector('[data-kb-sheet]').open")
    assert page.evaluate("location.hash") == "#knowledge"
    assert page.evaluate("document.activeElement.hasAttribute('data-kb-unfold')")
    page.locator("[data-kb-unfold]").click()
    page.locator("[data-kb-close]").click()
    page.wait_for_function("() => !document.querySelector('[data-kb-sheet]').open")
    assert errors == []


def test_the_unfold_button_only_shows_at_the_knowledge_stop(make_page, browser_no_webgl, base_url):
    page, _ = open_page(make_page, base_url, "tour", browser_no_webgl, hash_="#scaffolding")
    wait_stop(page, 1)
    assert page.locator("[data-kb-unfold]").is_hidden() and page.locator(".tour-hint").is_visible()


def test_linked_destinations_open_in_a_new_tab_from_the_card_and_the_map(make_page, browser_no_webgl, base_url):
    page = make_page(browser_no_webgl)
    with_tour_file(page, TOUR_FILE.read_text(encoding="utf-8").replace(
        "{ name: 'Java', url: ''", "{ name: 'Java', url: 'https://wiki.example.com/java'"))
    page.goto(base_url + PAGES["tour"] + "#knowledge")
    wait_stop(page, 2)
    for _ in range(3):
        page.locator("[data-card-next]").click()       # page 4: Language specific
    link = page.locator("[data-card-body] a", has_text="Java")
    assert link.get_attribute("href") == "https://wiki.example.com/java"
    assert link.get_attribute("target") == "_blank" and "noopener" in link.get_attribute("rel")
    open_sheet(page)
    a = page.locator("[data-kb-sheet] svg a")
    assert a.count() == 1 and a.get_attribute("href") == "https://wiki.example.com/java"
    assert a.get_attribute("target") == "_blank" and "noopener" in a.get_attribute("rel")


def test_names_with_markup_stay_words(make_page, browser_no_webgl, base_url):
    page = make_page(browser_no_webgl)
    with_tour_file(page, TOUR_FILE.read_text(encoding="utf-8").replace(
        "{ name: 'Proxy', url: ''", "{ name: '<b>R&D</b>', url: ''"))
    page.goto(base_url + PAGES["tour"] + "#knowledge")
    wait_stop(page, 2)
    page.locator("[data-card-next]").click()
    assert "<b>R&D</b>" in page.locator("[data-card-body] .kb-trail").inner_text()
    assert page.locator("[data-card-body] .kb-trail b").count() == 0
    open_sheet(page)
    assert page.locator("[data-kb-sheet] svg b").count() == 0
    assert page.locator("[data-kb-sheet] svg text", has_text="<b>R&D</b>").count() == 1


def test_going_back_with_the_map_open_closes_it(make_page, browser_no_webgl, base_url):
    page, _ = open_page(make_page, base_url, "tour", browser_no_webgl, hash_="#scaffolding")
    wait_stop(page, 1)
    page.locator("button[data-sign=right]").click()
    wait_stop(page, 2)
    open_sheet(page)
    page.go_back()
    wait_stop(page, 1)
    assert not page.evaluate("document.querySelector('[data-kb-sheet]').open")


def test_the_map_still_draws_when_the_fonts_fail(make_page, browser_no_webgl, base_url):
    page = make_page(browser_no_webgl)
    errors = collect_errors(page)
    page.route("**/*.woff2", lambda route: route.abort())
    page.goto(base_url + PAGES["tour"] + "#knowledge")
    wait_stop(page, 2)
    open_sheet(page)
    assert page.locator("[data-kb-sheet] svg text").count() >= 21
    assert not [e for e in errors if e.startswith("pageerror")]
```

- [ ] **Step 2: Run them to check they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_pages.py -q -k "unfold or linked or markup or going_back or fonts_fail"`
Expected: FAIL (`[data-kb-unfold]` not found).

- [ ] **Step 3: Add the markup to `public/tour/index.html`**

Replace the card footer's hint line with the hint plus the button:

```html
        <span class="tour-hint">Use the signposts, or the ← → keys.</span>
        <button class="btn btn-ghost kb-unfold" type="button" data-kb-unfold hidden>Unfold the map</button>
```

Add after the closing `</section>` of the tour card:

```html
    <dialog class="kb-sheet" data-kb-sheet aria-labelledby="kb-sheet-title">
      <div class="kb-sheet-head">
        <h2 id="kb-sheet-title">Knowledge base trail map</h2>
        <button class="btn btn-ghost" type="button" data-kb-close>Close</button>
      </div>
      <div class="kb-sheet-map" data-kb-sheet-map></div>
    </dialog>
```

- [ ] **Step 4: Wire it up in `tour.js`**

1. Add the import: `import { layoutMap, drawMap, svgPainter, canvasMeasure, loadMapFonts } from './kbmap.js';`
2. In `els`, add:

```js
    hint: q(doc, '.tour-hint'),
    unfold: q(doc, '[data-kb-unfold]'),
    sheet: q(doc, '[data-kb-sheet]'),
    sheetMap: q(doc, '[data-kb-sheet-map]'),
    sheetClose: q(doc, '[data-kb-close]'),
```

3. In `renderCard`, before `syncMap();`, add:

```js
    els.unfold.hidden = !stop.map;
    els.hint.hidden = Boolean(stop.map);
```

4. After `syncMap()`, add:

```js
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

  // The unfolded map: a modal dialog (Escape and Close shut it; focus goes back to whatever opened it).
  let sheetReturn = null;
  async function openSheet(returnTo) {
    const laid = await mapLayout();
    if (!laid || els.sheet.open) return;
    const painter = svgPainter(doc);
    drawMap(painter, laid, { links: true });
    painter.svg.setAttribute('role', 'group');
    painter.svg.setAttribute('aria-label', 'Knowledge base trail map');
    els.sheetMap.replaceChildren(painter.svg);
    sheetReturn = returnTo;
    els.sheet.showModal();
  }
  els.unfold.addEventListener('click', () => openSheet(els.unfold));
  els.sheetClose.addEventListener('click', () => els.sheet.close());
  els.sheet.addEventListener('close', () => {
    const back = sheetReturn;
    sheetReturn = null;
    if (back && back.isConnected && !back.hidden) back.focus({ preventScroll: true });
  });
```

5. At the very top of `go()`, before `const outcome = …`, add: `if (els.sheet.open) els.sheet.close();`
6. At the top of the `keydown` listener, before the modifier-key check, add: `if (els.sheet.open) return;   // the dialog handles its own keys (Escape closes it)`.

- [ ] **Step 5: Style the button and the sheet** (append to the tour section of `site.css`)

```css
.kb-unfold { min-height: 36px; padding: 6px 14px; font-size: 15px; }
.kb-sheet { width: min(1300px, calc(100vw - 32px)); max-height: 92vh; padding: 16px 20px 20px; border: 0; border-radius: 12px; background: #E6D6AE; color: #2A1A0F; box-shadow: 0 30px 80px rgba(0, 0, 0, 0.6); }
.kb-sheet::backdrop { background: rgba(5, 10, 12, 0.78); }
.kb-sheet-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin: 0 0 8px; }
.kb-sheet-head h2 { margin: 0; font-family: var(--display); font-weight: 600; font-size: 28px; }
.kb-sheet-head .btn-ghost { color: #2A1A0F; border-color: #6B5640; background: transparent; }
.kb-sheet-map { overflow: auto; }
.kb-sheet-map svg { display: block; width: 100%; min-width: 960px; height: auto; }
.kb-sheet-map a:focus-visible { outline: 3px solid #B8452A; outline-offset: 2px; }
.kb-sheet-map a:hover text { fill: #7A2A20; }
```

- [ ] **Step 6: Run the tests to check they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_pages.py -q`
Expected: all PASS. That includes the existing `test_tour_escape_goes_home` (the key guard only applies while the dialog is open).

- [ ] **Step 7: Commit**

```bash
git add public/tour/index.html public/js/tour.js public/css/site.css tests/test_pages.py
git commit -F - <<'EOF'
feat: unfold the knowledge-base map

An Unfold the map button on stop 3's card opens the whole trail map
in a modal dialog, every linked destination clickable (new tab,
noopener). Escape and Close shut it and return focus; while it's open
the tour's own keys do nothing, and navigating away closes it.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
EOF
```

---

### Task 5: Blender: a blank kiosk board, and its frame for the page

**Files:**
- Modify: `blender/blazeahead_layout.py` (`MAP_BOARD`, `MAP_FACE`, `MAP_GRID`; `build_kiosk` records the board frame; `board_web()`, `board_corners()`; `to_web` exports `props.kioskBoard` and `stillSigns.knowledge.board`)
- Modify: `blender/build_blazeahead.py` (`build_kiosk`: `KioskMap` keeps only the paper)
- Modify: `tests/test_layout.py`, `tests/test_blender_build.py`
- Regenerate: `public/assets/blazeahead.glb`, `world.json`, `junction.json`, `still-signs.json`, `stills/knowledge.webp`

**Interfaces:**
- Produces:
  - `world.json` → `props.kioskBoard`:
    - `centre`, `right`, `up` and `normal` (Y-up, the web's coordinates);
    - `size: [1.38, 0.88]` and `grid: [9, 6]`;
    - `light`: 54 linear-RGB tints, row by row from the top, left to right as the viewer sees it.
  - `still-signs.json` → `knowledge.board`: 4 `[x, y]` fractions of the still image, clockwise from top-left.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_layout.py`)

```python
def test_the_kiosk_board_is_exported_for_the_live_map():
    web = L.to_web(W)
    b = web["props"]["kioskBoard"]
    assert b["size"] == [1.38, 0.88] and b["grid"] == [9, 6] and len(b["light"]) == 54
    assert all(0.0 < c <= 4.0 for rgb in b["light"] for c in rgb)
    r, u, n = b["right"], b["up"], b["normal"]
    assert abs(sum(x * y for x, y in zip(r, u))) < 1e-3
    cross = [r[1] * u[2] - r[2] * u[1], r[2] * u[0] - r[0] * u[2], r[0] * u[1] - r[1] * u[0]]
    assert all(abs(a - c) < 1e-3 for a, c in zip(cross, n))
    cam = web["views"]["knowledge"]["position"]
    assert sum((c - p) * q for c, p, q in zip(cam, b["centre"], n)) > 0      # it faces the knowledge view
    top = sum(rgb[0] for rgb in b["light"][:9]) / 9
    bottom = sum(rgb[0] for rgb in b["light"][-9:]) / 9
    assert top > bottom                                                       # the two lanterns hang above it


def test_the_still_knows_where_the_kiosk_board_is():
    corners = L.to_web(W)["stillSigns"]["knowledge"]["board"]
    assert len(corners) == 4 and all(0.0 < v < 1.0 for c in corners for v in c)
    tl, tr, br, bl = corners
    assert tl[0] < tr[0] and bl[0] < br[0] and tl[1] < bl[1] and tr[1] < br[1]
    assert 0.15 < tr[0] - tl[0] < 0.5 and tl[1] < 0.5
```

In `test_web_json_is_y_up_and_within_budget`, change the loop header so it skips the board's corners:

```python
    for box in (b for s in web["stillSigns"].values() for k, b in s.items() if k != "board"):
```

In `tests/test_blender_build.py`, add to the end of `test_blender_build_exports_the_world`:

```python
    assert set(world["props"]["kioskBoard"]) >= {"centre", "right", "up", "normal", "size", "grid", "light"}
    assert not [lb for lb in world.get("labels", []) if (lb.get("key") or "").startswith("map:")]
    signs = json.loads((tmp_path / "still-signs.json").read_text())
    assert len(signs["knowledge"]["board"]) == 4
```

- [ ] **Step 2: Run them to check they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_layout.py -q`
Expected: the two new tests FAIL (`KeyError: 'kioskBoard'`).

- [ ] **Step 3: Record the board in the layout** (`blender/blazeahead_layout.py`)

Add near the other light constants (after `FLOW_LIGHT`):

```python
MAP_BOARD = (1.38, 0.88)          # the knowledge kiosk's map board (width, height), metres
MAP_FACE = (0.0, -0.109, 1.35)    # its centre in the kiosk's frame: 3 mm in front of the paper (local -y faces the viewer)
MAP_GRID = (9, 6)                 # light samples across and down it, for the live scene's tint
```

At the end of `build_kiosk(W, f)`, after the lantern loop, add:

```python
    # the map board's face: the live scene lays the trail map there, and the still gets its corners
    lx, ly, lz = MAP_FACE
    k["board"] = {"centre": [k["pos"][0] + ax * lx - fx * ly, k["pos"][1] + ay * lx - fy * ly, k["pos"][2] + lz],
                  "right": [ax, ay, 0.0], "up": [0.0, 0.0, 1.0], "normal": [fx, fy, 0.0], "size": list(MAP_BOARD)}
```

(`ax, ay` and `fx, fy` are already computed at the top of `build_kiosk`: the kiosk's local x and its local −y, the direction toward the viewer.)

Add before `def to_web(world):`:

```python
def board_corners(bd):
    """The map board's corners, clockwise from the top-left as the viewer sees it."""
    w, h = bd["size"]
    return [[c + r * sx * w / 2 + u * sy * h / 2 for c, r, u in zip(bd["centre"], bd["right"], bd["up"])]
            for sx, sy in ((-1, 1), (1, 1), (1, -1), (-1, -1))]


def board_web(bd, sources):
    """The board's frame for the browser (Y-up) and its baked light: MAP_GRID tints, row by row from the top."""
    w, h = bd["size"]
    cols, rows = MAP_GRID
    light = []
    for j in range(rows):
        for i in range(cols):
            u = -w / 2 + w * i / (cols - 1)
            v = h / 2 - h * j / (rows - 1)
            p = [c + r * u + q * v for c, r, q in zip(bd["centre"], bd["right"], bd["up"])]
            lr, lg, lb = light_at(*p, *bd["normal"], sources)
            light.append([round(min(4.0, lr), 3), round(min(4.0, lg), 3), round(min(4.0, lb), 3)])
    return {"centre": _p(bd["centre"]), "right": _p(bd["right"], 4), "up": _p(bd["up"], 4),
            "normal": _p(bd["normal"], 4), "size": list(bd["size"]), "grid": [cols, rows], "light": light}
```

In `to_web`, right after the `for s in world["stops"]:` loop that fills `still_signs`, add:

```python
    board = world["props"].get("kiosk", {}).get("board")
    if board:
        kv = next(s["view"] for s in world["stops"] if s["id"] == "knowledge")
        still_signs["knowledge"]["board"] = [[round(v, 4) for v in screen_xy(kv, p)] for p in board_corners(board)]
```

After the `if "tent" in world["props"]:` block, add:

```python
    if board:
        web["props"]["kioskBoard"] = board_web(board, world["sources"])
```

- [ ] **Step 4: Run the layout tests to check they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_layout.py -q`
Expected: all PASS.

- [ ] **Step 5: Blank the board in the Blender build** (`blender/build_blazeahead.py`)

In `build_kiosk(world, font)`:

1. Change `paper, note, ink = baker(src, "#DCCDA6"), baker(src, "#F2EAD3"), baker(src, "#4A3626")` to `paper = baker(src, "#DCCDA6")`.
2. Change `pin, burn, iron = baker(src, "#B83A2A"), baker(src, "#2A1A0F"), baker(src, "#221E1B")` to `iron = baker(src, "#221E1B")`. `burn` and `pin` are only used by the map; check with a search for `burn` in the function before deleting.
3. Replace everything from `mp = Part("KioskMap")` down to (not including) `return [p.finish(), mp.finish()]` with:

```python
    # the map board is plain paper: the page draws the trail map on it (live, and over the still)
    mp = Part("KioskMap")
    mp.add_bm(cube_bm((L.MAP_BOARD[0], 0.012, L.MAP_BOARD[1]), (0, -0.1, L.MAP_FACE[2])), face_color=paper, matrix=m)
```

- [ ] **Step 6: Rebuild the assets and re-render the knowledge still**

Run (about 8 minutes: the build takes about a minute, then Cycles renders one still):

```bash
"/c/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b --factory-startup --python-exit-code 1 --python blender/build_blazeahead.py -- --stills --only knowledge
```

Expected: the output ends with `SELFCHECK …` and `BUILD OK`, and `git status` shows the GLB, the JSON files and `public/assets/stills/knowledge.webp` changed. Open `knowledge.webp` and check that the kiosk board is blank, lantern-lit paper.

- [ ] **Step 7: Run the slow build test and the fast suite**

Run: `.venv/Scripts/python.exe -m pytest -m slow tests/test_blender_build.py -q -k exports_the_world`, then `.venv/Scripts/python.exe -m pytest -q`
Expected: all PASS. The live tour tests still pass: the board is blank paper until Task 6 paints it.

- [ ] **Step 8: Commit**

```bash
git add blender/blazeahead_layout.py blender/build_blazeahead.py blender/blazeahead.blend tests/test_layout.py tests/test_blender_build.py public/assets/blazeahead.glb public/assets/world.json public/assets/junction.json public/assets/still-signs.json public/assets/stills/knowledge.webp
git commit -F - <<'EOF'
feat: a blank kiosk board, with its frame and corners for the page

The kiosk's hard-coded map (dots, labels, pinned notes) is gone; the
board is plain paper. The layout exports the board's frame and a 9 x 6
grid of its lantern light in world.json, and its four corners in the
knowledge still in still-signs.json, so the page can draw the trail map
on it live and over the still. The knowledge still is re-rendered.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
EOF
```

---

### Task 6: The live kiosk paints the map

**Files:**
- Modify: `public/js/world.js` (`buildBoard`, `paintBoard`, `boardAt`)
- Modify: `public/js/stage-live.js` (`api.paintMap`, `api.onboard`, board hover and click)
- Modify: `public/js/tour.js` (`syncMap` paints the live board; `attachLive` wires `onboard` and syncs)
- Test: `tests/test_tour_live.py`

**Interfaces:**
- Consumes: `props.kioskBoard` (Task 5); `drawMap`, `canvasPainter`, `BOARD` (Task 2); `mapLayout`, `openSheet`, `litTrail`, `syncMap` (Tasks 3–4).
- Produces:
  - `WorldView.board = { mesh, canvas, tex, focus, draws }` (or `undefined`);
  - `WorldView.paintBoard(laid, focus) → boolean` and `WorldView.boardAt(ndcX, ndcY) → boolean`;
  - stage API: `paintMap(laid, focus) → boolean`, and an `onboard` callback, set by `tour.js`.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_tour_live.py`)

```python
BOARD = "document.querySelector('[data-stage]').__blaze.view.board"


def test_the_kiosk_map_lights_the_trail_on_each_card_page(make_page, base_url):
    page, errors = open_tour(make_page, base_url, "#knowledge")
    wait_stop(page, 2)
    page.wait_for_function(f"() => {BOARD} && {BOARD}.draws > 0", timeout=10000)
    assert page.evaluate(f"{BOARD}.focus") is None
    before = page.evaluate(f"{BOARD}.draws")
    page.locator("[data-card-next]").click()
    page.wait_for_function(f"(n) => {BOARD}.draws > n", arg=before)
    assert page.evaluate(f"{BOARD}.focus") == 0
    page.locator("[data-card-prev]").click()
    page.wait_for_function(f"() => {BOARD}.focus === null")
    assert errors == []


def test_clicking_the_kiosk_map_unfolds_it(make_page, base_url):
    page, _ = open_tour(make_page, base_url, "#knowledge")
    wait_stop(page, 2)
    page.wait_for_function(f"() => {BOARD} && {BOARD}.draws > 0", timeout=10000)
    xy = page.evaluate("""() => { const v = document.querySelector('[data-stage]').__blaze.view;
        const p = v.board.mesh.position.clone().project(v.camera); const r = v.canvas.getBoundingClientRect();
        return [r.left + (p.x + 1) / 2 * r.width, r.top + (1 - p.y) / 2 * r.height]; }""")
    page.mouse.click(xy[0], xy[1])
    page.wait_for_function("() => document.querySelector('[data-kb-sheet]').open")
    page.keyboard.press("Escape")
    page.wait_for_function("() => !document.querySelector('[data-kb-sheet]').open")
    assert page.evaluate("document.activeElement.hasAttribute('data-card-heading')")
    assert page.evaluate("location.hash") == "#knowledge"
```

- [ ] **Step 2: Run them to check they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_tour_live.py -q -k "kiosk_map"`
Expected: FAIL (`view.board` is undefined).

- [ ] **Step 3: Build and paint the board in `world.js`**

1. Add the import: `import { BOARD as MAP_BOARD, drawMap, canvasPainter } from './kbmap.js';`
2. In the constructor, right after the `for (const lb of layout.labels || [])` loop, add:

```js
    if (layout.props && layout.props.kioskBoard && assets.which !== 'junction') {
      try {
        this.buildBoard(layout.props.kioskBoard);
      } catch (err) {
        console.warn('blazeAhead: the kiosk map could not be drawn in 3D; the card and the unfolded map still work.', err);
      }
    }
```

3. Add these methods to `WorldView`, after `collectSigns`:

```js
  // The knowledge kiosk's map board: a panel just in front of the paper, carrying the trail map as a canvas texture,
  // tinted by the baked lantern light (a grid of vertex colours, row by row from the top-left, as PlaneGeometry
  // orders its vertices).
  buildBoard(b) {
    const canvas = document.createElement('canvas');
    canvas.width = 2048;
    canvas.height = Math.round((2048 * MAP_BOARD.h) / MAP_BOARD.w);
    const tex = new THREE.CanvasTexture(canvas);
    tex.colorSpace = THREE.SRGBColorSpace;
    tex.anisotropy = this.renderer.capabilities.getMaxAnisotropy();
    const [cols, rows] = b.grid;
    const geo = new THREE.PlaneGeometry(b.size[0], b.size[1], cols - 1, rows - 1);
    const colors = new Float32Array(cols * rows * 3);
    b.light.forEach((c, i) => colors.set(c, i * 3));
    geo.setAttribute('color', new THREE.BufferAttribute(colors, 3));
    const mat = new THREE.MeshBasicMaterial({ map: tex, vertexColors: true, fog: true,
      polygonOffset: true, polygonOffsetFactor: -1, polygonOffsetUnits: -1 });
    const mesh = new THREE.Mesh(geo, mat);
    const basis = new THREE.Matrix4().makeBasis(new THREE.Vector3(...b.right), new THREE.Vector3(...b.up),
      new THREE.Vector3(...b.normal));
    mesh.quaternion.setFromRotationMatrix(basis);
    mesh.position.set(...b.centre);
    this.scene.add(mesh);
    this.board = { mesh, canvas, tex, focus: null, draws: 0 };
    this.disposables.push(geo, mat, tex);
  }

  paintBoard(laid, focus = null) {
    const bd = this.board;
    if (!bd || !laid) return false;
    const ctx = bd.canvas.getContext('2d');
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, bd.canvas.width, bd.canvas.height);
    drawMap(canvasPainter(ctx, bd.canvas.width / MAP_BOARD.w), laid, { focus });
    bd.tex.needsUpdate = true;
    bd.focus = focus;
    bd.draws += 1;
    return true;
  }

  boardAt(ndcX, ndcY) {
    return Boolean(this.board) && this.toRay(ndcX, ndcY).intersectObject(this.board.mesh, false).length > 0;
  }
```

- [ ] **Step 4: Expose it from the stage** (`stage-live.js`)

1. After `api.signBox = …`, add:

```js
  api.paintMap = (laid, focus) => {
    if (stopped || !view.paintBoard(laid, focus)) return false;
    if (!rafId) view.render();
    return true;
  };
  const atKiosk = () => variant === 'tour' && !walking && VIEW_ORDER[stopIndex + 1] === 'knowledge';
```

2. In the `pointermove` listener, after the `if (variant === 'home') {…}` block, add:

```js
    if (atKiosk()) canvas.style.cursor = view.boardAt(x, y) ? 'pointer' : '';
```

3. In the `click` listener, add after the home line:

```js
    if (atKiosk() && typeof api.onboard === 'function' && view.boardAt(...toNdc(event))) api.onboard();
```

- [ ] **Step 5: Paint it from the tour** (`tour.js`)

1. Replace `syncMap` with:

```js
  function syncMap() {
    const trail = litTrail();
    doc.body.dataset.kbTrail = trail === null ? '' : String(trail);
    if (stage && stage.paintMap) {
      mapLayout().then((laid) => {
        if (laid && stage && stage.paintMap) stage.paintMap(laid, litTrail());
      });
    }
  }
```

2. In `api.attachLive`, after `if (state.index >= 0 && stage.show) stage.show(state.index);`, add:

```js
      stage.onboard = () => openSheet(q(doc, '[data-card-heading]'));
      syncMap();
```

- [ ] **Step 6: Run the tests to check they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_tour_live.py tests/test_stage.py -q`
Expected: all PASS.

- [ ] **Step 7: Look at it**

Run `python tools/serve.py`, open `http://localhost:8000/tour/#knowledge`, and page through the card. Check that:
- the map sits on the board;
- it is lit warmer near the lanterns;
- the lit trail glows and the others fade;
- clicking the board opens the sheet.

- [ ] **Step 8: Commit**

```bash
git add public/js/world.js public/js/stage-live.js public/js/tour.js tests/test_tour_live.py
git commit -F - <<'EOF'
feat: the live kiosk shows the trail map

The 3D kiosk carries the map as a canvas texture on a panel in front of
the paper, tinted by the baked lantern light. Paging the card lights
that trail on the board; clicking the board unfolds the map.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
EOF
```

---

### Task 7: The map on the still image

**Files:**
- Modify: `public/tour/index.html` (the overlay container)
- Modify: `public/js/tour.js` (`placeOverlay`; `syncMap` paints the overlay when there's no live stage; hide while walking or live; click to unfold)
- Modify: `public/css/site.css` (overlay)
- Test: `tests/test_pages.py`

**Interfaces:**
- Consumes: `stillSigns.knowledge.board` (Task 5); `quadMatrix3d`, `BOARD`, `svgPainter`, `drawMap` (Task 2); `syncMap`, `mapLayout`, `openSheet`, `placeSigns` (Tasks 3–4).
- Produces: `[data-kb-overlay]`, shown only at stop 3 on stills when not walking; `placeOverlay()` in `tour.js`.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_pages.py`)

```python
OVERLAY_CORNERS = """async () => {
    const o = document.querySelector('[data-kb-overlay]');
    const main = document.querySelector('main').getBoundingClientRect();
    const img = [...document.querySelectorAll('[data-stage] img.stage-still')].find((i) => !i.classList.contains('is-hidden'));
    const r = img.getBoundingClientRect();
    const board = (await (await fetch('../assets/still-signs.json')).json()).knowledge.board;
    const m = new DOMMatrix(getComputedStyle(o).transform);
    const at = (x, y) => { const p = m.transformPoint(new DOMPoint(x, y, 0, 1)); return [main.left + p.x / p.w, main.top + p.y / p.w]; };
    return { got: [at(0, 0), at(1380, 0), at(1380, 880), at(0, 880)],
             want: board.map(([fx, fy]) => [r.left + fx * r.width, r.top + fy * r.height]) };
}"""


def assert_on_the_board(page):
    c = page.evaluate(OVERLAY_CORNERS)
    for (gx, gy), (wx, wy) in zip(c["got"], c["want"]):
        assert abs(gx - wx) < 4 and abs(gy - wy) < 4, c


@pytest.mark.parametrize("size", [(1440, 900), (1024, 768)])
def test_the_still_shows_the_map_on_the_kiosk_board(make_page, browser_no_webgl, base_url, size):
    page, errors = open_page(make_page, base_url, "tour", browser_no_webgl, hash_="#knowledge",
                             viewport={"width": size[0], "height": size[1]})
    wait_stop(page, 2)
    page.wait_for_function("() => !document.querySelector('[data-kb-overlay]').hidden")
    assert_on_the_board(page)
    assert page.locator("[data-kb-overlay] svg text", has_text="Artifactory").count() == 1
    assert errors == []


def test_the_still_map_follows_the_card_and_the_window(make_page, browser_no_webgl, base_url):
    page, _ = open_page(make_page, base_url, "tour", browser_no_webgl, hash_="#knowledge")
    wait_stop(page, 2)
    page.wait_for_function("() => !document.querySelector('[data-kb-overlay]').hidden")
    assert page.locator("[data-kb-overlay] svg filter").count() == 0
    page.locator("[data-card-next]").click()
    page.wait_for_function("() => document.querySelectorAll('[data-kb-overlay] svg filter').length === 1")
    page.set_viewport_size({"width": 1200, "height": 800})
    page.wait_for_timeout(300)
    assert_on_the_board(page)
    c = page.evaluate(OVERLAY_CORNERS)["want"]
    page.mouse.click((c[0][0] + c[2][0]) / 2, (c[0][1] + c[2][1]) / 2)
    page.wait_for_function("() => document.querySelector('[data-kb-sheet]').open")


def test_the_still_map_shows_only_at_the_knowledge_stop(make_page, browser_no_webgl, base_url):
    page, _ = open_page(make_page, base_url, "tour", browser_no_webgl, hash_="#scaffolding")
    wait_stop(page, 1)
    assert page.locator("[data-kb-overlay]").is_hidden()
    page.keyboard.press("ArrowRight")
    wait_stop(page, 2)
    page.wait_for_function("() => !document.querySelector('[data-kb-overlay]').hidden")
    page.keyboard.press("ArrowRight")
    wait_stop(page, 3)
    assert page.locator("[data-kb-overlay]").is_hidden()


def test_reduced_motion_shows_the_still_map(make_page, base_url):
    page, _ = open_page(make_page, base_url, "tour", hash_="#knowledge", reduced_motion="reduce")
    wait_stop(page, 2)
    page.wait_for_function("() => !document.querySelector('[data-kb-overlay]').hidden")
    assert_on_the_board(page)
```

- [ ] **Step 2: Run them to check they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_pages.py -q -k "still_map or still_shows or reduced_motion_shows"`
Expected: FAIL (`[data-kb-overlay]` not found).

- [ ] **Step 3: Add the container** (`public/tour/index.html`)

Right after the stage `<div class="stage tour-stage" …>…</div>`, add:

```html
    <div class="kb-overlay" data-kb-overlay hidden></div>
```

- [ ] **Step 4: Place and paint it** (`tour.js`)

1. Change the kbmap import to: `import { BOARD, layoutMap, drawMap, svgPainter, canvasMeasure, loadMapFonts, quadMatrix3d } from './kbmap.js';`
2. In `els`, add `overlay: q(doc, '[data-kb-overlay]'),`.
3. Replace `syncMap` with:

```js
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
    });
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
```

`stillSigns` and `shown` are declared before this point, near the top of `startTour`, so the closures see them.

4. At the end of `placeSigns()`, add `placeOverlay();`. `placeSigns` already runs on render, resize, the still-signs fetch, and live attach and detach.
5. At the end of `setWalking(on)`, add `placeOverlay();`.
6. In `api.detachLive`, change the body to:

```js
      stage = null;
      showStill(idFor(Math.max(0, state.index)), true).then(() => {
        placeSigns();
        syncMap();
      });
```

- [ ] **Step 5: Style it** (append to the tour section of `site.css`)

```css
.kb-overlay { position: absolute; z-index: 1; left: 0; top: 0; width: 1380px; height: 880px; transform-origin: 0 0; mix-blend-mode: multiply; cursor: pointer; }
.kb-overlay svg { display: block; width: 100%; height: 100%; }
```

- [ ] **Step 6: Run the tests to check they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_pages.py tests/test_tour_live.py -q`
Expected: all PASS.

- [ ] **Step 7: Look at it**

With `python tools/serve.py` running, open `http://localhost:8000/tour/#knowledge` in a reduced-motion browser context, or in Chrome with WebGL disabled. Check that the map sits on the kiosk board of the still, lit like the paper, and that paging the card lights each trail.

- [ ] **Step 8: Commit**

```bash
git add public/tour/index.html public/js/tour.js public/css/site.css tests/test_pages.py
git commit -F - <<'EOF'
feat: the trail map on the still image

Where the tour shows stills (no 3D, reduced motion, before 3D loads),
the map is laid over the kiosk's board: warped onto its four corners
from still-signs.json and multiplied in, so the still's lantern light
shows through. It follows the card's lit trail, the window's size, and
unfolds on a click.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
EOF
```

---

### Task 8: Screenshots, docs and the zip

**Files:**
- Modify: `tools/verify.py` (lit-trail and open-sheet shots)
- Modify: `public/js/tour.js` (the knowledge stop's description)
- Modify: `README.md`, `docs/superpowers/specs/2026-09-25-blazeahead-site-design.md`
- Regenerate: `dist/blazeahead-site.zip` (not tracked)

**Interfaces:**
- Consumes: everything above.

- [ ] **Step 1: Add the shots to `tools/verify.py`**

In the tour loop, right after `shot(report, page, f"tour-{STOPS[i]}")`, add:

```python
            if STOPS[i] == "knowledge":
                page.locator("[data-card-next]").click()
                page.wait_for_timeout(400)
                shot(report, page, "tour-kb-trail")
                page.locator("[data-kb-unfold]").click()
                page.wait_for_function("() => document.querySelector('[data-kb-sheet]').open", timeout=5000)
                page.wait_for_timeout(300)
                shot(report, page, "tour-kb-sheet")
                page.keyboard.press("Escape")
                page.locator("[data-card-prev]").click()
```

- [ ] **Step 2: Update the stop's description** (`tour.js`)

Change the `knowledge` entry in `DESCRIPTIONS` to: `knowledge: 'A trail kiosk headed Knowledge Base, with a map of coloured trails leading from blazeAhead to the company’s tools.',`

- [ ] **Step 3: Update the docs**

In `README.md`, in the paragraph beginning `**`public/tour-content.js`** holds the tour's words`, change "the knowledge-base cards (readers page through them)" to "the knowledge-base trail map". Then add this bullet under it, after the "Keep `sign` words short" bullet:

```markdown
- **The trail map** is the `map` in the knowledge stop: trails from the centre, each with its destinations, and a destination can lead on to more (`next`). It holds up to 5 trails, 5 destinations on a trail, 2 onward stops per destination, and 25 stops in all. A `url` that starts with `https://` makes a name a link on the card and on the unfolded map. The map lays itself out, and a change shows up everywhere (the 3D kiosk, the still image and the unfolded map) as soon as you publish. No re-render is needed. If a very full map can't fit every name cleanly, it still draws, and the browser console says so.
```

In `docs/superpowers/specs/2026-09-25-blazeahead-site-design.md`:
- line 111's row: replace "Its map shows the network as trails (proxy at the centre, the services around it, "you are here"), with pinned note cards and two lanterns." with "Its board carries the knowledge-base trail map (see [2026-09-25-kb-trail-map-design.md](2026-09-25-kb-trail-map-design.md)), lit by two lanterns."
- line 163's row: replace the card description with "Every internal tool, charted as trails from one trailhead; the card steps through the trails (see the trail-map spec)."
- line 250: change "KB cards" to "KB trail map".

- [ ] **Step 4: Run everything**

Run: `.venv/Scripts/python.exe -m pytest -q`, then `.venv/Scripts/python.exe tools/verify.py`
Expected: all tests PASS, and verify prints `All budgets and states OK.` Open these files in `verify-output/` and check them by eye:
- `tour-knowledge.png`: the map on the live board;
- `tour-kb-trail.png`: one trail lit;
- `tour-kb-sheet.png`: the sheet, readable;
- `tour-reduced-motion.png`: the map on the still;
- `tour-kb-short.png`: the short window.

- [ ] **Step 5: Rebuild the zip**

Run: `.venv/Scripts/python.exe tools/package.py`
Expected: `wrote dist\blazeahead-site.zip (…)`.

- [ ] **Step 6: Commit**

```bash
git add tools/verify.py public/js/tour.js README.md docs/superpowers/specs/2026-09-25-blazeahead-site-design.md
git commit -F - <<'EOF'
docs: the trail map in the README, the specs and the screenshots

verify.py now shoots a lit trail and the unfolded map; the README tells
the owner how to edit the map; the main spec points at the trail-map
spec for stop 3.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
EOF
```
