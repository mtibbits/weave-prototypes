"""The Help page (#17): its shell, placeholder still, three help cards and the links site-config.js gives them."""
import json
from pathlib import Path

import pytest

from helpers import (CARD_KEYS, CARD_TITLES, FILLED_SITE, NOT_FOUND, SITE_SYNTAX_ERROR, ink_fraction, jpeg_size,
                     open_help)
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
