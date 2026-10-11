"""The load-time half of the hero contract: the still path, the desktop positive control and load-failed."""
from helpers import HOME, collect_errors, hero_result, hidden_by_attribute, ink_fraction

STILL_HINT = "Your browser shows a picture of the quilt. The panels below have everything."
THREE_FAILED = "WEAVE: Three.js could not load, so the still image stays."


def assert_still_page(page):
    """The still is showing, both lists rendered, the still hint is written and the controls row is hidden."""
    still = page.locator(".hero-still")
    assert still.is_visible()
    assert still.evaluate("img => [img.complete, img.naturalWidth]") == [True, 1600]
    assert page.locator('[data-list="live"] li.panel').count() == 7
    assert page.locator('[data-list="planned"] li.panel').count() == 4
    assert page.locator("[data-hint]").text_content() == STILL_HINT
    controls = page.locator("[data-controls]")
    # Count guard first: hidden_by_attribute on a missing element would never get the chance to fail.
    assert controls.count() == 1 and hidden_by_attribute(controls)


def test_reduced_motion_keeps_still_and_skips_three(make_page, base_url):
    page = make_page(reduced_motion="reduce")
    requested = []
    page.on("request", lambda request: requested.append(request.url))
    page.goto(f"{base_url}{HOME}")
    assert hero_result(page) == ["still", "reduced-motion"]
    page.wait_for_load_state("networkidle")
    assert not any("three.module" in url for url in requested)
    assert_still_page(page)


def test_no_webgl_keeps_still(make_page, base_url, browser_no_webgl):
    page = make_page(target_browser=browser_no_webgl)
    page.goto(f"{base_url}{HOME}")
    assert hero_result(page) == ["still", "no-webgl"]
    page.wait_for_load_state("networkidle")
    assert_still_page(page)


def test_touch_device_keeps_still(make_page, base_url):
    page = make_page(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
    page.goto(f"{base_url}{HOME}")
    assert hero_result(page) == ["still", "no-hover"]
    page.wait_for_load_state("networkidle")
    assert_still_page(page)


def test_desktop_requests_three_and_stays_loading(make_page, base_url):
    """The positive control for the still path: the same page on desktop does request Three.js."""
    page = make_page()
    errors = collect_errors(page)
    with page.expect_request("**/three.module.min.js"):
        page.goto(f"{base_url}{HOME}")
    # Same module record as main.js's import, so a failed load surfaces here rather than after the asserts.
    assert page.evaluate("() => import('three').then(() => 'ok')") == "ok"
    page.wait_for_load_state("networkidle")
    stage = page.locator("[data-hero]")
    assert stage.evaluate("el => [el.dataset.heroState, el.dataset.heroReason]") == ["still", "loading"]
    assert page.locator("[data-hint]").text_content() == ""
    assert page.locator(".hero-still").is_visible()
    assert errors == []
    assert ink_fraction(stage.screenshot()) > 0.3


def test_three_load_failure_keeps_still(make_page, base_url):
    page = make_page()
    errors = collect_errors(page)
    warnings = []
    page.on("console", lambda msg: warnings.append(msg.text) if msg.type == "warning" else None)
    page.route("**/three.module.min.js", lambda route: route.abort())
    page.goto(f"{base_url}{HOME}")
    assert hero_result(page) == ["still", "load-failed"]
    assert page.locator("[data-hint]").text_content() == STILL_HINT
    assert page.locator(".hero-still").is_visible()
    assert not [e for e in errors if e.startswith("pageerror")]
    # The browser appends the error object to the console text, so pin the message as a prefix.
    assert len([w for w in warnings if w.startswith(THREE_FAILED)]) == 1, warnings


def test_controls_check_fails_when_the_row_is_unhidden(make_page, base_url):
    """Planted control: a controls row that shows must fail assert_still_page's check."""
    page = make_page(reduced_motion="reduce")
    page.goto(f"{base_url}{HOME}")
    hero_result(page)
    controls = page.locator("[data-controls]")
    controls.evaluate("el => { el.hidden = false; }")
    assert not hidden_by_attribute(controls)
