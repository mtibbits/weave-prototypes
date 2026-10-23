"""The Help page's live corner (#18): the still path and its reasons, the boundary (no static Three, no panels.js),
going live, framing, the hooks, the loop, the stir, ?pose=rest and every runtime fallback."""
import re
from pathlib import Path

import pytest
from playwright.sync_api import TimeoutError as PWTimeout

from helpers import (CLOCK_ADVANCE, HELP, HELP_LOAD_FAILED, RESIZE_AND_READ, SET_HIDDEN, STRANDS_JSON, WEBGL_FAILED,
                     collect_warnings, frames, help_hook, sweep, hero_result, hidden_by_attribute, ink_fraction, open_help,
                     open_help_live, rising, wait_for_reason)
from test_hero import NO_STAGE_WEBGL, SASHING_THROWS

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


# --- Going live: the corner, its framing and its hooks. ---


def test_help_goes_live_on_desktop(make_page, base_url):
    """AC 1, a port of test_hero.py's test_goes_live_on_desktop. The pinned clock empties the performance timeline,
    so this runs on the real clock (Issue-12/16)."""
    page, errors = open_help_live(make_page, base_url, clock=None)
    canvas = page.locator("[data-hero] canvas")
    assert canvas.count() == 1 and canvas.get_attribute("aria-hidden") == "true"
    pause = page.locator("[data-pause]")
    assert pause.count() == 1 and pause.is_visible()
    assert pause.evaluate("el => el.closest('[data-hero]') === null") is True
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


# Projects every framing point through the hook: the edge at u = 0, 0.1, ..., 1, every strand point and the eight
# corners of the needle's and the spool's world boxes; returns them with the canvas's client rect.
FRAMING = r"""async (el) => {
    const THREE = await import('three');
    const h = el.__weaveHelp;
    const corners = (obj) => {
      const b = new THREE.Box3().setFromObject(obj, true);
      const out = [];
      for (const x of [b.min.x, b.max.x]) for (const y of [b.min.y, b.max.y]) for (const z of [b.min.z, b.max.z]) out.push([x, y, z]);
      return out;
    };
    const edge = Array.from({ length: 11 }, (_, i) => h.edge.getPointAt(i / 10).toArray());
    const points = [...edge, ...h.fray.strands.flatMap((s) => s.points), ...corners(h.needle), ...corners(h.spool)];
    const r = el.querySelector('canvas').getBoundingClientRect();
    return { rect: [r.left, r.top, r.right, r.bottom], projected: points.map((p) => h.project(p)),
             edge: edge.map((p) => h.project(p)) };
}"""


@pytest.mark.parametrize("pose", ["rest", "idle"])
def test_help_scene_stays_in_the_canvas(make_page, base_url, pose):
    """AC 2 at 1440 x 900: at ?pose=rest, and after 3 s of idle without it, every framing point projects inside the
    canvas. Tightness control: the edge spans at least 40% of the canvas width, so a whole-quilt fit fails."""
    query = "?pose=rest&nowatchdog" if pose == "rest" else "?nowatchdog"
    page, errors = open_help_live(make_page, base_url, query=query)
    if pose == "idle":
        page.wait_for_timeout(3000)
    r = page.eval_on_selector("[data-hero]", FRAMING)
    left, top, right, bottom = r["rect"]
    assert len(r["projected"]) == 11 + 160 + 16
    outside = [(i, p) for i, p in enumerate(r["projected"]) if not (left <= p[0] <= right and top <= p[1] <= bottom)]
    assert outside == [], (r["rect"], outside)
    span = max(p[0] for p in r["edge"]) - min(p[0] for p in r["edge"])
    assert span >= 0.4 * (right - left), (span, r["rect"])
    assert errors == []


