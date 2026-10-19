"""#15's what's-new card (whatsnew.js): the module, the page shell, the still path and the live trigger.

Every expected string is a literal here, never imported from the modules, so a reworded string fails these tests.
"""
import re
from pathlib import Path

import pytest

import helpers
from helpers import HOME

WEAVE = Path(__file__).resolve().parents[1]
MARKUP = '<img src=x onerror="window.__pwned=1">'
RELEASE_TEXT = "New this release · v1.1 (sample release)"

# --- The module on a blank page. mk(kind, opts) builds a stage, a region, the toggle, an h1 (tabindex -1) and a
# button X, then createNews over them with a counting recordSeen; kind is none-live, none-still, still or live.
# tick() lets the module's one-task append (and anything else queued) run. ---

NEWS_JS = r"""
    const W = await import('/public/js/whatsnew.js');
    const tick = () => new Promise((r) => setTimeout(r, 0)).then(() => new Promise((r) => setTimeout(r, 0)));
    const RELEASE = { kind: 'release', text: 'New this release · v1.1 (sample release)',
                      groups: [{ version: '1.1', names: ['Travel', 'Desk Allocation'] }] };
    const mk = (kind, opts = {}) => {
      document.body.replaceChildren();
      const stage = document.createElement('div');
      const region = document.createElement('div');
      region.setAttribute('aria-live', 'polite');
      const toggle = document.createElement('button');
      toggle.textContent = 'Unstitch';
      const h1 = document.createElement('h1');
      h1.tabIndex = -1;
      h1.textContent = 'Title';
      const x = document.createElement('button');
      x.textContent = 'X';
      document.body.append(h1, stage, toggle, x, region);
      const calls = { n: 0 };
      const none = kind.startsWith('none');
      const news = W.createNews({
        stage, region: opts.noRegion ? null : region, heading: none ? null : (opts.heading ?? RELEASE),
        newIds: none ? [] : ['travel', 'desks'], recordSeen: () => { calls.n += 1; return true; },
        live: kind === 'live' || kind === 'none-live', focusFallbacks: [toggle, h1],
      });
      return { stage, region, toggle, h1, x, calls, news };
    };
    const mode = (t, m) => t.stage.dispatchEvent(new CustomEvent('weave:mode', { detail: { mode: m, from: null } }));
    const view = (t) => ({ state: t.news.state, attr: t.stage.dataset.releaseState ?? null,
                           panels: t.stage.dataset.newPanels ?? null, calls: t.calls.n,
                           cards: t.region.querySelectorAll('.whatsnew-card').length });
    const gotIt = (t) => t.region.querySelector('.whatsnew-close');
"""


