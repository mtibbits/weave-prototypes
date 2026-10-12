import json
import re
from pathlib import Path

import pytest

from helpers import FULL, collect_errors, stage_result

PAGES = {"home": "/public/index.html", "tour": "/public/tour/index.html", "help": "/public/help/index.html"}

TOUR_FILE = Path(__file__).resolve().parents[1] / "public" / "tour-content.js"


def with_tour_file(page, text):
    """Serve this text as tour-content.js, as if the owner had edited it."""
    page.route("**/tour-content.js", lambda route: route.fulfill(status=200, content_type="text/javascript", body=text))


def open_sheet(page):
    page.locator("[data-kb-unfold]").click()
    page.wait_for_function("() => document.querySelector('[data-kb-sheet]').open")


def open_page(make_page, base_url, name, target_browser=None, hash_="", settle=True, **context_args):
    page = make_page(target_browser, **context_args)
    errors = collect_errors(page)
    page.goto(base_url + PAGES[name] + hash_)
    page.wait_for_load_state("networkidle")
    if settle:
        stage_result(page)
    return page, errors


def tour_index(page):
    return int(page.eval_on_selector("body", "b => b.dataset.tourIndex"))


def wait_stop(page, index):
    page.wait_for_function("(i) => document.body.dataset.tourIndex === String(i)"
                           " && document.body.dataset.tourWalking === 'false'", arg=index, timeout=15000)


# ---------------------------------------------------------------- every page

@pytest.mark.parametrize("name", PAGES)
def test_page_loads_cleanly_as_a_still_without_webgl(make_page, browser_no_webgl, base_url, name):
    page, errors = open_page(make_page, base_url, name, browser_no_webgl)
    assert stage_result(page) == ["still", "no-webgl"]
    page.wait_for_function("() => { const img = document.querySelector('[data-stage] img:not(.is-hidden)');"
                           " return img && img.complete && img.naturalWidth === 1600; }", timeout=10000)
    statuses = page.evaluate("""async () => {
        await Promise.all([...document.fonts].map((f) => f.load().catch(() => null)));
        return [...document.fonts].map((f) => f.status);
    }""")
    assert len(statuses) == 3 and set(statuses) == {"loaded"}
    assert errors == []


@pytest.mark.parametrize("name", PAGES)
def test_empty_settings_show_link_coming_soon(make_page, browser_no_webgl, base_url, name):
    page, _ = open_page(make_page, base_url, name, browser_no_webgl)
    links = page.eval_on_selector_all(
        "[data-link]", "els => els.map((e) => [e.getAttribute('href'), e.getAttribute('aria-disabled')])")
    assert links and all(href is None and disabled == "true" for href, disabled in links)
    assert page.locator("[data-cta]", has_text="Link coming soon").count() >= 1


@pytest.mark.parametrize("name", PAGES)
def test_filled_settings_wire_every_link(make_page, browser_no_webgl, base_url, name):
    page = make_page(browser_no_webgl)
    page.route("**/site-config.js", lambda route: route.fulfill(
        content_type="text/javascript", body=f"window.BLAZEAHEAD_SITE = {json.dumps(FULL)};"))
    page.goto(base_url + PAGES[name])
    page.wait_for_load_state("networkidle")
    hrefs = page.eval_on_selector_all("[data-link]", "els => els.map((e) => e.getAttribute('href'))")
    assert hrefs and all(h and h.startswith("https://") for h in hrefs), hrefs
    if name != "tour":
        assert page.locator("footer [data-text=teamName]").inner_text() == "Developer Tools"


@pytest.mark.parametrize("name", PAGES)
@pytest.mark.parametrize("size", [(1024, 768), (1440, 900), (2560, 1080)])
def test_no_horizontal_scroll(make_page, browser_no_webgl, base_url, name, size):
    page, _ = open_page(make_page, base_url, name, browser_no_webgl, viewport={"width": size[0], "height": size[1]})
    assert page.locator("[data-stage]").count() == 1
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")