def test_help_hook_shape_and_fray_state(make_page, base_url):
    """AC 14: stage.__weaveHelp's fields, the props' children and data-fray-state."""
    page, errors = open_help_live(make_page, base_url)
    r = page.eval_on_selector("[data-hero]", r"""el => {
        const h = el.__weaveHelp;
        const f = h.fray;
        const names = (o) => o.children.map((c) => c.name);
        return { keys: Object.keys(h), getPointAt: typeof h.edge.getPointAt, stop: typeof h.stop,
                 project: typeof h.project, needle: names(h.needle), spool: names(h.spool),
                 strands: f.strands.map((s) => s.points.length),
                 sizes: [...new Set(f.strands.flatMap((s) => s.points.map((p) => p.length)))],
                 hanging: f.strands.map((s) => s.hanging), frayAmount: f.frayAmount, state: f.state,
                 clock: typeof f.clock, stir: f.stir, frayState: el.dataset.frayState,
                 tail: h.needle.getObjectByName('tail').material.color.getHexString(),
                 thread: h.spool.getObjectByName('thread').material.color.getHexString() };
    }""")
    assert {"fray", "stop", "project", "edge", "needle", "spool"} <= set(r["keys"]), r["keys"]
    assert r["getPointAt"] == "function" and r["stop"] == "function" and r["project"] == "function"
    assert {"body", "tail"} <= set(r["needle"]) and r["spool"] == ["spool", "thread"]
    assert r["strands"] == [16] * 10 and r["sizes"] == [3]
    assert r["hanging"] == [1] * 10 and r["frayAmount"] == 1 and r["state"] == "frayed"
    assert r["clock"] == "number" and r["stir"] is None
    assert r["frayState"] == "frayed"
    assert r["tail"] == r["thread"] == "c9a227"
    assert errors == []


# Geometry and material ids are global counters (test_needle.py's probe): a gap of 1 across a second of frames means
# no frame built anything.
ID_PROBE = ("async () => { const T = await import('three');"
            " return [new T.BufferGeometry().id, new T.MeshBasicMaterial().id]; }")


def test_help_fringe_is_painted_once_and_frames_allocate_no_geometry(make_page, base_url):
    """U3 and the incremental-fringe rule: a second of frames paints and uploads nothing new and builds no geometry;
    a frayAmount change moves only the threshold."""
    page, errors = open_help_live(make_page, base_url)
    assert rising(page, 300)
    before = page.evaluate(ID_PROBE)
    fringe = help_hook(page, ".fringe")
    page.wait_for_timeout(1000)
    after = page.evaluate(ID_PROBE)
    held = help_hook(page, ".fringe")
    assert after == [before[0] + 1, before[1] + 1], (before, after)
    assert fringe["paints"] == 1 and held == fringe, (fringe, held)
    page.eval_on_selector("[data-hero]", "el => { el.__weaveHelp.fray.frayAmount = 0.5; }")
    page.wait_for_timeout(200)
    half = help_hook(page, ".fringe")
    assert half["threshold"] != fringe["threshold"] and 0 < half["threshold"] <= 1, (fringe, half)
    assert (half["paints"], half["textureVersion"], half["materialVersion"]) == (
        fringe["paints"], fringe["textureVersion"], fringe["materialVersion"])
    assert errors == []


def test_help_fringe_keeps_its_threshold_for_a_bad_fray_amount(make_page, base_url):
    """frayAmount is #19's to write: NaN must not reach alphaTest, where crossing 0 recompiles the fringe without its
    alpha cut and draws a dark band."""
    page, errors = open_help_live(make_page, base_url)
    fringe = help_hook(page, ".fringe")
    page.eval_on_selector("[data-hero]", "el => { el.__weaveHelp.fray.frayAmount = NaN; }")
    page.wait_for_timeout(200)
    bad = help_hook(page, ".fringe")
    assert bad["threshold"] == fringe["threshold"] and bad["materialVersion"] == fringe["materialVersion"], (fringe, bad)
    assert errors == []


def test_help_click_does_nothing_and_has_no_mend_button(make_page, base_url):
    """Until #19: no Mend it button, and a click on the hero changes nothing."""
    page, errors = open_help_live(make_page, base_url)
    assert page.get_by_role("button", name="Mend it").count() == 0
    box = page.locator("[data-hero]").bounding_box()
    page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.wait_for_timeout(300)
    assert help_hook(page, ".fray.state") == "frayed" and help_hook(page, ".fray.frayAmount") == 1
    assert hero_result(page) == ["live", "ok"]
    assert errors == []


def test_help_never_requests_panels_js_on_the_live_path(make_page, base_url):
    """AC 12's live leg."""
    requested = []
    page, _ = open_help_live(make_page, base_url, before_goto=logged(requested))
    assert any("three.module" in url for url in requested), requested  # the live path really loaded
    assert not [url for url in requested if url.endswith("/panels.js")], requested


# --- The loop: Pause, resizes, a hidden tab, off screen and the one clock. ---


def fray_clock(page):
    return help_hook(page, ".fray.clock")


def strands(page):
    return page.eval_on_selector("[data-hero]", STRANDS_JSON)


def stage_ink(page):
    """The stage's ink, and the same with the canvas hidden (the control)."""
    stage = page.locator("[data-hero]")
    live = ink_fraction(stage.screenshot())
    page.eval_on_selector("[data-hero] canvas", "el => { el.style.visibility = 'hidden'; }")
    control = ink_fraction(stage.screenshot())
    page.eval_on_selector("[data-hero] canvas", "el => { el.style.visibility = ''; }")
    return live, control


