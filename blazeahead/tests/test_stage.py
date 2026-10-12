import pytest

from helpers import collect_errors, stage_result

PAGES = {"home": "/public/index.html", "tour": "/public/tour/index.html", "help": "/public/help/index.html"}


def live_page(make_page, base_url, name, query="?nowatchdog", hash_="", **context_args):
    page = make_page(**context_args)
    errors = collect_errors(page)
    page.goto(base_url + PAGES[name] + query + hash_)
    return page, errors


def frames(page):
    return int(page.eval_on_selector("[data-stage]", "el => Number(el.dataset.stageFrames || 0)"))


@pytest.mark.parametrize("name", PAGES)
def test_pages_go_live_on_a_gpu(make_page, base_url, name):
    page, errors = live_page(make_page, base_url, name)
    assert stage_result(page, timeout=45000) == ["live", "ok"]
    first = frames(page)
    page.wait_for_timeout(800)
    assert frames(page) > first
    assert page.locator("[data-stage] canvas").count() == 1
    assert page.locator("[data-pause]").is_visible()
    assert errors == []


def test_a_slow_device_falls_back_to_the_still(make_page, base_url):
    page, _ = live_page(make_page, base_url, "home", query="?watchdogLimitMs=0.01")
    page.wait_for_function("() => document.querySelector('[data-stage]').dataset.stageReason === 'too-slow'",
                           timeout=45000)
    assert page.locator("[data-stage] canvas").count() == 0
    assert page.locator("[data-stage] img.stage-still").is_visible()
    assert page.locator("[data-pause]").is_hidden()


def test_reduced_motion_keeps_the_still(make_page, base_url):
    page, _ = live_page(make_page, base_url, "home", reduced_motion="reduce")
    assert stage_result(page) == ["still", "reduced-motion"]


def test_losing_the_gpu_mid_session_leaves_the_still(make_page, base_url):
    page, errors = live_page(make_page, base_url, "help")
    assert stage_result(page, timeout=45000) == ["live", "ok"]
    page.evaluate("document.querySelector('[data-stage]').__blaze.stop('context-lost')")
    assert page.eval_on_selector("[data-stage]", "el => [el.dataset.stageState, el.dataset.stageReason]") == [
        "still", "context-lost"]
    assert page.locator("[data-stage] canvas").count() == 0
    assert page.locator("[data-stage] img.stage-still").is_visible()
    assert errors == []


def test_pause_freezes_the_idle_motion(make_page, base_url):
    page, _ = live_page(make_page, base_url, "home")
    assert stage_result(page, timeout=45000) == ["live", "ok"]
    page.locator("[data-pause]").click()
    assert page.locator("[data-pause]").get_attribute("aria-pressed") == "true"
    held = frames(page)
    page.wait_for_timeout(600)
    assert frames(page) == held
    page.locator("[data-pause]").click()
    page.wait_for_timeout(600)
    assert frames(page) > held


@pytest.mark.parametrize("view", ["trailhead", "continuity", "scaffolding", "knowledge", "in-flight"])
def test_every_view_stays_within_the_triangle_budget(make_page, base_url, view):
    page, _ = live_page(make_page, base_url, "home")
    assert stage_result(page, timeout=45000) == ["live", "ok"]
    stats = page.evaluate(f"""async () => {{
        const s = document.querySelector('[data-stage]').__blaze;
        s.view.showView('{view}');
        await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
        return s.view.stats();
    }}""")
    assert 5_000 < stats["triangles"] <= 450_000, stats
    assert stats["calls"] <= 160, stats


def test_home_hover_parts_the_ferns_and_the_sign_leads_to_the_tour(make_page, base_url):
    page, _ = live_page(make_page, base_url, "home")
    assert stage_result(page, timeout=45000) == ["live", "ok"]
    box = page.locator("[data-stage]").bounding_box()
    page.mouse.move(box["x"] + box["width"] * 0.62, box["y"] + box["height"] * 0.86)
    page.wait_for_timeout(700)
    assert page.evaluate("document.querySelector('[data-stage]').__blaze.view.hoverActive") > 0
    sign = page.evaluate("document.querySelector('[data-stage]').__blaze.view.boxFor('trailhead', 'tour')")
    assert sign, "the trailhead sign should project into the stage"
    page.mouse.click((sign[0] + sign[2]) / 2, (sign[1] + sign[3]) / 2)
    page.wait_for_url("**/public/tour/**", timeout=10000)