@pytest.mark.parametrize("name", PAGES)
def test_accessibility_basics(make_page, browser_no_webgl, base_url, name):
    page, _ = open_page(make_page, base_url, name, browser_no_webgl)
    assert page.locator("h1").count() == 1
    assert page.locator("header").count() >= 1 and page.locator("main").count() == 1
    assert page.locator("a.skip-link").count() == 1
    unlabeled = page.eval_on_selector_all(
        "button", "els => els.filter((b) => !(b.getAttribute('aria-label') || b.textContent.trim())).length")
    assert unlabeled == 0
    missing_alt = page.eval_on_selector_all("img", "els => els.filter((i) => !i.hasAttribute('alt')).length")
    assert missing_alt == 0
    assert page.get_attribute("html", "lang") == "en"


# ---------------------------------------------------------------- home and help

def test_home_offers_download_tour_and_install_steps(make_page, browser_no_webgl, base_url):
    page, _ = open_page(make_page, base_url, "home", browser_no_webgl)
    assert re.sub(r"\s+", " ", page.locator("h1").inner_text()) == "Find the trail. Keep it lit."
    hero = page.locator(".hero")
    assert hero.locator("a[data-link=download]").count() == 1
    assert hero.locator("a", has_text="Take the tour").get_attribute("href") == "tour/"
    steps = page.locator("#install ol.steps > li")
    assert steps.count() == 3
    assert "Install from VSIX" in steps.nth(1).inner_text()
    assert page.locator("[data-requires=version]").first.is_hidden()


def test_help_cards_point_the_three_ways(make_page, browser_no_webgl, base_url):
    page = make_page(browser_no_webgl)
    page.route("**/site-config.js", lambda route: route.fulfill(
        content_type="text/javascript", body=f"window.BLAZEAHEAD_SITE = {json.dumps(FULL)};"))
    page.goto(base_url + PAGES["help"])
    page.wait_for_load_state("networkidle")
    cards = page.locator(".help-cards .card")
    assert cards.count() == 3
    assert cards.nth(0).get_attribute("href") == FULL["links"]["issues"]
    assert cards.nth(1).get_attribute("href") == FULL["links"]["docs"]
    assert cards.nth(2).get_attribute("href") == "../tour/"
    assert re.sub(r"\s+", " ", page.locator("h1").inner_text()) == "Which way from here?"


# ---------------------------------------------------------------- the tour, as stills

def test_tour_without_a_hash_opens_stop_one(make_page, browser_no_webgl, base_url):
    page, errors = open_page(make_page, base_url, "tour", browser_no_webgl)
    wait_stop(page, 0)
    assert page.evaluate("location.hash") == "#continuity"
    assert page.locator("[data-card-heading]").inner_text() == "The continuity proxy"
    assert page.locator("[data-card-eyebrow]").text_content() == "Stop 1 of 4"
    assert page.locator("button[data-sign=left]").get_attribute("aria-label") == "Back: Trailhead"
    assert page.locator("button[data-sign=right]").get_attribute("aria-label") == "Next: Scaffolding"
    assert errors == []


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


def test_tour_keys_walk_on_and_leave_at_both_ends(make_page, browser_no_webgl, base_url):
    page, _ = open_page(make_page, base_url, "tour", browser_no_webgl, hash_="#knowledge")
    wait_stop(page, 2)
    page.keyboard.press("ArrowRight")
    wait_stop(page, 3)
    assert page.evaluate("location.hash") == "#in-flight"
    assert page.locator("button[data-sign=right]").get_attribute("aria-label") == "Next: Download"
    page.keyboard.press("ArrowRight")
    page.wait_for_url(re.compile(r"/public/(index\.html)?#install$"))
    page.goto(base_url + PAGES["tour"] + "#continuity")
    wait_stop(page, 0)
    page.keyboard.press("ArrowLeft")
    page.wait_for_url(re.compile(r"/public/(index\.html)?$"))


