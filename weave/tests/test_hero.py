"""The hero contract: the still path and its reasons, going live on desktop, the hooks, and every runtime fallback."""
import pytest

from helpers import (DEFAULT_IDS, HOME, LOAD_FAILED, PAUSE_NAME, QUILT_HINT, SEW_NAME, STILL_HINT, TILES_HINT,
                     UNSTITCH_NAME, WEBGL_FAILED, collect_errors, frames, hero_result, hidden_by_attribute, ink_fraction,
                     open_live, rising, wait_for_reason, weave)


def assert_still_page(page):
    """The still is showing, both lists rendered, the still hint is written, and nothing live is left: no canvas,
    Pause, the toggle and the controls row hidden, no is-live and no data-mode."""
    still = page.locator(".hero-still")
    assert still.is_visible()
    assert still.evaluate("img => [img.complete, img.naturalWidth]") == [True, 1600]
    assert page.locator('[data-list="live"] li.panel').count() == 7
    assert page.locator('[data-list="planned"] li.panel').count() == 4
    assert page.locator("[data-hint]").text_content() == STILL_HINT
    controls = page.locator("[data-controls]")
    # Count guard first: hidden_by_attribute on a missing element would never get the chance to fail.
    assert controls.count() == 1 and hidden_by_attribute(controls)
    assert page.locator("[data-hero] canvas").count() == 0
    pause = page.locator("[data-pause]")
    assert pause.count() == 1 and pause.evaluate("el => el.hidden") is True
    toggle = page.locator("[data-toggle]")
    assert toggle.count() == 1 and toggle.evaluate("el => el.hidden") is True
    assert page.eval_on_selector("[data-hero]", "el => el.classList.contains('is-live')") is False
    assert page.eval_on_selector("[data-hero]", "el => el.hasAttribute('data-mode')") is False


def warnings_of(page):
    warnings = []
    page.on("console", lambda msg: warnings.append(msg.text) if msg.type == "warning" else None)
    return warnings


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


def test_goes_live_on_desktop(make_page, base_url):
    """Port of coalesce/tests/test_hero.py::test_goes_live_on_desktop, with the first-frame mark and a non-blank
    canvas (control: the same stage with the canvas hidden)."""
    page, errors = open_live(make_page, base_url)
    canvas = page.locator("[data-hero] canvas")
    assert canvas.count() == 1 and canvas.get_attribute("aria-hidden") == "true"
    assert page.locator("[data-pause]").is_visible()
    assert rising(page)
    assert page.evaluate("performance.getEntriesByName('weave:first-live-frame', 'mark').length") == 1
    assert page.eval_on_selector("[data-hero]", "el => el.classList.contains('is-live')") is True
    page.wait_for_function("getComputedStyle(document.querySelector('.hero-still')).opacity === '0'", timeout=5000)
    stage = page.locator("[data-hero]")
    live = ink_fraction(stage.screenshot())
    canvas.evaluate("el => { el.style.visibility = 'hidden'; }")
    control = ink_fraction(stage.screenshot())
    print(f"ink live={live:.4f} control={control:.4f}")
    assert live >= 0.05 and live >= 3 * control
    assert errors == []


def test_pause_sits_in_the_controls_row_not_the_stage(make_page, base_url):
    page, _ = open_live(make_page, base_url)
    pause = page.get_by_role("button", name=PAUSE_NAME)
    assert pause.count() == 1
    assert pause.evaluate("el => el.closest('[data-hero]') === null") is True
    assert pause.evaluate("el => el.closest('[data-controls]') !== null") is True


def test_hooks_describe_the_drawn_quilt(make_page, base_url):
    page, _ = open_live(make_page, base_url)
    assert weave(page, ".mode") == "quilt"
    assert weave(page, ".order") == DEFAULT_IDS
    slots = weave(page, ".slots")
    assert slots[0] == {"id": "manpower", "name": "Manpower", "status": "live", "face": "sewn"}
    assert slots[4]["face"] == "planned" and slots[11]["face"] == "suggest"
    # Copies: a caller's edit never reaches the page's state.
    assert page.eval_on_selector("[data-hero]", "el => { el.__weave.order[0] = 'x'; el.__weave.slots[0].id = 'x';"
                                 " return [el.__weave.order[0], el.__weave.slots[0].id]; }") == ["manpower", "manpower"]
    clock = weave(page, ".clock")
    page.wait_for_timeout(300)
    assert weave(page, ".clock") > clock


