"""The Help page (#17): its shell, placeholder still, three help cards and the links site-config.js gives them."""
import json
from pathlib import Path

import pytest

from helpers import (CARD_KEYS, CARD_TITLES, FILLED_SITE, NOT_FOUND, SITE_SYNTAX_ERROR, contrast_failures,
                     focus_failures, ink_fraction, jpeg_size, open_help)
from test_config import BAD_LINKS

PUBLIC = Path(__file__).resolve().parents[1] / "public"
SOURCE = "https://github.com/mtibbits/weave-prototypes"
STAGE_LABEL = "A corner of the quilt coming apart, with loose threads, a needle and a spool of thread."


def test_help_still_is_1600_by_1000_and_at_most_250_kb():
    data = (PUBLIC / "assets" / "help-still.jpg").read_bytes()
    assert len(data) <= 250_000
    assert jpeg_size(data) == (1600, 1000)


def test_help_header_nav_pill_and_footer(make_page, base_url):
    page, _ = open_help(make_page, base_url)
    links = page.eval_on_selector_all(
        ".site-nav a", "els => els.map((a) => [a.textContent.trim(), a.getAttribute('href')])")
    assert links == [["What's in it", "../#panels"], ["Help", "./"], ["Coalesce", "../../coalesce/"],
                     ["Source", SOURCE]]
    assert page.locator("a.brand").get_attribute("href") == "../"
    assert page.locator(".pill").text_content().strip() == "Prototype · work in progress"
    footer = page.locator("footer")
    assert "Sample data only" in footer.inner_text()
    assert footer.locator(f'a[href="{SOURCE}"]').count() == 1
    assert footer.locator('a[href="../../"]').inner_text().strip() == "← All prototypes"


def test_help_nav_marks_the_current_page(make_page, base_url):
    page, _ = open_help(make_page, base_url)
    current = page.locator(".site-nav a[aria-current=page]")
    assert current.count() == 1
    assert current.inner_text().strip() == "Help" and current.get_attribute("href") == "./"


def test_help_copy(make_page, base_url):
    page, _ = open_help(make_page, base_url)
    assert page.locator("h1").inner_text() == "Coming apart at the seams?"
    assert page.locator(".lede").inner_text() == "Tell us what's wrong and we'll help put it right."
    cards = page.locator("a.card")
    assert cards.count() == 3
    assert cards.evaluate_all("els => els.map((el) => el.dataset.link)") == CARD_KEYS
    assert page.locator("a.card .card-title").all_inner_texts() == CARD_TITLES
    for i in range(3):
        card = cards.nth(i)
        assert card.locator(".card-text").inner_text().strip()
        assert card.locator("[data-cta]").count() == 1


def test_accessibility_basics(make_page, base_url):
    page, _ = open_help(make_page, base_url)
    assert page.locator("a.skip-link").get_attribute("href") == "#main"
    assert page.locator("main#main").count() == 1
    assert page.locator("h1").count() == 1
    stage = page.locator("[data-hero]")
    assert stage.get_attribute("role") == "img" and len(stage.get_attribute("aria-label")) > 40
    assert page.evaluate("[...document.images].every((i) => i.hasAttribute('alt'))")
    assert page.evaluate("document.images.length") == 1


def test_stage_holds_only_the_still(make_page, base_url):
    page, _ = open_help(make_page, base_url)
    stage = page.locator("[data-hero]")
    assert stage.get_attribute("aria-label") == STAGE_LABEL
    assert stage.evaluate("el => [...el.children].map((c) => c.tagName + '.' + c.className)") == ["IMG.hero-still"]
    still = stage.locator("img.hero-still")
    assert still.evaluate("img => [img.getAttribute('src'), img.getAttribute('alt'), img.getAttribute('fetchpriority'),"
                          " img.getAttribute('width'), img.getAttribute('height')]") == [
        "../assets/help-still.jpg", "", "high", "1600", "1000"]
    assert still.evaluate("img => [img.complete, img.naturalWidth, img.naturalHeight]") == [True, 1600, 1000]
    assert page.locator("[data-hero] :is(a, button, input, select, textarea, [tabindex])").count() == 0
    assert ink_fraction(stage.screenshot()) >= 0.05


@pytest.mark.parametrize("width", [390, 1440])
def test_help_stage_keeps_its_shape(make_page, base_url, width):
    page, _ = open_help(make_page, base_url, viewport={"width": width, "height": 844})
    box = page.locator("[data-hero]").bounding_box()
    assert box["width"] > 0 and abs(box["width"] / box["height"] - 1.6) < 0.01