class TestModule:
    def test_whatsnew_js_imports_nothing(self):
        """A source property on purpose: with comments stripped, whatsnew.js has no import of any kind, so the still
        path can never pull in Three.js through it."""
        text = (WEAVE / "public" / "js" / "whatsnew.js").read_text(encoding="utf-8")
        code = re.sub(r"//[^\n]*", "", re.sub(r"/\*.*?\*/", "", text, flags=re.S))
        assert "export function createNews" in code
        assert not re.search(r"^\s*import\b", code, re.M) and "import(" not in code

    @pytest.mark.parametrize("kind, state, panels, calls, cards", [
        ("none-live", "none", "", 1, 0),
        ("none-still", "none", "", 1, 0),
        ("still", "card", "travel desks", 1, 1),
        ("live", "pending", "travel desks", 0, 0),
    ], ids=["none-live", "none-still", "still", "live"])
    def test_news_boot_states(self, js, kind, state, panels, calls, cards):
        got = js(NEWS_JS + f"""
            const t = mk('{kind}');
            const boot = view(t);
            await tick();
            return [boot.state, view(t)];""")
        assert got[0] == state
        assert got[1] == {"state": state, "attr": state, "panels": panels, "calls": calls, "cards": cards}

    def test_news_live_waits_for_quilt(self, js):
        got = js(NEWS_JS + """
            const t = mk('live');
            const out = [];
            mode(t, 'intro'); out.push(view(t));
            mode(t, 'quilt'); out.push(view(t));
            mode(t, 'quilt'); mode(t, 'unstitching'); t.news.fallBack(); out.push(view(t));
            gotIt(t).click(); out.push(view(t));
            mode(t, 'quilt'); t.news.fallBack(); out.push(view(t));
            return out;""")
        assert [(v["state"], v["calls"], v["cards"]) for v in got] == [
            ("pending", 0, 0), ("card", 1, 1), ("card", 1, 1), ("done", 1, 0), ("done", 1, 0)]
        assert [v["attr"] for v in got] == ["pending", "card", "card", "done", "done"]

    def test_news_fallback_while_pending(self, js):
        got = js(NEWS_JS + """
            const a = mk('live');
            a.news.fallBack();
            const first = view(a);
            const b = mk('none-live');
            b.news.fallBack(); mode(b, 'quilt');
            return [first, view(b)];""")
        assert got[0] == {"state": "card", "attr": "card", "panels": "travel desks", "calls": 1, "cards": 1}
        assert got[1] == {"state": "none", "attr": "none", "panels": "", "calls": 1, "cards": 0}

    def test_card_text_is_text(self, js):
        got = js(NEWS_JS + f"""
            const m = {MARKUP!r};
            const t = mk('live', {{ heading: {{ kind: 'release', text: m, groups: [{{ version: '1.1', names: [m, 'B'] }}] }} }});
            mode(t, 'quilt');
            const card = t.region.querySelector('.whatsnew-card');
            return {{ heading: card.querySelector('h2').textContent,
                      names: [...card.querySelectorAll('li')].map((li) => li.textContent),
                      imgs: t.region.querySelectorAll('img').length,
                      tags: [card, ...card.querySelectorAll('*')].map((el) => el.tagName.toLowerCase()),
                      button: gotIt(t).textContent, type: gotIt(t).type }};""")
        assert got["heading"] == MARKUP and got["names"] == [MARKUP, "B"] and got["imgs"] == 0
        assert got["tags"] == ["div", "h2", "ul", "li", "li", "button"]
        assert got["button"] == "Got it" and got["type"] == "button"

    def test_card_groups_since_last_visit(self, js):
        got = js(NEWS_JS + """
            const groups = [{ version: '1.1', names: ['Travel'] }, { version: '1.2', names: ['Promotions'] }];
            const read = (t) => [...t.region.querySelectorAll('.whatsnew-card > *')].map((el) =>
              [el.tagName.toLowerCase(), el.className, el.textContent]);
            const a = mk('live', { heading: { kind: 'since-last-visit', text: 'New since your last visit', groups } });
            mode(a, 'quilt');
            const since = read(a);
            const b = mk('live', { heading: { kind: 'release', text: 'New this release · v1.2', groups } });
            mode(b, 'quilt');
            return [since, read(b)];""")
        assert got[0] == [
            ["h2", "whatsnew-heading", "New since your last visit"],
            ["p", "whatsnew-version", "v1.1"], ["ul", "whatsnew-list", "Travel"],
            ["p", "whatsnew-version", "v1.2"], ["ul", "whatsnew-list", "Promotions"],
            ["button", "whatsnew-close", "Got it"]]
        assert [row[1] for row in got[1]] == ["whatsnew-heading", "whatsnew-list", "whatsnew-list", "whatsnew-close"]

    def test_card_takes_no_focus(self, js):
        got = js(NEWS_JS + """
            const a = mk('live');
            a.toggle.focus();
            const before = document.activeElement === a.toggle;
            mode(a, 'quilt');
            const live = [before, document.activeElement === a.toggle, view(a).cards];
            document.activeElement.blur();
            const b = mk('still');
            const body = document.activeElement === document.body;
            await tick();
            return [live, [body, document.activeElement === document.body, view(b).cards]];""")
        assert got == [[True, True, 1], [True, True, 1]]

    @pytest.mark.parametrize("leg, expected", [
        ("returns", "x"), ("gone", "toggle"), ("hidden", "h1"), ("undisplayed", "h1"), ("body", "toggle"),
    ], ids=["returns", "gone", "hidden", "undisplayed", "body"])
    def test_close_restores_focus(self, js, leg, expected):
        # hidden: the [hidden] clause alone (an inline display keeps a box); undisplayed: the box clause alone.
        got = js(NEWS_JS + f"""
            const t = mk('still');
            await tick();
            const leg = '{leg}';
            if (leg !== 'body') t.x.focus();
            gotIt(t).focus();
            if (leg === 'gone') t.x.remove();
            if (leg === 'hidden') for (const el of [t.x, t.toggle]) {{ el.hidden = true; el.style.display = 'inline-block'; }}
            if (leg === 'undisplayed') for (const el of [t.x, t.toggle]) el.style.display = 'none';
            const inside = document.activeElement === gotIt(t);
            gotIt(t).click();
            const names = new Map([[t.x, 'x'], [t.toggle, 'toggle'], [t.h1, 'h1'], [document.body, 'body']]);
            return [inside, names.get(document.activeElement) ?? document.activeElement.tagName, view(t)];""")
        assert got[0] is True
        assert got[1] == expected
        assert got[2]["state"] == "done" and got[2]["cards"] == 0
        assert got[2]["calls"] == 1

    def test_escape_closes_from_anywhere(self, js):
        got = js(NEWS_JS + """
            const t = mk('still');
            await tick();
            t.x.focus();
            const key = (k) => document.body.dispatchEvent(new KeyboardEvent('keydown', { key: k, bubbles: true }));
            key('Enter');
            const other = [view(t).state, view(t).cards];
            key('Escape');
            return [other, view(t), document.activeElement === t.x];""")
        assert got[0] == ["card", 1]
        assert got[1]["state"] == "done" and got[1]["cards"] == 0
        assert got[2] is True

    def test_news_with_no_region_never_throws(self, js):
        got = js(NEWS_JS + """
            const out = {};
            for (const kind of ['none-live', 'none-still', 'still', 'live']) {
              const t = mk(kind, { noRegion: true });
              await tick();
              const boot = view(t);
              if (kind === 'live') mode(t, 'quilt');
              out[kind] = [boot.state, boot.calls, t.news.state, t.calls.n, view(t).cards,
                           document.querySelectorAll('.whatsnew-card').length];
            }
            document.body.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
            return out;""")
        assert got == {"none-live": ["none", 1, "none", 1, 0, 0], "none-still": ["none", 1, "none", 1, 0, 0],
                       "still": ["card", 1, "card", 1, 0, 0], "live": ["pending", 0, "card", 1, 0, 0]}


