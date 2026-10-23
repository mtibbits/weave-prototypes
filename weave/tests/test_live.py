"""The live loop: Pause and Play, the one clock, and idling when the tab is hidden or the stage is off screen."""
from helpers import (RESIZE_AND_READ, SET_HIDDEN, contrast_failures, corner_z, focus_failures, frames, ink_fraction,
                     live_quilt, open_live, rising, weave)

FIXED = "2026-10-09T09:00:00"

# Records __weave.lastDt at the first counted frame after this call (frame() sets lastDt before data-hero-frames).
WATCH_NEXT_FRAME = r"""el => {
    window.__nextDt = null;
    const observer = new MutationObserver(() => { window.__nextDt = el.__weave.lastDt; observer.disconnect(); });
    observer.observe(el, { attributes: true, attributeFilter: ['data-hero-frames'] });
}"""

def test_pause_freezes_motion_and_play_resumes_without_a_jump(make_page, base_url):
    """Port of coalesce/tests/test_hero.py::test_pause_stops_and_resumes_rendering, plus the AC's frozen pose."""
    page, errors = open_live(make_page, base_url)
    assert rising(page, 300)  # w193: the loop really ran before Pause
    pause = page.locator("[data-pause]")
    pause.click()
    assert pause.get_attribute("aria-pressed") == "true" and pause.inner_text() == "Play motion"
    page.wait_for_timeout(200)
    held = (frames(page), weave(page, ".clock"), corner_z(page, 0), corner_z(page, 8))
    page.wait_for_timeout(800)
    assert (frames(page), weave(page, ".clock"), corner_z(page, 0), corner_z(page, 8)) == held
    page.eval_on_selector("[data-hero]", WATCH_NEXT_FRAME)
    pause.click()
    assert pause.get_attribute("aria-pressed") == "false" and pause.inner_text() == "Pause motion"
    page.wait_for_timeout(600)
    assert frames(page) > held[0]
    assert weave(page, ".clock") - held[1] < 1.0
    first_dt = page.evaluate("window.__nextDt")
    assert first_dt is not None and first_dt <= 1 / 30
    assert errors == []


def test_paused_quilt_redraws_after_a_resize(make_page, base_url):
    """Port of coalesce/tests/test_hero.py::test_paused_hero_redraws_after_a_resize (U6: alpha keeps an undrawn
    canvas transparent, so a missing redraw reads as paper)."""
    page, _ = open_live(make_page, base_url)
    page.locator("[data-pause]").click()
    page.wait_for_timeout(200)
    stage = page.locator("[data-hero]")
    before = (stage.bounding_box()["width"], page.eval_on_selector("[data-hero] canvas", "c => c.width"))
    held = frames(page)
    page.set_viewport_size({"width": 820, "height": 900})
    page.wait_for_timeout(600)
    box = stage.bounding_box()
    after = (box["width"], page.eval_on_selector("[data-hero] canvas", "c => c.width"))
    assert after[0] != before[0] and after[1] != before[1]  # the stage and its buffer really changed
    assert frames(page) == held
    clip = {"x": box["x"] + box["width"] * 0.3, "y": box["y"] + box["height"] * 0.3,
            "width": box["width"] * 0.4, "height": box["height"] * 0.4}
    assert ink_fraction(page.screenshot(clip=clip)) > 0.05


def test_live_resize_redraws_before_the_frame_paints(make_page, base_url):
    """A resize while the loop runs lands after that frame's render; without a redraw the cleared canvas would paint
    as bare paper, so the quilt flickers on every resize step."""
    page, errors = live_quilt(make_page, base_url)
    assert rising(page, 300)
    r = page.eval_on_selector("[data-hero]", RESIZE_AND_READ)
    assert r["after"] != r["before"]  # the buffer really was resized, and so cleared
    assert r["ink"] > 0.3, r
    assert errors == []


def test_hidden_tab_stops_the_loop(make_page, base_url):
    page, errors = open_live(make_page, base_url)
    assert rising(page, 300)
    held = page.evaluate(SET_HIDDEN, True)
    pose = corner_z(page, 8)
    page.wait_for_timeout(1000)
    assert frames(page) == held and corner_z(page, 8) == pose
    page.evaluate(SET_HIDDEN, False)
    page.wait_for_timeout(600)
    assert frames(page) > held
    assert errors == []


def test_off_screen_stage_idles(make_page, base_url):
    page, _ = open_live(make_page, base_url, viewport={"width": 1440, "height": 500})
    assert rising(page, 300)
    page.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)")
    page.wait_for_timeout(300)
    assert page.eval_on_selector("[data-hero]", "el => el.getBoundingClientRect().bottom") <= 0
    held = frames(page)
    page.wait_for_timeout(800)
    assert frames(page) == held
    page.locator("[data-hero]").scroll_into_view_if_needed()
    page.wait_for_timeout(600)
    assert frames(page) > held


def test_frozen_date_keeps_frames_and_sway(make_page, base_url):
    """The one-clock AC's page leg: Date is frozen, and the loop still runs and the quilt still sways."""
    page, errors = open_live(make_page, base_url, before_goto=lambda p: p.clock.set_fixed_time(FIXED))
    assert rising(page)
    pose = corner_z(page, 8)
    page.wait_for_timeout(1000)
    assert corner_z(page, 8) != pose
    assert page.evaluate(f"Date.now() === new Date('{FIXED}').getTime()") is True
    assert errors == []


def test_live_controls_are_focusable_and_readable(make_page, base_url):
    page, _ = open_live(make_page, base_url)
    assert page.locator("[data-pause]").is_visible()
    assert focus_failures(page) == []
    assert contrast_failures(page) == []
