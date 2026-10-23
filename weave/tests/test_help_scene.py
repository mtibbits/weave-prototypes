"""The Help page's live corner (#18): the still path and its reasons, the boundary (no static Three, no panels.js),
going live, framing, the hooks, the loop, the stir, ?pose=rest and every runtime fallback."""
import re
from pathlib import Path

import pytest
from playwright.sync_api import TimeoutError as PWTimeout

from helpers import hero_result, hidden_by_attribute, open_help

PUBLIC = Path(__file__).resolve().parents[1] / "public"

SAVE_DATA = ("Object.defineProperty(navigator, 'connection', { configurable: true, "
             "get: () => ({ saveData: true }) });")


def assert_help_still(page):
    """The still is showing at full opacity, and nothing live is left: no canvas, the controls row and Pause hidden,
    no is-live and no data-fray-state. The opacity wait covers a fallback's fade back in."""
    still = page.locator("[data-hero] .hero-still")
    assert still.count() == 1 and still.is_visible()
    assert still.evaluate("img => [img.complete, img.naturalWidth]") == [True, 1600]
    try:
        page.wait_for_function("getComputedStyle(document.querySelector('[data-hero] .hero-still')).opacity === '1'",
                               timeout=3000)
    except PWTimeout as exc:
        raise AssertionError("the still never returned to full opacity") from exc
    assert page.locator("[data-hero] canvas").count() == 0
    controls = page.locator("[data-controls]")
    # Count guards first: a hidden check on a missing element would never get the chance to fail. The row keeps its
    # space where Pause could show (hover and a fine pointer), so it is hidden by visibility there, else by display.
    assert controls.count() == 1
    assert controls.evaluate("el => el.hidden === true && (getComputedStyle(el).display === 'none'"
                             " || getComputedStyle(el).visibility === 'hidden')") is True
    pause = page.locator("[data-pause]")
    assert pause.count() == 1 and hidden_by_attribute(pause)
    assert page.eval_on_selector("[data-hero]", "el => el.classList.contains('is-live')") is False
    assert page.eval_on_selector("[data-hero]", "el => el.hasAttribute('data-fray-state')") is False


LEFTOVERS = {
    "canvas": ("[data-hero]", "el => el.append(document.createElement('canvas'))"),
    "pause-shown": ("[data-pause]", "el => { el.hidden = false; }"),
    "unhidden-row": ("[data-controls]", "el => { el.hidden = false; }"),
    "fray-state": ("[data-hero]", "el => { el.dataset.frayState = 'frayed'; }"),
    "is-live": ("[data-hero]", "el => el.classList.add('is-live')"),
    # A still left faded out (the transition off, so the first poll cannot read the start of a fade).
    "still-faded": (".hero-still", "el => { el.style.transition = 'none'; el.style.opacity = '0'; }"),
}


@pytest.mark.parametrize("planted", list(LEFTOVERS))
def test_help_still_check_fails_on_a_live_leftover(make_page, base_url, planted):
    """Planted controls: every clause of assert_help_still can fail."""
    page, _ = open_help(make_page, base_url)
    assert hero_result(page) == ["still", "reduced-motion"]
    assert_help_still(page)  # the unplanted page passes
    selector, plant = LEFTOVERS[planted]
    page.locator(selector).evaluate(plant)
    with pytest.raises(AssertionError):
        assert_help_still(page)


def logged(requested):
    return lambda page: page.on("request", lambda request: requested.append(request.url))


def test_help_reduced_motion_keeps_still_and_skips_three(make_page, base_url):
    """AC 10, a port of test_hero.py's test_reduced_motion_keeps_still_and_skips_three."""
    requested = []
    page, errors = open_help(make_page, base_url, before_goto=logged(requested))
    assert hero_result(page) == ["still", "reduced-motion"]
    assert any(url.endswith("/public/js/help.js") for url in requested), requested  # the log sees modules
    assert not [url for url in requested if "three.module" in url], requested
    assert_help_still(page)
    assert errors == []


STILL_REASONS = {
    "no-webgl": {"no_webgl": True},
    "no-hover": {"viewport": {"width": 390, "height": 844}, "is_mobile": True, "has_touch": True},
    "save-data": {"init_script": SAVE_DATA},
}


@pytest.mark.parametrize("reason", list(STILL_REASONS))
def test_help_still_reasons_at_load(make_page, base_url, browser_no_webgl, reason):
    """AC 11's load-time reasons, each with motion allowed so reduced motion cannot win first."""
    args = dict(STILL_REASONS[reason])
    script = args.pop("init_script", None)
    if args.pop("no_webgl", False):
        args["target_browser"] = browser_no_webgl
    page, errors = open_help(make_page, base_url, reduced_motion="no-preference",
                             before_goto=(lambda p: p.add_init_script(script)) if script else None, **args)
    assert hero_result(page) == ["still", reason]
    assert_help_still(page)
    if reason == "no-webgl":
        assert page.locator("a.card").count() == 3
        assert all(page.locator("a.card").nth(i).is_visible() for i in range(3))
    assert errors == []


def test_help_never_requests_panels_js_on_the_still_path(make_page, base_url):
    """AC 12's still leg (the live leg is with the live tests)."""
    requested = []
    page, _ = open_help(make_page, base_url, before_goto=logged(requested))
    assert hero_result(page) == ["still", "reduced-motion"]
    assert any(url.endswith("/public/js/help.js") for url in requested), requested
    assert not [url for url in requested if url.endswith("/panels.js")], requested


# --- The boundary: help.js reaches Three only through import(). ---

STATIC_IMPORT = re.compile(r"""^\s*import\s+(?:[^'"]*?\s+from\s+)?['"]([^'"]+)['"]""", re.M)


def static_imports(text):
    code = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    code = re.sub(r"(?m)(^|\s)//[^\n]*", " ", code)
    return STATIC_IMPORT.findall(code)


def static_graph(start):
    """Every specifier statically reachable from public/js/<start>, and the modules visited."""
    seen, specifiers, todo = set(), set(), [start]
    while todo:
        name = todo.pop()
        if name in seen:
            continue
        seen.add(name)
        for spec in static_imports((PUBLIC / "js" / name).read_text(encoding="utf-8")):
            specifiers.add(spec)
            if spec.startswith("./"):
                todo.append(spec[2:])
    return seen, specifiers


def test_help_js_never_statically_reaches_three():
    seen, specifiers = static_graph("help.js")
    assert len(seen) >= 3 and {"eligibility.js", "dom.js"} <= seen, seen
    assert "three" not in specifiers, specifiers
    # Positive control: the same walk from scene.js does reach Three.
    assert "three" in static_graph("scene.js")[1]


def test_help_page_loads_help_js_with_an_import_map():
    html = (PUBLIC / "help" / "index.html").read_text(encoding="utf-8")
    assert '<script type="module" src="../js/help.js"></script>' in html
    assert re.search(r'"three"\s*:\s*"\.\./vendor/three/build/three\.module\.min\.js"', html)
    # The Pause row ships hidden, outside the stage, and reserves its space.
    assert re.search(r'<div class="hero-controls" data-controls data-reserve hidden>\s*<button class="hero-pause" '
                     r'type="button" data-pause aria-pressed="false" hidden>Pause motion</button>', html)