# --- The page shell: the empty polite region and the h1 as a focus target. ---

REGION_RE = re.compile(r"<(\w+)([^>]*\bdata-whatsnew\b[^>]*)>(.*?)</\1>", re.S)


class TestShell:
    def test_live_region_is_in_the_served_page_empty(self, make_page, base_url):
        page, errors = helpers.open_page(make_page, base_url)
        html = page.request.get(base_url + HOME).text()
        assert html.count("data-whatsnew") == 1
        found = REGION_RE.findall(html)
        assert len(found) == 1
        tag, attrs, content = found[0]
        assert 'aria-live="polite"' in attrs and content == ""
        got = page.evaluate("""() => { const r = document.querySelectorAll('[data-whatsnew]');
            return [r.length, r[0]?.childNodes.length, r[0]?.closest('[data-hero]') === null,
                    r[0] && getComputedStyle(r[0]).display, r[0]?.getAttribute('aria-live')]; }""")
        assert got == [1, 0, True, "block", "polite"]
        assert errors == []

    def test_h1_is_a_programmatic_focus_target(self, make_page, base_url):
        page, _ = helpers.open_page(make_page, base_url)
        assert page.get_attribute(".hero h1", "tabindex") == "-1"
        count = page.evaluate("""() => [...document.querySelectorAll('a[href], button:not([disabled]), [tabindex]')]
            .filter((el) => el.tabIndex >= 0 && el.getClientRects().length > 0).length""")
        assert count >= 5
        page.evaluate("() => document.activeElement?.blur()")
        seen = []
        for _ in range(count + 2):
            page.keyboard.press("Tab")
            seen.append(page.evaluate("() => document.activeElement.tagName.toLowerCase()"))
        assert "h1" not in seen and "a" in seen, seen
        page.evaluate("() => document.querySelector('.hero h1').focus()")
        assert page.evaluate("() => document.activeElement === document.querySelector('.hero h1')")


# --- Page scaffolding (TestStill, TestLive). ---

SHIPPED = (WEAVE / "public" / "panels.js").read_text(encoding="utf-8")
CARD = "[data-whatsnew] .whatsnew-card"
TRAVEL_DESKS = ["Travel", "Desk Allocation"]
SOURCE_LINK = ".site-nav a:last-child"


def mutated(js_text):
    """The shipped panels.js with a WEAVE_PANELS mutation appended (never spliced)."""
    return SHIPPED + "\n" + js_text + "\n"


