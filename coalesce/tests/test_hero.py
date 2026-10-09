import pytest

from helpers import collect_errors, hero_result, ink_fraction

HOME = "/public/index.html"
HELP = "/public/help/index.html"


def frames(page):
    return page.eval_on_selector("[data-hero]", "el => Number(el.dataset.heroFrames || 0)")


def wait_for_intro(page):
    page.wait_for_function(
        "() => (document.querySelector('[data-hero]').__coalesce?.sim.clock || 0) > 4", timeout=30000)


@pytest.mark.parametrize("url", [HOME, HELP])
def test_goes_live_on_desktop(make_page, base_url, url):
    page = make_page()
    errors = collect_errors(page)
    page.goto(f"{base_url}{url}?nowatchdog")
    assert hero_result(page) == ["live", "ok"]
    assert page.locator("[data-hero] canvas").count() == 1
    assert page.locator("[data-pause]").is_visible()
    first = frames(page)
    page.wait_for_timeout(600)
    assert frames(page) > first
    assert errors == []


def test_pause_stops_and_resumes_rendering(make_page, base_url):
    page = make_page()
    page.goto(f"{base_url}{HOME}?nowatchdog")
    assert hero_result(page) == ["live", "ok"]
    pause = page.locator("[data-pause]")
    pause.click()
    assert pause.get_attribute("aria-pressed") == "true" and pause.inner_text() == "Play motion"
    page.wait_for_timeout(200)
    stopped_at = frames(page)
    clock = page.eval_on_selector("[data-hero]", "el => el.__coalesce.sim.clock")
    page.wait_for_timeout(800)
    assert frames(page) == stopped_at
    pause.click()
    page.wait_for_timeout(600)
    assert frames(page) > stopped_at
    resumed_clock = page.eval_on_selector("[data-hero]", "el => el.__coalesce.sim.clock")
    assert resumed_clock - clock < 1.0  # continues from where it stopped, no jump


def test_reduced_motion_keeps_still_and_skips_three(make_page, base_url):
    page = make_page(reduced_motion="reduce")
    requested = []
    page.on("request", lambda request: requested.append(request.url))
    page.goto(f"{base_url}{HOME}")
    assert hero_result(page) == ["still", "reduced-motion"]
    page.wait_for_load_state("networkidle")
    assert not any("three.module" in url or "coalesce.glb" in url for url in requested)
    assert page.locator("[data-hero] canvas").count() == 0
    assert page.locator(".hero-still").is_visible()
    assert page.locator("[data-pause]").is_hidden()


def test_touch_device_keeps_still(make_page, base_url):
    page = make_page(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
    page.goto(f"{base_url}{HOME}")
    assert hero_result(page) == ["still", "no-hover"]


def test_no_webgl_keeps_still(make_page, base_url, browser_no_webgl):
    page = make_page(target_browser=browser_no_webgl)
    page.goto(f"{base_url}{HOME}")
    assert hero_result(page) == ["still", "no-webgl"]


def test_asset_failure_keeps_still(make_page, base_url):
    page = make_page()
    errors = collect_errors(page)
    page.route("**/coalesce.glb", lambda route: route.abort())
    page.goto(f"{base_url}{HOME}?nowatchdog")
    assert hero_result(page) == ["still", "load-failed"]
    assert page.locator(".hero-still").is_visible()
    assert not [e for e in errors if e.startswith("pageerror")]


def test_slow_machine_falls_back(make_page, base_url):
    page = make_page()
    page.goto(f"{base_url}{HOME}?watchdogLimitMs=0")
    page.wait_for_function(
        "document.querySelector('[data-hero]').dataset.heroReason === 'too-slow'", timeout=20000)
    assert page.locator("[data-hero] canvas").count() == 0
    assert page.locator("[data-pause]").is_hidden()
    assert page.locator(".hero-still").is_visible()


def test_home_hover_parts_people_and_click_scatters_them(make_page, base_url):
    page = make_page()
    page.goto(f"{base_url}{HOME}?nowatchdog")
    assert hero_result(page) == ["live", "ok"]
    wait_for_intro(page)
    box = page.locator("[data-hero]").bounding_box()
    x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    page.mouse.move(x, y)
    page.wait_for_timeout(1500)
    moved = page.eval_on_selector("[data-hero]", """el => Math.max(...el.__coalesce.sim.tokens
        .filter((t) => t.mode === 'home')
        .map((t) => Math.hypot(t.p[0] - t.home[0], t.p[1] - t.home[1], t.p[2] - t.home[2])))""")
    assert moved > 0.25
    page.mouse.click(x, y)
    page.wait_for_timeout(100)
    bursting = page.eval_on_selector("[data-hero]", "el => el.__coalesce.sim.tokens.filter((t) => t.mode === 'burst').length")
    assert bursting > 50


def test_help_magnifier_follows_the_pointer_and_highlights_one_person(make_page, base_url):
    page = make_page()
    page.goto(f"{base_url}{HELP}?nowatchdog")
    assert hero_result(page) == ["live", "ok"]
    wait_for_intro(page)
    box = page.locator("[data-hero]").bounding_box()
    page.mouse.move(box["x"] + box["width"] * 0.40, box["y"] + box["height"] * 0.45)
    page.wait_for_timeout(1500)
    first = page.eval_on_selector("[data-hero]", """el => {
        const { sim, aim } = el.__coalesce;
        return { focus: sim.focusIndex, pos: aim.pos.slice(), target: aim.target.slice(),
                 terra: sim.tokens.filter((t) => t.colT[0] > t.colT[1]).length };
    }""")
    assert first["focus"] >= 0 and first["terra"] == 1
    assert abs(first["pos"][0] - first["target"][0]) < 0.1 and abs(first["pos"][1] - first["target"][1]) < 0.1
    page.mouse.move(box["x"] + box["width"] * 0.62, box["y"] + box["height"] * 0.70)
    page.wait_for_timeout(1500)
    second = page.eval_on_selector("[data-hero]", "el => el.__coalesce.sim.focusIndex")
    assert second >= 0 and second != first["focus"]


def test_help_has_no_arrivals_or_departures(make_page, base_url):
    page = make_page()
    page.goto(f"{base_url}{HELP}?nowatchdog")
    assert hero_result(page) == ["live", "ok"]
    page.wait_for_timeout(8000)
    modes = page.eval_on_selector("[data-hero]", "el => [...new Set(el.__coalesce.sim.tokens.map((t) => t.mode))]")
    assert set(modes) <= {"home", "intro"}


def test_paused_hero_redraws_after_a_resize(make_page, base_url):
    page = make_page()
    page.goto(f"{base_url}{HOME}?nowatchdog")
    assert hero_result(page) == ["live", "ok"]
    wait_for_intro(page)
    page.locator("[data-pause]").click()
    page.set_viewport_size({"width": 820, "height": 900})  # narrow enough that the stage itself shrinks
    page.wait_for_timeout(600)
    box = page.locator("[data-hero]").bounding_box()
    clip = {"x": box["x"] + box["width"] * 0.3, "y": box["y"] + box["height"] * 0.3,
            "width": box["width"] * 0.4, "height": box["height"] * 0.4}
    assert ink_fraction(page.screenshot(clip=clip)) > 0.05