READ_HOOKS = "const { readHooks } = await import('/public/js/dom.js');"


def test_read_hooks_parses_the_url(js):
    r = js(READ_HOOKS + r"""
        return ['', '?watchdogLimitMs=0', '?watchdogLimitMs=', '?watchdogLimitMs=abc', '?nowatchdog',
                '?pose=rest&frame=still'].map((q) => { const h = readHooks(q); return [h.watchdog, String(h.limitMs), h.rest, h.still]; });
    """)
    assert r == [
        [True, "45", False, False],
        [True, "0", False, False],
        [True, "0", False, False],
        [True, "NaN", False, False],
        [False, "45", False, False],
        [True, "45", True, True],
    ]


FILL_SLOTS = r"""
    const { fillSlots } = await import('/public/js/dom.js');
    const entry = (i) => ({ id: `p${i}`, name: `P${i}`, status: 'live', sample: null });
    const ids = (slots) => slots.map((s) => (s === null ? null : s.id));
"""


def test_fill_slots(js):
    r = js(FILL_SLOTS + r"""
        const ten = Array.from({ length: 10 }, (_, i) => entry(i));
        const thirteen = Array.from({ length: 13 }, (_, i) => entry(i));
        const invalid = [entry(0), { id: '', name: 'bad', status: 'live' }, entry(2)];
        return { ten: ids(fillSlots(ten)), thirteen: ids(fillSlots(thirteen)), broken: ids(fillSlots(undefined)),
                 object: ids(fillSlots({})), invalid: ids(fillSlots(invalid)) };
    """)
    assert r["ten"] == [f"p{i}" for i in range(10)] + [None, None]
    assert r["thirteen"] == [f"p{i}" for i in range(12)]
    assert r["broken"] == [None] * 12 and r["object"] == [None] * 12
    assert r["invalid"] == ["p0", "p2"] + [None] * 10


def test_default_watchdog_stays_live(make_page, base_url):
    """The production configuration (w202): no query at all, so the real watchdog rules."""
    page, errors = open_live(make_page, base_url, query="")
    page.wait_for_timeout(2000)
    before = frames(page)
    page.wait_for_timeout(1000)
    assert hero_result(page) == ["live", "ok"]
    assert frames(page) > before
    assert errors == []


# Makes the sashing's canvas (#6's sashingSize(LAYOUT), 1204 x 912) refuse a context, so buildQuilt throws after
# createRenderer has succeeded.
SASHING_THROWS = r"""
    const original = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = function (...args) {
      if (this.width === 1204 && this.height === 912) throw new Error('planted: paintSashing fails');
      return original.apply(this, args);
    };
"""

# U4: a WebGL context is refused only to the stage's (aria-hidden) canvas, so readEnvironment's probe still passes.
NO_STAGE_WEBGL = r"""
    const original = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = function (type, ...args) {
      if (/webgl/.test(type) && this.getAttribute('aria-hidden') === 'true') return null;
      return original.call(this, type, ...args);
    };
"""


def open_desktop(make_page, base_url, query="?nowatchdog", init_script=None, route=None):
    page = make_page()
    errors = collect_errors(page)
    warnings = warnings_of(page)
    if init_script:
        page.add_init_script(init_script)
    if route:
        page.route(route, lambda r: r.abort())
    page.goto(f"{base_url}{HOME}{query}")
    return page, errors, warnings


def prefixed(warnings, prefix):
    # The browser appends the error object to the console text, so pin the message as a prefix.
    return [w for w in warnings if w.startswith(prefix)]