# Records fray.clock at the first counted frame after this call.
WATCH_NEXT_CLOCK = r"""el => {
    window.__nextClock = null;
    const observer = new MutationObserver(() => { window.__nextClock = el.__weaveHelp.fray.clock; observer.disconnect(); });
    observer.observe(el, { attributes: true, attributeFilter: ['data-hero-frames'] });
}"""


def test_help_pause_freezes_threads_and_play_resumes_without_a_jump(make_page, base_url):
    """AC 6, a port of test_live.py's Pause test (coalesce's test_pause_stops_and_resumes_rendering)."""
    page, errors = open_help_live(make_page, base_url)
    assert rising(page, 300)
    pause = page.locator("[data-pause]")
    pause.click()
    assert pause.get_attribute("aria-pressed") == "true" and pause.inner_text() == "Play motion"
    page.wait_for_timeout(200)
    held = (strands(page), frames(page), fray_clock(page))
    page.wait_for_timeout(1000)
    assert (strands(page), frames(page), fray_clock(page)) == held
    page.eval_on_selector("[data-hero]", WATCH_NEXT_CLOCK)
    pause.click()
    assert pause.get_attribute("aria-pressed") == "false" and pause.inner_text() == "Pause motion"
    page.wait_for_timeout(600)
    assert frames(page) > held[1]
    first = page.evaluate("window.__nextClock")
    assert first is not None and first - held[2] <= 1 / 30, (first, held[2])
    assert errors == []


def test_help_paused_scene_redraws_after_a_resize(make_page, base_url):
    """AC 6, a port of test_live.py's paused-resize test: the alpha canvas reads as paper if it is not redrawn."""
    page, _ = open_help_live(make_page, base_url)
    page.locator("[data-pause]").click()
    page.wait_for_timeout(200)
    stage = page.locator("[data-hero]")
    before = (stage.bounding_box()["width"], page.eval_on_selector("[data-hero] canvas", "c => c.width"))
    held = frames(page)
    page.set_viewport_size({"width": 820, "height": 900})
    page.wait_for_timeout(600)
    after = (stage.bounding_box()["width"], page.eval_on_selector("[data-hero] canvas", "c => c.width"))
    assert after[0] != before[0] and after[1] != before[1]  # the stage and its buffer really changed
    assert frames(page) == held
    live, control = stage_ink(page)
    assert live >= 0.05 and live >= 3 * control, (live, control)


def test_help_live_resize_redraws_before_the_frame_paints(make_page, base_url):
    """Issue-7: a resize while the loop runs lands after that frame's render, so it must redraw itself."""
    page, errors = open_help_live(make_page, base_url)
    assert rising(page, 300)
    r = page.eval_on_selector("[data-hero]", RESIZE_AND_READ)
    assert r["after"] != r["before"]
    assert r["ink"] > 0.1, r
    assert errors == []


def test_help_hidden_tab_holds_frames_and_clock(make_page, base_url):
    """AC 7."""
    page, errors = open_help_live(make_page, base_url)
    assert rising(page, 300)
    held = page.evaluate(SET_HIDDEN, True)
    clock = fray_clock(page)
    page.wait_for_timeout(1000)
    assert frames(page) == held and fray_clock(page) == clock
    page.evaluate(SET_HIDDEN, False)
    page.wait_for_timeout(600)
    assert frames(page) > held and fray_clock(page) > clock
    assert errors == []


def test_help_off_screen_stage_idles(make_page, base_url):
    page, _ = open_help_live(make_page, base_url, viewport={"width": 1440, "height": 500})
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


def test_help_frozen_date_keeps_threads_moving(make_page, base_url):
    """AC 8: Date is pinned (the default make_page, #12's fixture), and the sim still runs on rAF time."""
    page, errors = open_help_live(make_page, base_url)
    assert page.evaluate(CLOCK_ADVANCE) == 0  # control: Date really is pinned
    clock, pose = fray_clock(page), strands(page)
    page.wait_for_timeout(1000)
    assert fray_clock(page) > clock + 0.5 and strands(page) != pose
    assert errors == []


# --- The stir and ?pose=rest. ---

# Sums each strand's frame-to-frame point movement over every counted frame from now on, into window.__moved.
RECORD_MOVES = r"""el => {
    const f = el.__weaveHelp.fray;
    const copy = () => f.strands.map((s) => s.points.map((p) => [...p]));
    let prev = copy();
    window.__moved = new Array(f.strands.length).fill(0);
    window.__recorder = new MutationObserver(() => {
      const now = copy();
      now.forEach((s, i) => s.forEach((p, j) => {
        window.__moved[i] += Math.hypot(p[0] - prev[i][j][0], p[1] - prev[i][j][1], p[2] - prev[i][j][2]);
      }));
      prev = now;
    });
    window.__recorder.observe(el, { attributes: true, attributeFilter: ['data-hero-frames'] });
}"""