# An init script: from the moment [data-hero] is parsed, every new data-release-state value is pushed to
# window.__release as { state, mode, events, hero }, read in the observer's callback, and only when it differs from
# the last one pushed.
RELEASE_LOG = r"""
    window.__release = [];
    new MutationObserver((_, outer) => {
      const el = document.querySelector('[data-hero]');
      if (!el) return;
      outer.disconnect();
      const push = () => {
        const state = el.dataset.releaseState ?? null;
        const last = window.__release[window.__release.length - 1];
        if (state === null || (last && last.state === state)) return;
        window.__release.push({ state, mode: el.__weave?.mode ?? null, events: (window.__modes || []).length,
                                hero: [el.dataset.heroState ?? null, el.dataset.heroReason ?? null] });
      };
      new MutationObserver(push).observe(el, { attributes: true, attributeFilter: ['data-release-state'] });
    }).observe(document, { childList: true, subtree: true });
"""

# Installed after boot, so it runs after the module's own weave:mode listener: every entry's dispatch-time mode with
# the release state and the event count then; and a rAF sampler of [__weave.mode, data-release-state].
ENTRY_LOG = r"""() => {
    const el = document.querySelector('[data-hero]');
    window.__entries = [];
    window.__frames = [];
    el.addEventListener('weave:mode', (e) => window.__entries.push(
      [e.detail.mode, el.dataset.releaseState ?? null, (window.__modes || []).length]));
    const sample = () => {
      window.__frames.push([el.__weave?.mode ?? null, el.dataset.releaseState ?? null]);
      requestAnimationFrame(sample);
    };
    requestAnimationFrame(sample);
}"""

CARD_READ = r"""() => {
    const cards = document.querySelectorAll('[data-whatsnew] .whatsnew-card');
    const c = cards[0];
    return [cards.length, c ? { heading: c.querySelector('.whatsnew-heading')?.textContent ?? null,
      versions: [...c.querySelectorAll('.whatsnew-version')].map((e) => e.textContent),
      names: [...c.querySelectorAll('.whatsnew-name')].map((e) => e.textContent) } : null];
}"""

# The close button's border against the card's background, as a contrast ratio.
BORDER_RATIO = r"""() => {
    const lum = (c) => {
      const [r, g, b] = c.match(/[\d.]+/g).slice(0, 3).map(Number).map((v) => {
        v /= 255;
        return v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
      });
      return 0.2126 * r + 0.7152 * g + 0.0722 * b;
    };
    const a = lum(getComputedStyle(document.querySelector('.whatsnew-close')).borderTopColor);
    const b = lum(getComputedStyle(document.querySelector('.whatsnew-card')).backgroundColor);
    return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
}"""

NO_ANIMATION = r"""() => ['.whatsnew-card', '[data-whatsnew]'].map((s) => {
    const st = getComputedStyle(document.querySelector(s));
    return [st.opacity, st.transitionDuration, st.animationName];
})"""


def card(page):
    """[count, {heading, versions, names} or None] for the card in the region."""
    return page.evaluate(CARD_READ)


def states(page):
    return [r["state"] for r in page.evaluate("window.__release")]


def stored(page):
    return page.evaluate("() => [localStorage.getItem('weave.lastSeenRelease.sim'),"
                         " localStorage.getItem('weave.lastSeenRelease')]")


def stage_data(page, name):
    return page.eval_on_selector("[data-hero]", f"el => el.dataset.{name} ?? null")


def focused_is(page, selector):
    return page.evaluate("(s) => document.activeElement === document.querySelector(s)", selector)


def open_still(make_page, base_url, query="", wait_card=True, **kwargs):
    """open_release (reduced motion) with RELEASE_LOG; waits for the card's one-task append when asked."""
    before = kwargs.pop("before_goto", None)

    def setup(page):
        page.add_init_script(RELEASE_LOG)
        if before is not None:
            before(page)

    page, errors, _ = helpers.open_release(make_page, base_url, query, before_goto=setup, **kwargs)
    if wait_card:
        page.wait_for_selector(CARD)
    return page, errors


def assert_sample_card(page):
    count, read = card(page)
    assert count == 1
    assert read == {"heading": RELEASE_TEXT, "versions": [], "names": TRAVEL_DESKS}
    assert stage_data(page, "newPanels") == "travel desks"
    assert stage_data(page, "releaseState") == "card"
    assert stored(page) == ["1.1", None]


def assert_card_contrast_and_focus(page):
    assert helpers.contrast_failures(page) == []
    page.evaluate("() => { document.querySelector('.whatsnew-heading').style.color = '#BBBBBB'; }")
    assert [f["text"] for f in helpers.contrast_failures(page)] == [RELEASE_TEXT]
    page.evaluate("() => { document.querySelector('.whatsnew-heading').style.color = ''; }")
    assert 'button "Got it"' in page.evaluate(helpers.FOCUS_TARGETS)
    assert helpers.focus_failures(page) == []