def test_quilt_build_failure_keeps_still(make_page, base_url):
    page, errors, warnings = open_desktop(make_page, base_url, init_script=SASHING_THROWS)
    wait_for_reason(page, "load-failed")
    assert hero_result(page) == ["still", "load-failed"]
    assert_still_page(page)
    assert len(prefixed(warnings, LOAD_FAILED)) == 1, warnings
    assert not [e for e in errors if e.startswith("pageerror")]


def test_slow_machine_falls_back(make_page, base_url):
    """Port of coalesce/tests/test_hero.py::test_slow_machine_falls_back."""
    page, _, _ = open_desktop(make_page, base_url, query="?watchdogLimitMs=0")
    wait_for_reason(page, "too-slow")
    assert hero_result(page) == ["still", "too-slow"]
    assert_still_page(page)


def test_scene_module_failure_keeps_still(make_page, base_url):
    """Port of coalesce/tests/test_hero.py::test_asset_failure_keeps_still."""
    page, errors, warnings = open_desktop(make_page, base_url, route="**/js/scene.js")
    wait_for_reason(page, "load-failed")
    assert hero_result(page) == ["still", "load-failed"]
    assert_still_page(page)
    assert len(prefixed(warnings, LOAD_FAILED)) == 1, warnings
    assert not [e for e in errors if e.startswith("pageerror")]


def test_three_load_failure_keeps_still(make_page, base_url):
    page, errors, warnings = open_desktop(make_page, base_url, route="**/three.module.min.js")
    wait_for_reason(page, "load-failed")
    assert hero_result(page) == ["still", "load-failed"]
    assert_still_page(page)
    assert not [e for e in errors if e.startswith("pageerror")]
    assert len(prefixed(warnings, LOAD_FAILED)) == 1, warnings


def test_context_loss_falls_back(make_page, base_url):
    page, errors = open_live(make_page, base_url)
    page.eval_on_selector("[data-hero] canvas", "c => c.getContext('webgl2').getExtension('WEBGL_lose_context').loseContext()")
    wait_for_reason(page, "context-lost")
    assert hero_result(page) == ["still", "context-lost"]
    assert_still_page(page)
    assert errors == []


def test_webgl_setup_failure_falls_back(make_page, base_url):
    page, errors, warnings = open_desktop(make_page, base_url, init_script=NO_STAGE_WEBGL)
    wait_for_reason(page, "webgl-failed")
    assert hero_result(page) == ["still", "webgl-failed"]
    assert_still_page(page)
    assert errors == ["console.error: THREE.WebGLRenderer: Error creating WebGL context."]
    assert len(prefixed(warnings, WEBGL_FAILED)) == 1, warnings


def test_stop_hook_tears_down_once(make_page, base_url):
    page, errors = open_live(make_page, base_url)
    page.eval_on_selector("[data-hero]", "el => { el.__weave.stop('context-lost'); el.__weave.stop('too-slow'); }")
    assert hero_result(page) == ["still", "context-lost"]
    assert_still_page(page)
    held = frames(page)
    clock = weave(page, ".clock")
    page.wait_for_timeout(600)
    assert frames(page) == held and weave(page, ".clock") == clock
    assert weave(page, ".mode") == "quilt"  # the hook outlives the teardown
    assert errors == []


LEFTOVERS = {
    "unhidden-row": ("[data-controls]", "el => { el.hidden = false; }"),
    "canvas-left": ("[data-hero]", "el => el.append(document.createElement('canvas'))"),
    "toggle-shown": ("[data-toggle]", "el => { el.hidden = false; }"),
    "data-mode-left": ("[data-hero]", "el => { el.dataset.mode = 'quilt'; }"),
}


@pytest.mark.parametrize("planted", list(LEFTOVERS))
def test_still_check_fails_on_a_live_leftover(make_page, base_url, planted):
    """Planted controls: a controls row or toggle that shows, a canvas left in the stage, or a data-mode left on it
    must fail assert_still_page."""
    page = make_page(reduced_motion="reduce")
    page.goto(f"{base_url}{HOME}")
    hero_result(page)
    selector, plant = LEFTOVERS[planted]
    page.locator(selector).evaluate(plant)
    with pytest.raises(AssertionError):
        assert_still_page(page)


