"""fontsReady: the faces wait for the web fonts, and warn (rather than paint blank) when a font fails."""
import time

from helpers import canvas_hashes, collect_console, font_warnings, open_faces

SANS = "**/InstrumentSans.woff2"
SANS_SPEC = '700 48px "Instrument Sans"'

TILES_IMPORT = "const T = await import('/public/js/tiles.js');"


def test_fonts_ready_resolves_false_and_warns_when_no_face_is_declared(make_page, base_url):
    page = make_page()
    messages = collect_console(page)
    page.goto(f"{base_url}/tests/blank.html")
    ok = page.evaluate(f"async () => {{ {TILES_IMPORT} return await T.fontsReady(); }}")
    warnings = font_warnings(messages)
    assert ok is False
    assert len(warnings) == 3 and all("could not load" in w for w in warnings), warnings
    specs = page.evaluate(f"async () => {{ {TILES_IMPORT} return T.FONT_SPECS; }}")
    assert [w for spec in specs for w in warnings if f"font {spec} could" in w] == warnings


def test_fonts_ready_resolves_true_with_the_real_faces(paint_js):
    assert paint_js(f"{TILES_IMPORT} return await T.fontsReady();") is True
    assert font_warnings(paint_js.console) == []
    assert paint_js("return [...document.fonts].filter((f) => f.status === 'loaded').length;") >= 3


# --- The faces page under a slow, failed or never-arriving Sans (routes go in before navigation). ---
# A held font blocks the load event, so these tests navigate with wait_until="commit", and abort any route
# still held before the context closes.


def release(held):
    for route in held:
        try:
            route.abort()
        except Exception:  # noqa: BLE001 - already handled
            pass


def open_held(make_page, base_url, held, messages, clock=None, abort=False):
    """The faces page with Sans held (or aborted) by a route installed before navigation; returns (page, errors)."""
    def before_goto(page):
        if clock is not None:
            page.clock.set_fixed_time(clock)
        page.route(SANS, (lambda route: route.abort()) if abort else (lambda route: held.append(route)))

    return open_faces(make_page, base_url, wait_until="commit", wait_painted=False, before_goto=before_goto,
                      messages=messages)


def painted_after(page, start, timeout=10000):
    page.wait_for_selector("body[data-painted]", state="attached", timeout=timeout)
    return page.get_attribute("body", "data-painted"), time.monotonic() - start


def test_delayed_sans_gives_the_undelayed_hashes(make_page, base_url, faces_baseline):
    held, messages = [], []
    try:
        page, errors = open_held(make_page, base_url, held, messages)
        page.wait_for_timeout(1000)
        assert len(held) == 1 and page.get_attribute("body", "data-painted") is None
        held.pop().continue_()
        painted, _ = painted_after(page, time.monotonic())
        assert painted == "fonts"
        assert font_warnings(messages) == []
        assert canvas_hashes(page) == faces_baseline
        assert errors == []
    finally:
        release(held)


def test_aborted_sans_paints_in_the_fallback_with_a_warning(make_page, base_url, faces_baseline):
    messages = []
    start = time.monotonic()
    page, errors = open_held(make_page, base_url, [], messages, abort=True)
    painted, elapsed = painted_after(page, start)
    assert painted == "fallback" and elapsed < 3.5, elapsed
    warnings = font_warnings(messages)
    assert len(warnings) == 1 and f"font {SANS_SPEC} could not load" in warnings[0], warnings
    assert not any("had not loaded" in w for w in warnings)
    assert errors == ["console.error: Failed to load resource: net::ERR_FAILED"], errors
    hashes = canvas_hashes(page)
    assert sorted(hashes) == sorted(faces_baseline)
    for key, value in hashes.items():
        if key.startswith("face:"):
            assert value != faces_baseline[key], key
        if key.startswith("texture:"):
            assert value == faces_baseline[key], key


FIXED = "2026-10-09T09:00:00"


def test_frozen_date_and_held_sans_paint_after_the_timer(make_page, base_url):
    held, messages = [], []
    try:
        start = time.monotonic()
        page, errors = open_held(make_page, base_url, held, messages, clock=FIXED)
        painted, elapsed = painted_after(page, start)
        print(f"frozen-clock fallback after {elapsed:.2f} s")
        assert painted == "fallback" and 2.8 <= elapsed <= 6.0, elapsed
        warnings = font_warnings(messages)
        assert warnings == ["WEAVE: the web fonts had not loaded after 3 s, so the faces are painted in the "
                            "fallback font."], warnings
        assert len(held) == 1, "the held Sans request was fulfilled"
        fixed_ms = page.evaluate(f"() => new Date('{FIXED}').getTime()")
        assert page.evaluate("() => Date.now()") == fixed_ms
        assert not [e for e in errors if e.startswith("pageerror:")], errors
    finally:
        release(held)