def test_pointer_stirs_the_nearest_strand(make_page, base_url):
    """AC 5 (U1 on the page)."""
    page, errors = open_help_live(make_page, base_url)
    p = help_hook(page, ".fray.strands[4].points[8]")
    x, y = page.eval_on_selector("[data-hero]", "(el, p) => el.__weaveHelp.project(p)", p)
    page.mouse.move(x, y)
    page.wait_for_timeout(100)
    stir = help_hook(page, ".fray.stir")
    assert stir is not None and max(abs(a - b) for a, b in zip(stir, p)) <= 0.05, (stir, p)
    pins = help_hook(page, ".fray.strands.map((s) => s.points[0])")
    farthest = max(range(10), key=lambda i: abs(pins[i][0] - pins[4][0]))
    page.eval_on_selector("[data-hero]", RECORD_MOVES)
    for i in range(20):
        page.mouse.move(x + (40 if i % 2 == 0 else -40), y)
        page.wait_for_timeout(50)
    moved = page.evaluate("window.__recorder.disconnect(), window.__moved")
    assert moved[4] > moved[farthest] and moved[4] > 0, (moved, farthest)
    page.mouse.move(0, 0)
    page.wait_for_timeout(100)
    assert help_hook(page, ".fray.stir") is None
    assert errors == []


@pytest.mark.parametrize("rest", [True, False], ids=["rest", "control"])
def test_help_pose_rest_is_still_but_not_paused(make_page, base_url, rest):
    """AC 9, a port of test_pose.py's: the rest pose holds the threads still while the loop runs; without it (the
    control) the same sweeps move them."""
    page, errors = open_help_live(make_page, base_url, query="?pose=rest&nowatchdog" if rest else "?nowatchdog")
    sweep(page, y0=0.4, y1=0.9)
    stirs = [help_hook(page, ".fray.stir")]
    pose = strands(page)
    before = frames(page)
    sweep(page, y0=0.4, y1=0.9)
    stirs.append(help_hook(page, ".fray.stir"))
    page.wait_for_timeout(1000)
    assert frames(page) > before
    assert (strands(page) == pose) is rest
    if rest:
        assert stirs == [None, None]
    assert errors == []


def test_help_pose_rest_still_falls_back_when_slow(make_page, base_url):
    """AC 9: ?pose=rest freezes the motion inputs only; the watchdog still rules (D34)."""
    page, _ = open_help(make_page, base_url, path=HELP + "?pose=rest&watchdogLimitMs=0", reduced_motion="no-preference")
    wait_for_reason(page, "too-slow")
    assert hero_result(page) == ["still", "too-slow"]
    assert_help_still(page)


# --- Every runtime fallback, each with its fault shown to have arrived. ---


# Counts WEBGL_lose_context.loseContext() calls on the stage's (aria-hidden) canvas into window.__stageLost; the
# eligibility probe's own canvas is not counted.
COUNT_STAGE_CONTEXT_LOSS = r"""
    for (const proto of [WebGLRenderingContext.prototype, WebGL2RenderingContext.prototype]) {
      const original = proto.getExtension;
      proto.getExtension = function (name, ...args) {
        const ext = original.call(this, name, ...args);
        if (ext && name === 'WEBGL_lose_context' && !ext.__counted) {
          const gl = this;
          const lose = ext.loseContext.bind(ext);
          ext.loseContext = () => {
            if (gl.canvas.getAttribute && gl.canvas.getAttribute('aria-hidden') === 'true') {
              window.__stageLost = (window.__stageLost || 0) + 1;
            }
            return lose();
          };
          ext.__counted = true;
        }
        return ext;
      };
    }
"""


def fallback_page(make_page, base_url, case):
    """The Help page set up for runtime fallback `case`; returns (page, errors, warnings, hits)."""
    warnings, hits = [], []
    query = "?watchdogLimitMs=0" if case == "too-slow" else "?nowatchdog"

    def abort(route):
        hits.append(route.request.url)
        route.abort()

    def before(page):
        collect_warnings(page, ("WEAVE: ",), warnings)
        if case == "load-failed":
            page.route("**/three.module.min.js", abort)
        if case == "load-failed-build":
            page.add_init_script(SASHING_THROWS)
            page.add_init_script(COUNT_STAGE_CONTEXT_LOSS)
        if case == "webgl-failed":
            page.add_init_script(NO_STAGE_WEBGL)

    page, errors = open_help(make_page, base_url, path=HELP + query, reduced_motion="no-preference", before_goto=before)
    return page, errors, warnings, hits