class TestStill:
    @pytest.mark.parametrize("path", ["still"])
    def test_sample_card_on_a_fresh_profile(self, make_page, base_url, path):
        page, errors = open_still(make_page, base_url, "?now=2026-10-10")
        assert_sample_card(page)
        assert errors == []

    @pytest.mark.parametrize("path", ["reduced-motion", "no-webgl"])
    def test_still_paths_show_the_card_at_once(self, make_page, base_url, browser_no_webgl, path):
        options = {} if path == "reduced-motion" else {"target_browser": browser_no_webgl,
                                                       "reduced_motion": "no-preference"}
        page, errors = open_still(make_page, base_url, "?now=2026-10-10", **options)
        assert states(page) == ["card"]
        assert helpers.hero_result(page) == ["still", path]
        assert stored(page)[0] == "1.1"
        assert errors == []

    def test_reload_shows_no_card_and_keeps_tags(self, make_page, base_url):
        page, _ = open_still(make_page, base_url, "?now=2026-10-10")
        assert stage_data(page, "releaseState") == "card"
        page.reload()
        page.wait_for_function(helpers.RELEASE_READY)
        assert stage_data(page, "releaseState") == "none"
        assert stage_data(page, "newPanels") == ""
        assert card(page) == [0, None]
        assert page.evaluate("() => document.querySelectorAll('li.panel.is-new').length") == 2

    def test_after_the_window_rule_b_writes_sim(self, make_page, base_url):
        page, errors = open_still(make_page, base_url, "?now=2026-10-20", wait_card=False)
        assert stage_data(page, "releaseState") == "none" and card(page) == [0, None]
        assert stored(page) == ["1.1", None]
        assert errors == []

    def test_whatsnew_before_the_window_shows_card_writes_nothing(self, make_page, base_url):
        page, _ = open_still(make_page, base_url, "?now=2026-10-08&whatsnew")
        assert stage_data(page, "releaseState") == "card"
        assert card(page)[1]["names"] == TRAVEL_DESKS
        assert page.evaluate("() => localStorage.length") == 0

    def test_no_card_and_no_write_at_the_fixed_instant(self, make_page, base_url):
        page, errors = open_still(make_page, base_url, wait_card=False)
        assert stage_data(page, "releaseState") == "none"
        assert stage_data(page, "newPanels") == ""
        assert page.evaluate("() => localStorage.length") == 0
        assert errors == []

    def test_markup_in_card_strings_stays_text(self, make_page, base_url):
        m = repr(MARKUP)
        body = mutated(f"window.WEAVE_PANELS.panels.find((p) => p.id === 'travel').name = {m};\n"
                       f"window.WEAVE_PANELS.release.label = {m};")
        page, _ = open_still(make_page, base_url, "?now=2026-10-10", panels_body=body)
        count, read = card(page)
        assert count == 1 and read["heading"] == f"New this release · v1.1 ({MARKUP})"
        assert read["names"] == [MARKUP, "Desk Allocation"]
        assert page.evaluate("() => document.querySelectorAll('[data-whatsnew] img').length") == 0
        assert page.evaluate("window.__pwned === undefined")
        assert page.evaluate("document.images.length") == 1

    def test_whatsnew_on_a_release_with_no_panels(self, make_page, base_url):
        body = mutated("window.WEAVE_PANELS.release = { version: '1.2', date: '2026-10-09' };")
        page, _ = open_still(make_page, base_url, "?now=2026-10-10&whatsnew", panels_body=body, wait_card=False)
        page.wait_for_timeout(100)
        assert states(page) == ["none"]
        assert card(page) == [0, None]

    def test_thirteenth_new_panel_is_on_the_card(self, make_page, base_url):
        body = mutated("window.WEAVE_PANELS.panels.push({ id: 'payroll', name: 'Payroll', status: 'live', "
                       "since: '1.1', sample: null, blurb: 'Pay.' });")
        page, _ = open_still(make_page, base_url, "?now=2026-10-10", panels_body=body)
        assert card(page)[1]["names"] == ["Travel", "Desk Allocation", "Payroll"]
        assert page.evaluate("() => [...document.querySelectorAll('li.panel.is-new .panel-name')]"
                             ".map((e) => e.textContent)") == ["Travel", "Desk Allocation", "Payroll"]

    def test_card_text_lands_in_the_live_region(self, make_page, base_url):
        tag = ("document.addEventListener('DOMContentLoaded', () => {"
               " document.querySelector('[data-whatsnew]').__atLoad = true; });")
        page, _ = open_still(make_page, base_url, "?now=2026-10-10", before_goto=lambda p: p.add_init_script(tag))
        got = page.evaluate("""() => { const r = document.querySelector('.whatsnew-card').closest('[data-whatsnew]');
            return [r?.getAttribute('aria-live'), r?.__atLoad === true]; }""")
        assert got == ["polite", True]

    def test_tab_moves_through_and_past_the_card(self, make_page, base_url):
        page, _ = open_still(make_page, base_url, "?now=2026-10-10")
        assert page.evaluate("() => document.activeElement === document.body")
        page.focus(SOURCE_LINK)
        page.keyboard.press("Tab")
        assert page.evaluate("() => document.activeElement.matches('.whatsnew-close')")
        page.keyboard.press("Tab")
        assert page.evaluate("""() => { const a = document.activeElement;
            return a !== document.body && !a.closest('.whatsnew-card'); }""")
        page.keyboard.press("Shift+Tab")
        page.keyboard.press("Shift+Tab")
        assert focused_is(page, SOURCE_LINK)

    @pytest.mark.parametrize("how", ["got-it-enter", "got-it-click", "escape-inside", "hidden"])
    def test_close_on_the_still(self, make_page, base_url, how):
        page, _ = open_still(make_page, base_url, "?now=2026-10-10")
        page.focus(SOURCE_LINK)
        page.focus(".whatsnew-close")
        if how == "hidden":
            page.evaluate("(s) => { document.querySelector(s).hidden = true; }", SOURCE_LINK)
        if how == "got-it-click":
            page.click(".whatsnew-close")
        else:
            page.keyboard.press("Escape" if how == "escape-inside" else "Enter")
        assert focused_is(page, ".hero h1" if how == "hidden" else SOURCE_LINK)
        assert stage_data(page, "releaseState") == "done"
        assert page.evaluate("() => document.querySelector('[data-whatsnew]').childNodes.length") == 0

    def test_escape_closes_when_focus_never_entered(self, make_page, base_url):
        page, _ = open_still(make_page, base_url, "?now=2026-10-10")
        assert card(page)[0] == 1
        page.keyboard.press("Escape")
        assert stage_data(page, "releaseState") == "done"
        assert card(page)[0] == 0
        assert page.evaluate("() => document.activeElement === document.body")

    @pytest.mark.parametrize("width", [390, 1440])
    def test_card_meets_contrast_and_focus(self, make_page, base_url, width):
        page, _ = open_still(make_page, base_url, "?now=2026-10-10", viewport={"width": width, "height": 844})
        assert_card_contrast_and_focus(page)
        assert page.evaluate(BORDER_RATIO) >= 3
        page.evaluate("() => { document.querySelector('.whatsnew-close').style.borderColor = '#E0D8C8'; }")
        assert page.evaluate(BORDER_RATIO) < 3

    @pytest.mark.parametrize("path", ["still"])
    def test_card_has_no_animation(self, make_page, base_url, path):
        page, _ = open_still(make_page, base_url, "?now=2026-10-10")
        assert page.evaluate(NO_ANIMATION) == [["1", "0s", "none"], ["1", "0s", "none"]]

    def test_missing_region_still_boots(self, make_page, base_url):
        remove = ("new MutationObserver(() => document.querySelector('[data-whatsnew]')?.remove())"
                  ".observe(document, { childList: true, subtree: true });")
        page, errors = open_still(make_page, base_url, "?now=2026-10-10", wait_card=False,
                                  before_goto=lambda p: p.add_init_script(remove))
        assert page.locator("[data-whatsnew]").count() == 0
        assert helpers.hero_result(page) == ["still", "reduced-motion"]
        assert stage_data(page, "releaseState") == "card"
        assert stored(page)[0] == "1.1"
        assert errors == []

    def test_no_horizontal_scroll_with_the_card(self, make_page, base_url):
        page, _ = open_still(make_page, base_url, "?now=2026-10-10", viewport={"width": 390, "height": 844})
        assert page.locator(CARD).is_visible()
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")

    def test_card_module_loads_without_three(self, make_page, base_url):
        requested = []
        open_still(make_page, base_url, "?now=2026-10-10",
                   before_goto=lambda p: p.on("request", lambda r: requested.append(r.url)))
        assert any(u.endswith("/js/whatsnew.js") for u in requested)
        assert not any("three.module" in u for u in requested)