@pytest.mark.parametrize("width", [390, 1440])
def test_no_horizontal_scroll(make_page, base_url, width):
    page, _ = open_help(make_page, base_url, viewport={"width": width, "height": 844})
    assert page.locator("[data-hero]").count() == 1  # the real page rendered (a 404 never scrolls sideways either)
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")


def test_page_loads_cleanly_with_its_fonts(make_page, base_url):
    page, errors = open_help(make_page, base_url)
    statuses = page.evaluate("""async () => {
        await Promise.all([...document.fonts].map((f) => f.load().catch(() => null)));
        return [...document.fonts].map((f) => f.status);
    }""")
    assert len(statuses) == 3 and set(statuses) == {"loaded"}
    assert errors == []


# --- The links (ACs 1-3): every test routes site-config.js, so none reads the committed values. ---

def test_filled_settings_wire_every_link(make_page, base_url):
    page, errors = open_help(make_page, base_url, site=FILLED_SITE)
    cards = page.locator("a.card")
    assert cards.count() == 3
    for i, key in enumerate(CARD_KEYS):
        assert cards.nth(i).get_attribute("href") == FILLED_SITE["links"][key]
    assert page.locator("a.card[aria-disabled], a.card.is-missing").count() == 0
    assert "Link coming soon" not in page.locator("[data-cta]").all_inner_texts()
    assert page.locator("footer [data-text=teamName]").inner_text() == "Workforce Systems"
    assert errors == []


def assert_all_missing(page):
    """Every card keeps its title and text, reads "Link coming soon", and is no link; the footer names the default
    team."""
    cards = page.locator("a.card")
    assert cards.count() == 3
    assert page.locator(".card.is-missing").count() == 3
    for i in range(3):
        card = cards.nth(i)
        assert card.locator(".card-title").inner_text() == CARD_TITLES[i]
        assert card.locator(".card-text").inner_text().strip()
        assert card.locator("[data-cta]").inner_text().strip() == "Link coming soon"
        assert card.get_attribute("href") is None
        assert card.get_attribute("aria-disabled") == "true"
    assert "maintained by the WEAVE team" in page.locator("footer").inner_text()


def test_empty_settings_show_link_coming_soon(make_page, base_url):
    page, errors = open_help(make_page, base_url)
    assert_all_missing(page)
    assert errors == []


@pytest.mark.parametrize("site", [SITE_SYNTAX_ERROR, NOT_FOUND], ids=["syntax", "missing"])
def test_broken_settings_file_degrades(make_page, base_url, site):
    page, errors = open_help(make_page, base_url, site=site)
    assert_all_missing(page)
    if site is SITE_SYNTAX_ERROR:
        # Only the routed syntax error itself escapes.
        assert len(errors) == 1 and errors[0].startswith("pageerror: "), errors
    else:
        console = [e for e in errors if e.startswith("console.error: ")]
        assert not [e for e in errors if e.startswith("pageerror: ")], errors
        assert console and all(e.startswith("console.error: Failed to load resource") for e in console), errors


@pytest.mark.parametrize("bad", BAD_LINKS)
def test_dropped_link_shows_link_coming_soon(make_page, base_url, bad):
    b = json.dumps(bad)
    body = f"window.WEAVE_SITE = {{teamName: '', links: {{serviceDesk: {b}, tutorial: {b}, docs: {b}}}}};"
    page, errors = open_help(make_page, base_url, site=body)
    assert_all_missing(page)
    assert errors == []


def test_markup_in_team_name_stays_text(make_page, base_url):
    markup = '<img src=x onerror="window.__pwned=1">'
    page, errors = open_help(make_page, base_url, site={**FILLED_SITE, "teamName": markup})
    assert page.locator("footer [data-text=teamName]").evaluate("el => el.textContent") == markup
    assert page.evaluate("document.images.length") == 1
    assert page.evaluate("window.__pwned") is None
    assert errors == []


# --- Card styles (#17, ACs 4 and 6): focus, contrast and hover. ---

CARD_FOCUS = r"""() => {
    const el = document.activeElement;
    const style = getComputedStyle(el);
    return [el.tagName, el.dataset.link ?? null, !!el.closest('.card'), style.outlineStyle,
            parseFloat(style.outlineWidth) || 0];
}"""


def tab_cycle(page, limit=40):
    """From the skip link, press Tab until focus wraps to BODY (headless Chromium wraps through it) or a card key
    repeats; returns [(link key, outline style, outline width, inside a card)] for each stop that is in a card."""
    page.focus("a.skip-link")
    seen, stops = set(), []
    for _ in range(limit):
        page.keyboard.press("Tab")
        tag, key, in_card, style, width = page.evaluate(CARD_FOCUS)
        if tag == "BODY" or (key is not None and key in seen):
            return stops
        if key is not None:
            seen.add(key)
        if key is not None or in_card:
            stops.append((key, style, width, in_card))
    raise AssertionError(f"Tab never wrapped to BODY in {limit} presses")