@pytest.mark.parametrize("case", ["too-slow", "load-failed", "load-failed-build", "context-lost", "webgl-failed"])
def test_help_runtime_fallbacks(make_page, base_url, case):
    """AC 11's runtime reasons: each falls back to the still with nothing live left, and each fault really arrived
    (Issue-17's vacuous-degrade rule)."""
    page, errors, warnings, hits = fallback_page(make_page, base_url, case)
    reason = "load-failed" if case == "load-failed-build" else case
    if case == "context-lost":
        assert hero_result(page) == ["live", "ok"]
        page.eval_on_selector("[data-hero] canvas",
                              "c => c.getContext('webgl2').getExtension('WEBGL_lose_context').loseContext()")
    wait_for_reason(page, reason)
    assert hero_result(page) == ["still", reason]
    assert_help_still(page)
    if case == "too-slow":
        assert frames(page) >= 3  # the loop really ran before the watchdog ruled
    if case == "load-failed":
        assert len(hits) >= 1, hits
    if case == "load-failed-build":
        # The renderer was built before the scene threw, so its context must have been released.
        assert page.evaluate("window.__stageLost || 0") == 1
    if case in ("load-failed", "load-failed-build"):
        assert len([w for w in warnings if w.startswith(HELP_LOAD_FAILED)]) == 1, warnings
        assert not [e for e in errors if e.startswith("pageerror")], errors
    if case == "context-lost":
        assert errors == []
    if case == "webgl-failed":
        assert errors == ["console.error: THREE.WebGLRenderer: Error creating WebGL context."]
        assert len([w for w in warnings if w.startswith(WEBGL_FAILED)]) == 1, warnings


def test_help_stop_hook_tears_down_once(make_page, base_url):
    page, errors = open_help_live(make_page, base_url)
    page.eval_on_selector("[data-hero]",
                          "el => { el.__weaveHelp.stop('context-lost'); el.__weaveHelp.stop('too-slow'); }")
    assert hero_result(page) == ["still", "context-lost"]
    assert_help_still(page)
    held, clock = frames(page), fray_clock(page)
    page.wait_for_timeout(600)
    assert frames(page) == held and fray_clock(page) == clock
    assert help_hook(page, ".fray.state") == "frayed"  # the hook outlives the teardown
    assert errors == []


# --- The h1 holds as Pause shows and hides (Issue-15; draft round 1). ---

H1_BOX = ("async () => { await document.fonts.ready; const r = document.querySelector('.hero h1').getBoundingClientRect();"
          " return [r.x, r.y, r.width, r.height]; }")


def close_box(a, b, tol=0.5):
    return all(abs(x - y) <= tol for x, y in zip(a, b))


def test_help_h1_holds_across_go_live_and_fallback(make_page, base_url):
    still, _ = open_help(make_page, base_url)
    assert hero_result(still) == ["still", "reduced-motion"]
    reference = still.evaluate(H1_BOX)
    row = still.locator("[data-controls]")
    assert row.count() == 1 and row.evaluate("el => getComputedStyle(el).visibility") == "hidden"
    assert row.bounding_box()["height"] >= 44

    page, errors = open_help_live(make_page, base_url)
    live_row = page.locator("[data-controls]")
    # Subject count first: the row and Pause really showed before anything is measured against them.
    assert live_row.count() == 1 and live_row.is_visible() and page.locator("[data-pause]").is_visible()
    assert close_box(page.evaluate(H1_BOX), reference), (page.evaluate(H1_BOX), reference)
    page.eval_on_selector("[data-hero]", "el => el.__weaveHelp.stop('too-slow')")
    wait_for_reason(page, "too-slow")
    assert live_row.evaluate("el => el.hidden") is True
    assert close_box(page.evaluate(H1_BOX), reference), (page.evaluate(H1_BOX), reference)
    assert errors == []

    # Planted control: without the reserve, the row collapses and the centred h1 moves.
    still.eval_on_selector("[data-controls]", "el => el.removeAttribute('data-reserve')")
    moved = still.evaluate(H1_BOX)
    assert abs(moved[1] - reference[1]) > 10, (moved, reference)
    # Home guard: only Help carries data-reserve, so the scoped rules never reach the home page.
    assert "data-reserve" not in (PUBLIC / "index.html").read_text(encoding="utf-8")