def test_tour_escape_goes_home(make_page, browser_no_webgl, base_url):
    page, _ = open_page(make_page, base_url, "tour", browser_no_webgl, hash_="#scaffolding")
    wait_stop(page, 1)
    page.keyboard.press("Escape")
    page.wait_for_url(re.compile(r"/public/(index\.html)?$"))


def test_tour_signs_trail_map_unknown_hash_and_back_button(make_page, browser_no_webgl, base_url):
    page, _ = open_page(make_page, base_url, "tour", browser_no_webgl, hash_="#foo")
    wait_stop(page, 0)
    assert page.evaluate("location.hash") == "#continuity"
    page.locator("button[data-sign=right]").click()
    wait_stop(page, 1)
    page.locator("nav[data-trail-map] button[data-goto='3']").click()
    wait_stop(page, 3)
    assert page.locator("nav[data-trail-map] button[aria-current=step]").get_attribute("data-goto") == "3"
    page.go_back()
    wait_stop(page, 1)
    assert page.evaluate("location.hash") == "#scaffolding"


def test_tour_survives_a_missing_content_file(make_page, browser_no_webgl, base_url):
    page = make_page(browser_no_webgl)
    errors = collect_errors(page)
    page.route("**/tour-content.js", lambda route: route.abort())
    page.goto(base_url + PAGES["tour"] + "#in-flight")
    wait_stop(page, 3)
    assert page.locator("[data-card-heading]").inner_text() == "The In Flight queue"
    assert page.locator("nav[data-trail-map] button").count() == 6
    assert not [e for e in errors if "pageerror" in e]


@pytest.mark.parametrize("size", [(1024, 768), (1440, 900), (2560, 1080)])
def test_tour_sign_buttons_stay_on_screen(make_page, browser_no_webgl, base_url, size):
    page, _ = open_page(make_page, base_url, "tour", browser_no_webgl, hash_="#in-flight",
                        viewport={"width": size[0], "height": size[1]})
    wait_stop(page, 3)
    for side in ("left", "right"):
        box = page.locator(f"button[data-sign={side}]").bounding_box()
        assert box and box["width"] > 20 and box["height"] > 10, (side, box)
        assert box["x"] >= 0 and box["y"] >= 0, (side, box)
        assert box["x"] + box["width"] <= size[0] and box["y"] + box["height"] <= size[1], (side, box)


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


SHEET_FIT = """() => {
    const d = document.querySelector('[data-kb-sheet]');
    const map = d.querySelector('.kb-sheet-map');
    const box = (el) => { const r = el.getBoundingClientRect(); return { top: r.top, bottom: r.bottom, width: r.width }; };
    return { svg: box(map.querySelector('svg')), map: box(map), head: box(d.querySelector('h2')),
             close: box(d.querySelector('[data-kb-close]')), view: innerHeight,
             dialogScroll: [d.scrollHeight, d.clientHeight], mapScroll: [map.scrollHeight, map.clientHeight] };
}"""


def test_the_unfolded_map_fits_a_desktop_window_whole(make_page, browser_no_webgl, base_url):
    page, _ = open_page(make_page, base_url, "tour", browser_no_webgl, hash_="#knowledge")
    wait_stop(page, 2)
    open_sheet(page)
    f = page.evaluate(SHEET_FIT)
    assert f["svg"]["width"] >= 960, f
    assert f["svg"]["bottom"] <= f["map"]["bottom"] + 0.5 and f["svg"]["bottom"] <= f["view"], f
    assert f["mapScroll"][0] <= f["mapScroll"][1] + 1 and f["dialogScroll"][0] <= f["dialogScroll"][1] + 1, f


