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