def test_tab_reaches_the_cards_in_order_with_an_outline(make_page, base_url):
    page, _ = open_help(make_page, base_url, site=FILLED_SITE)
    assert focus_failures(page) == []
    stops = tab_cycle(page)
    assert [key for key, *_ in stops] == CARD_KEYS
    for key, style, width, _ in stops:
        assert style != "none" and width >= 2, (key, style, width)


def test_missing_cards_take_no_focus(make_page, base_url):
    page, _ = open_help(make_page, base_url)
    assert page.locator(".card.is-missing").count() == 3
    assert tab_cycle(page) == []
    assert focus_failures(page) == []


# Coalesce's missing-link CONTRAST, with WEAVE's linen as the fallback background: a flat 4.5:1 for every text leaf in
# the missing-link subtree, which is the AC's question (helpers.contrast_failures asks it of the whole page).
MISSING_CONTRAST = r"""() => {
    const lum = (c) => {
      const [r, g, b] = c.match(/[\d.]+/g).slice(0, 3).map(Number).map((v) => {
        v /= 255;
        return v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
      });
      return 0.2126 * r + 0.7152 * g + 0.0722 * b;
    };
    const background = (el) => {
      for (let e = el; e; e = e.parentElement) {
        const c = getComputedStyle(e).backgroundColor;
        if (c !== 'transparent' && !c.startsWith('rgba(0, 0, 0, 0)')) return c;
      }
      return 'rgb(243, 238, 228)';
    };
    const opacity = (el) => {
      let o = 1;
      for (let e = el; e; e = e.parentElement) o *= Number(getComputedStyle(e).opacity);
      return o;
    };
    return [...document.querySelectorAll('.is-missing, .is-missing *')].filter((el) => el.childElementCount === 0
      && el.textContent.trim()).map((el) => {
      const a = lum(getComputedStyle(el).color);
      const b = lum(background(el));
      return { text: el.textContent.trim().slice(0, 40), opacity: opacity(el),
               ratio: (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05) };
    });
}"""


def test_missing_links_stay_readable(make_page, base_url):
    page, _ = open_help(make_page, base_url)
    texts = page.evaluate(MISSING_CONTRAST)
    assert len(texts) >= 9, texts  # 3 cards x title, text and CTA
    for item in texts:
        assert item["opacity"] == 1 and item["ratio"] >= 4.5, item


@pytest.mark.parametrize("width", [390, 1440])
def test_help_text_meets_contrast(make_page, base_url, width):
    page, _ = open_help(make_page, base_url, viewport={"width": width, "height": 844})
    assert contrast_failures(page) == []


CARD_COLORS = "el => { const s = getComputedStyle(el); return [s.borderTopColor, s.color]; }"


def test_missing_cards_do_not_react_to_hover(make_page, base_url):
    page, _ = open_help(make_page, base_url)
    cards = page.locator(".card.is-missing")
    assert cards.count() == 3
    for i in range(3):
        card = cards.nth(i)
        page.mouse.move(0, 0)
        before = card.evaluate(CARD_COLORS)
        card.hover()
        assert card.evaluate(CARD_COLORS) == before, i


def test_linked_card_reacts_to_hover(make_page, base_url):
    page, _ = open_help(make_page, base_url, site=FILLED_SITE)
    card = page.locator("a.card").first
    page.mouse.move(0, 0)
    before = card.evaluate("el => getComputedStyle(el).borderTopColor")
    card.hover()
    after = card.evaluate("el => getComputedStyle(el).borderTopColor")
    assert after == "rgb(29, 94, 91)" and after != before


# --- Both pages share the nav (#17, AC 5). ---

SHARED_LINKS = """() => [
    [...document.querySelectorAll('.site-nav a')].map((a) => [a.textContent.trim(), a.href]),
    document.querySelector('a.brand').href,
    [...document.querySelectorAll('footer a')].map((a) => [a.textContent.trim(), a.href]),
]"""


def test_both_pages_share_the_nav(make_page, base_url):
    home = make_page(reduced_motion="reduce")
    home.goto(base_url + "/public/")
    home.wait_for_load_state("networkidle")
    help_page, _ = open_help(make_page, base_url)
    home_links, help_links = home.evaluate(SHARED_LINKS), help_page.evaluate(SHARED_LINKS)
    assert home_links == help_links
    assert [text for text, _ in home_links[0]] == ["What's in it", "Help", "Coalesce", "Source"]