@pytest.mark.parametrize("size", [(1536, 730), (1366, 657)])
def test_on_a_laptop_only_the_unfolded_map_scrolls(make_page, browser_no_webgl, base_url, size):
    page, _ = open_page(make_page, base_url, "tour", browser_no_webgl, hash_="#knowledge",
                        viewport={"width": size[0], "height": size[1]})
    wait_stop(page, 2)
    open_sheet(page)
    f = page.evaluate(SHEET_FIT)
    for part in ("head", "close"):
        assert f[part]["top"] >= 0 and f[part]["bottom"] <= f["view"], (part, f)
    assert f["dialogScroll"][0] <= f["dialogScroll"][1] + 1, f
    assert f["svg"]["width"] >= 960, f


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


def test_the_map_cannot_be_unfolded_mid_walk(make_page, browser_no_webgl, base_url):
    page, _ = open_page(make_page, base_url, "tour", browser_no_webgl, hash_="#knowledge")
    wait_stop(page, 2)
    page.locator("[data-kb-unfold]").focus()
    page.keyboard.press("ArrowRight")
    page.keyboard.press("Enter")
    wait_stop(page, 3)
    page.wait_for_timeout(200)
    assert not page.evaluate("document.querySelector('[data-kb-sheet]').open")


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


# the words of trail k on the still's map (names over 32 characters are cut on the map), and which of them the card hides
LIT_TRAIL_UNDER_THE_CARD = """(k) => {
    const t = window.__tour.tour.stops[2].map.trails[k];
    const cut = (n) => (n.length > 32 ? `${n.slice(0, 31).trimEnd()}…` : n);
    const names = new Set([t.name, ...t.destinations.flatMap((d) => [d.name, ...d.next.map((e) => e.name)])].map(cut));
    const card = document.querySelector('[data-tour-card]').getBoundingClientRect();
    const texts = [...document.querySelectorAll('[data-kb-overlay] svg text')].filter((x) => names.has(x.textContent));
    return { found: texts.length, want: names.size, cardTop: Math.round(card.top),
             hidden: texts.map((x) => [x.textContent, Math.round(x.getBoundingClientRect().bottom)])
               .filter(([, bottom]) => bottom >= card.top) };
}"""


def step_to_trail(page, k):
    """From the overview, page on to trail k's card page and wait for the still's map to light that trail."""
    page.locator("[data-card-next]").click()
    color = page.evaluate("(k) => ['#2F6FA3', '#B8452A', '#3E7D4C', '#74509C', '#A0721A'][k]", k)
    page.wait_for_function("(c) => document.querySelector(`[data-kb-overlay] svg feDropShadow[flood-color='${c}']`)",
                           arg=color)


@pytest.mark.parametrize("size", [(1536, 730), (1280, 720)])
def test_on_short_windows_the_card_leaves_the_lit_trail_in_view(make_page, browser_no_webgl, base_url, size):
    page, _ = open_page(make_page, base_url, "tour", browser_no_webgl, hash_="#knowledge",
                        viewport={"width": size[0], "height": size[1]})
    wait_stop(page, 2)
    page.wait_for_function("() => !document.querySelector('[data-kb-overlay]').hidden")
    page.wait_for_timeout(400)      # the card's slide-in
    for k in range(5):
        step_to_trail(page, k)
        r = page.evaluate(LIT_TRAIL_UNDER_THE_CARD, k)
        assert r["found"] == r["want"], (k, r)
        assert r["hidden"] == [], (size, k, r)


def test_on_a_short_laptop_window_the_trail_cards_do_not_scroll(make_page, browser_no_webgl, base_url):
    page, _ = open_page(make_page, base_url, "tour", browser_no_webgl, hash_="#knowledge",
                        viewport={"width": 1366, "height": 657})
    wait_stop(page, 2)
    for k in range(5):
        page.locator("[data-card-next]").click()
        sizes = page.eval_on_selector("[data-tour-card]", "c => [c.scrollHeight, c.clientHeight]")
        assert sizes[0] <= sizes[1] + 1, (k, sizes)
