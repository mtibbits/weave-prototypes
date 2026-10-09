import json

import pytest

from helpers import FULL, collect_errors

PAGES = {"home": "/public/index.html", "help": "/public/help/index.html"}


def open_page(make_page, base_url, name, **context_args):
    page = make_page(**context_args)
    errors = collect_errors(page)
    page.goto(base_url + PAGES[name])
    page.wait_for_load_state("networkidle")
    return page, errors


@pytest.mark.parametrize("name", PAGES)
def test_page_loads_cleanly_with_its_fonts(make_page, base_url, name):
    page, errors = open_page(make_page, base_url, name)
    statuses = page.evaluate("""async () => {
        await Promise.all([...document.fonts].map((f) => f.load().catch(() => null)));
        return [...document.fonts].map((f) => f.status);
    }""")
    assert len(statuses) == 3 and set(statuses) == {"loaded"}
    assert errors == []


@pytest.mark.parametrize("name", PAGES)
def test_empty_settings_show_link_coming_soon(make_page, base_url, name):
    page, _ = open_page(make_page, base_url, name)
    links = page.eval_on_selector_all(
        "[data-link]", "els => els.map((e) => [e.getAttribute('href'), e.getAttribute('aria-disabled')])")
    assert links and all(href is None and disabled == "true" for href, disabled in links)
    assert page.locator("[data-cta]", has_text="Link coming soon").count() >= 3


@pytest.mark.parametrize("name", PAGES)
def test_filled_settings_wire_every_link(make_page, base_url, name):
    page = make_page()
    page.route("**/site-config.js", lambda route: route.fulfill(
        content_type="text/javascript", body=f"window.COALESCE_SITE = {json.dumps(FULL)};"))
    page.goto(base_url + PAGES[name])
    page.wait_for_load_state("networkidle")
    hrefs = page.eval_on_selector_all("[data-link]", "els => els.map((e) => e.getAttribute('href'))")
    assert hrefs and all(h and h.startswith("https://") for h in hrefs), hrefs
    assert page.locator("footer [data-text=teamName]").inner_text() == "Manpower Systems"


@pytest.mark.parametrize("name", PAGES)
@pytest.mark.parametrize("width", [390, 1440])
def test_no_horizontal_scroll(make_page, base_url, name, width):
    page, _ = open_page(make_page, base_url, name, viewport={"width": width, "height": 844})
    assert page.locator("[data-hero]").count() == 1  # the real page rendered (a 404 never scrolls sideways either)
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")


@pytest.mark.parametrize("name", PAGES)
def test_accessibility_basics(make_page, base_url, name):
    page, _ = open_page(make_page, base_url, name)
    assert page.locator("a.skip-link").get_attribute("href") == "#main"
    assert page.locator("main#main").count() == 1
    assert page.locator("h1").count() == 1
    stage = page.locator("[data-hero]")
    assert stage.get_attribute("role") == "img" and len(stage.get_attribute("aria-label")) > 40
    assert page.evaluate("[...document.images].every((i) => i.hasAttribute('alt'))")


def test_help_nav_marks_the_current_page(make_page, base_url):
    page, _ = open_page(make_page, base_url, "help")
    assert page.locator(".site-nav a[aria-current=page]").inner_text() == "Help"
    assert page.locator("a.brand").get_attribute("href") == "../"


def test_home_install_steps_in_order(make_page, base_url):
    page, _ = open_page(make_page, base_url, "home")
    assert page.locator("#install .steps li h3").all_inner_texts() == ["Download", "Unblock it", "Add it to Excel"]


CONTRAST = """() => {
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
      return 'rgb(244, 240, 232)';
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


@pytest.mark.parametrize("name", PAGES)
def test_missing_links_stay_readable(make_page, base_url, name):
    page, _ = open_page(make_page, base_url, name)
    texts = page.evaluate(CONTRAST)
    assert texts
    for item in texts:
        assert item["opacity"] == 1 and item["ratio"] >= 4.5, item


def test_missing_links_do_not_react_to_hover(make_page, base_url):
    page, _ = open_page(make_page, base_url, "home")
    link = page.locator(".site-nav a.is-missing").first
    colour = link.evaluate("el => getComputedStyle(el).color")
    link.hover()
    assert link.evaluate("el => getComputedStyle(el).color") == colour
    card = page.locator(".card.is-missing").first
    border = card.evaluate("el => getComputedStyle(el).borderTopColor")
    card.hover()
    assert card.evaluate("el => getComputedStyle(el).borderTopColor") == border