DOM_JS = "const D = await import('/public/js/dom.js'); const { MODES } = await import('/public/js/motion.js');"


def test_toggle_label_names_the_next_press(js):
    r = js(DOM_JS + "return MODES.map((m) => [m, D.toggleLabel(m), D.liveHint(m)]);")
    sew = {"unstitching", "tiles"}
    assert [m for m, _, _ in r] == ["intro", "quilt", "unstitching", "tiles", "restitching", "sewing"]
    for mode, label, hint in r:
        assert label == (SEW_NAME if mode in sew else UNSTITCH_NAME), mode
        assert hint == (TILES_HINT if mode in sew else QUILT_HINT), mode


def test_set_hero_state_writes_the_live_hint(js):
    r = js(DOM_JS + r"""
        const stage = document.createElement('div'); const hint = document.createElement('p');
        return [['live', 'ok'], ['still', 'loading'], ['still', 'too-slow']].map(([state, reason]) => {
          D.setHeroState(stage, hint, state, reason);
          return hint.textContent;
        });
    """)
    assert r == [QUILT_HINT, "", STILL_HINT]


def test_set_toggle_and_data_mode_write_their_targets(js):
    r = js(DOM_JS + r"""
        const stage = document.createElement('div'); const button = document.createElement('button');
        const hint = document.createElement('p');
        D.setToggle(button, hint, 'unstitching');
        const pressed = [button.textContent, hint.textContent];
        D.setDataMode(stage, 'tiles');
        const set = stage.getAttribute('data-mode');
        D.setDataMode(stage, null);
        return { pressed, set, cleared: stage.hasAttribute('data-mode') };
    """)
    assert r == {"pressed": [SEW_NAME, TILES_HINT], "set": "tiles", "cleared": False}


def test_set_toggle_keeps_an_unchanged_hint(js):
    """The hint is aria-live: a settle that keeps its text (unstitching -> tiles) must not write it again."""
    r = js(DOM_JS + r"""
        const button = document.createElement('button'); const hint = document.createElement('p');
        D.setToggle(button, hint, 'unstitching');
        const seen = new MutationObserver(() => {});
        seen.observe(hint, { childList: true, characterData: true, subtree: true });
        D.setToggle(button, hint, 'tiles');
        const settle = seen.takeRecords().length;
        D.setToggle(button, hint, 'restitching');
        return { settle, press: seen.takeRecords().length > 0, text: hint.textContent };
    """)
    assert r == {"settle": 0, "press": True, "text": QUILT_HINT}


def test_quilt_hint_mentions_dragging(js):
    assert "drag a tile to move it" in js(DOM_JS + "return D.QUILT_HINT;")


@pytest.mark.parametrize("width", [360, 768, 1440])
def test_hint_height_is_steady_across_modes(make_page, base_url, width):
    """#9's longer quilt hint must not make the page jump when the hint changes on unstitch."""
    page, errors = open_live(make_page, base_url, query="?pose=rest&nowatchdog", viewport={"width": width, "height": 800})
    height = "() => document.querySelector('.hero-hint').getBoundingClientRect().height"
    quilt = page.evaluate(height)
    page.get_by_role("button", name=UNSTITCH_NAME, exact=True).click()
    page.wait_for_function("() => document.querySelector('[data-hero]').dataset.mode === 'tiles'", timeout=10000)
    tiles = page.evaluate(height)
    assert abs(quilt - tiles) <= 0.5, (quilt, tiles)
    assert errors == []


@pytest.mark.parametrize("width", [360, 1440])
def test_still_hint_keeps_one_line_of_room(make_page, base_url, width):
    """The still hint never changes, so the still path keeps one line of reserved room; only live grows it (#9)."""
    page = make_page(reduced_motion="reduce", viewport={"width": width, "height": 800})
    page.goto(f"{base_url}{HOME}")
    assert hero_result(page) == ["still", "reduced-motion"]
    assert page.eval_on_selector(".hero-hint", "el => getComputedStyle(el).minHeight") == "23.25px"
