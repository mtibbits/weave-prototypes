"""Check WEAVE's budgets and hero states on this machine (ported from coalesce/tools/verify.py).

From the repo root, with the venv active:

  python weave/tools/verify.py [--headless] [--base URL]

Measures every budget row (the sew-in's frames on a ?whatsnew load included), then checks every hero state (the quilt, hover, tiles, a reorder, the sew-back, Pause, the
three still fallbacks and the phone) and screenshots each, as shots/01-quilt.png to shots/11-full-page.png. Each run
keeps its own report.json and shots/ under weave/verify-output/runs/{local|base}-<sha7>[-dirty][-headless]/, and
weave/verify-output/report.json and shots/ are copies of the latest run. Exits 1 if any row fails. It runs a visible
browser by default so the frame times use the real GPU; --headless is a smoke run only, never evidence for the frame
rows. --base URL checks the states alone against a deployed copy (the budgets stay local: Pages compresses).

The clock (#12): every page opens through page_url, which adds NOW_QUERY, now= at fixed_clock.py's FIXED_DATE, so no
run lands in a release window. The browser clock is never pinned (a pin empties the performance timeline the budgets
read), and the run's clock variable for the tests is never read.
"""
import argparse
import importlib.util
import json
import re
import shutil
import statistics
import subprocess
import sys
from pathlib import Path

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

WEAVE = Path(__file__).resolve().parents[1]
REPO = WEAVE.parent
PUBLIC = WEAVE / "public"
OUT = WEAVE / "verify-output"
# The root serve.py serves public/ at / (D35). Appended, so it never shadows a module the caller resolves first.
sys.path.append(str(REPO / "tools"))
import serve  # noqa: E402


def _load_fixed_clock():
    """weave/tools/fixed_clock.py, loaded by path: the one home of the tests' instant. A missing file raises."""
    spec = importlib.util.spec_from_file_location("weave_fixed_clock", Path(__file__).with_name("fixed_clock.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


fixed_clock = _load_fixed_clock()
NOW_DATE = fixed_clock.FIXED_DATE
NOW_QUERY = f"now={NOW_DATE}"

# Copies of tests/conftest.py's GPU_ARGS and NO_WEBGL_ARGS (test_verify.py pins them equal).
GPU_ARGS = ["--use-angle=d3d11", "--enable-gpu", "--ignore-gpu-blocklist"]
NO_WEBGL_ARGS = ["--disable-webgl", "--disable-webgl2", "--disable-3d-apis"]
BUDGETS = {"home_transfer_bytes": 1_500_000, "first_live_frame_ms": 4000, "frame_median_ms": 16.7,
           "frame_p95_ms": 33.0, "still_bytes": 250_000}
STILL_SIZE = (1600, 1000)
# The hero each profile must end in.
EXPECTED_STATES = {"desktop": ["live", "ok"], "reduced_motion": ["still", "reduced-motion"], "phone": ["still", "no-hover"]}
# The idle window opens no earlier than this after going live: past the watchdog's 2 s ruling.
SETTLE_AFTER_LIVE_MS = 2500
# The modes one Unstitch and one Sew it back must pass through, in order, for the window to count (#8).
EXPECTED_CYCLE = ["unstitching", "tiles", "restitching", "quilt"]
# Recorded beside the pooled frame rows, not budgeted, so a slow transition stays visible; the max catches a single
# long frame (the first flip's tile shader compile and texture uploads) that no p95 can see.
CYCLE_MEASURES = ("cycle_frame_median_ms", "cycle_frame_p95_ms", "cycle_frame_max_ms")
# #16's sew-in rows: the frames over a ?whatsnew load's sew-in (at the fixed date, so nothing is written), held to the
# idle bars' median and p95; the max is recorded, never budgeted (the first needle's show is one long frame). They count
# only if that load passed through these modes.
EXPECTED_SEW = ["intro", "sewing", "quilt"]
SEW_MEASURES = ("sew_frame_median_ms", "sew_frame_p95_ms", "sew_frame_max_ms")

FRAME_TIMES = """() => new Promise((resolve) => {
  const deltas = []; let last = performance.now(); const end = last + 5000;
  const tick = (now) => { deltas.push(now - last); last = now;
    if (now < end) requestAnimationFrame(tick); else resolve(deltas); };
  requestAnimationFrame(tick);
})"""
# The desktop window (#8): one continuous rAF loop, 5 s tagged idle, then the toggle is pressed, pressed again on
# tiles, and the loop stops when quilt is entered from restitching (or after 15 s), so idle and cycle deltas are
# one unbroken series. The empty-page baseline keeps FRAME_TIMES: it has no toggle.
WINDOW_TIMES = """() => new Promise((resolve) => {
  const stage = document.querySelector('[data-hero]');
  const toggle = document.querySelector('[data-toggle]');
  const idle = []; const cycle = []; const modes = [];
  let phase = 'idle'; let last = performance.now(); const idleEnd = last + 5000; let capAt = 0;
  const onMode = (event) => {
    modes.push(event.detail.mode);
    if (event.detail.mode === 'tiles') toggle.click();
    else if (event.detail.mode === 'quilt' && event.detail.from === 'restitching') phase = 'done';
  };
  stage.addEventListener('weave:mode', onMode);
  const tick = (now) => {
    const dt = now - last; last = now;
    if (phase === 'idle') {
      idle.push(dt);
      if (now >= idleEnd) { phase = 'cycle'; capAt = now + 15000; toggle.click(); }
    } else {
      cycle.push(dt);
      if (phase === 'done' || now >= capAt) {
        stage.removeEventListener('weave:mode', onMode);
        resolve({ idle, cycle, modes });
        return;
      }
    }
    requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
})"""
TRANSFER = """() => performance.getEntriesByType('navigation').concat(performance.getEntriesByType('resource'))
  .reduce((sum, e) => sum + (e.transferSize || e.encodedBodySize || 0), 0)"""
SETTLED = """() => { const d = document.querySelector('[data-hero]').dataset;
  return d.heroState && d.heroReason !== 'loading'; }"""
HERO = "el => [el.dataset.heroState, el.dataset.heroReason]"
# The settled quilt (#10): a plain load plays the intro first, so the windows open only once it has settled. Byte-equal
# to tests/helpers.py's QUILT_SETTLED (test_verify.py pins the two), with wait_for_quilt's 15 s.
QUILT_SETTLED = ("() => { const el = document.querySelector('[data-hero]');"
                 " return el?.dataset.mode === 'quilt' && el.__weave?.mode === 'quilt'; }")
SETTLED_TIMEOUT_MS = 15000
# An init script: every rAF delta from the intro's weave:mode entry until it leaves intro (the event does not bubble,
# so the document listens in the capture phase). Recorded as the intro's longest frame, not budgeted.
INTRO_FRAMES = """
  window.__introFrames = null;
  document.addEventListener('weave:mode', (event) => {
    if (event.detail.mode !== 'intro') return;
    const deltas = []; window.__introFrames = deltas;
    let last = performance.now();
    const tick = (now) => { deltas.push(now - last); last = now;
      if (document.querySelector('[data-hero]').__weave?.mode === 'intro') requestAnimationFrame(tick); };
    requestAnimationFrame(tick);
  }, true);
"""
# An init script (#16), like INTRO_FRAMES: every rAF delta from the sewing entry until the mode leaves sewing, and
# every mode the load enters, in window.__sewModes.
SEW_FRAMES = """
  window.__sewFrames = null;
  window.__sewModes = [];
  document.addEventListener('weave:mode', (event) => {
    window.__sewModes.push(event.detail.mode);
    if (event.detail.mode !== 'sewing') return;
    const deltas = []; window.__sewFrames = deltas;
    let last = performance.now();
    const tick = (now) => { deltas.push(now - last); last = now;
      if (document.querySelector('[data-hero]').__weave?.mode === 'sewing') requestAnimationFrame(tick); };
    requestAnimationFrame(tick);
  }, true);
"""
# The hover's per-frame pick (#10), timed over 200 calls across the stage's middle row; its median in ms, recorded.
PICK_TIMES = """el => {
  const r = el.getBoundingClientRect(); const times = [];
  for (let i = 0; i < 200; i += 1) {
    const t0 = performance.now();
    el.__weave.pickBlock(r.left + r.width * ((i % 20) + 0.5) / 20, r.top + r.height / 2);
    times.push(performance.now() - t0);
  }
  times.sort((a, b) => a - b);
  return times[100];
}"""
FRAMES = "el => Number(el.dataset.heroFrames || 0)"
NO_SIDEWAYS_SCROLL = "document.documentElement.scrollWidth <= window.innerWidth"

# --- The state checks (#11): one shot per state, named as the PR and epic #1 cite them. ---

STATE_SHOTS = {"quilt": "01-quilt.png", "hover": "02-hover.png", "tiles": "03-tiles.png", "reorder": "04-reorder.png",
               "sewn_back": "05-sewn-back.png", "paused": "06-paused.png", "still_no_webgl": "07-still-no-webgl.png",
               "still_reduced_motion": "08-still-reduced-motion.png", "still_watchdog": "09-still-watchdog.png",
               "phone": "10-phone.png", "full_page": "11-full-page.png"}
CHECKS = (*STATE_SHOTS, "labels")
# Shot as the whole page; the rest at the viewport.
FULL_PAGE_SHOTS = ("still_no_webgl", "still_reduced_motion", "still_watchdog", "phone", "full_page")
DESKTOP = {"width": 1440, "height": 900}
PHONE = {"viewport": {"width": 390, "height": 844}, "is_mobile": True, "has_touch": True, "device_scale_factor": 2}
# The hover amount eases to exactly 1 in about 0.58 s (tests/test_hover.py's HOVER_SETTLE_MS).
HOVER_SETTLE_MS = 2000
# Every module the checks import resolves from the page's own URL, so a sub-path base (Pages) works unchanged.
LAYOUT_JS = "new URL('js/layout.js', document.baseURI).href"
# Byte-equal to tests/helpers.py's SEAMS_JS (test_verify.py pins the two): every non-planned block's 160 edge vertices
# against the sashing, and each block's centre against its quilt slot (off).
SEAMS_JS = r"""
    const seams = (snap, L, nudge = 0) => {
      const sp = snap.sashing.positions;
      let checked = 0; let missing = 0; let off = 0;
      for (const b of snap.blocks) {
        const p = b.positions;
        const mean = [0, 1].map((k) => [0, 40, 1640, 1680].reduce((s, j) => s + p[3 * j + k], 0) / 4);
        off = Math.max(off, ...mean.map((v, k) => Math.abs(v - L.slotCentre(b.slot)[k])));
        if (b.face === 'planned') continue;
        const dx = b.slot === 0 ? nudge : 0;
        for (let r = 0; r <= 40; r += 1) {
          for (let c = 0; c <= 40; c += 1) {
            if (r !== 0 && r !== 40 && c !== 0 && c !== 40) continue;
            const j = 3 * (r * 41 + c);
            checked += 1;
            let hit = false;
            for (let k = 0; k < sp.length && !hit; k += 3) {
              hit = Math.hypot(sp[k] - p[j] - dx, sp[k + 1] - p[j + 1], sp[k + 2] - p[j + 2]) <= 1e-4;
            }
            if (!hit) missing += 1;
          }
        }
      }
      return { checked, missing, off };
    };
"""
# local(snap, m): the snapshot's block and sashing positions mapped into the quilt group's own frame (m is
# __weave.groupMatrix(): a rotation about the rod plus a translation), so the sway and the pointer tilt drop out and
# the slot centres apply on a plain load as they do at rest.
LOCAL_JS = r"""
    const local = (snap, m) => {
      const f = (p) => {
        const out = new Array(p.length);
        for (let j = 0; j < p.length; j += 3) {
          const d = [p[j] - m[12], p[j + 1] - m[13], p[j + 2] - m[14]];
          for (let k = 0; k < 3; k += 1) out[j + k] = d[0] * m[4 * k] + d[1] * m[4 * k + 1] + d[2] * m[4 * k + 2];
        }
        return out;
      };
      return { ...snap, blocks: snap.blocks.map((b) => ({ ...b, positions: f(b.positions) })),
               sashing: { ...snap.sashing, positions: f(snap.sashing.positions) } };
    };
"""
# SEAMS_JS on a fresh snapshot in the group's frame, with the count of blocks it checks (the non-planned ones).
SEAMS = f"""async (el) => {{ const L = await import({LAYOUT_JS}); {SEAMS_JS} {LOCAL_JS}
    const snap = local(el.__weave.snapshot(), el.__weave.groupMatrix());
    return {{ ...seams(snap, L), sewn: snap.blocks.filter((b) => b.face !== 'planned').length }}; }}"""
TILE_CENTRES = (f"async () => {{ const L = await import({LAYOUT_JS});"
                " return [...Array(12).keys()].map((k) => L.slotCentre(k, 'tiles')); }")
# The client point of the block now in `slot`: its four corners' world mean, through __weave.project.
SLOT_POINT = """(el, slot) => { const b = el.__weave.snapshot().blocks.find((x) => x.slot === slot);
  const p = b.positions;
  return el.__weave.project([0, 1, 2].map((k) => [0, 40, 1640, 1680].reduce((s, j) => s + p[3 * j + k], 0) / 4)); }"""
# Synchronous: the order is as expected and every block's corner mean (in the group's frame) is within 1e-3 of its
# tile slot.
TILES_AT = f"""([tiles, order]) => {{ const el = document.querySelector('[data-hero]'); {LOCAL_JS}
  const snap = local(el.__weave.snapshot(), el.__weave.groupMatrix());
  return JSON.stringify(el.__weave.order) === JSON.stringify(order) && snap.blocks.every((b) => [0, 1].every((k) =>
    Math.abs([0, 40, 1640, 1680].reduce((s, j) => s + b.positions[3 * j + k], 0) / 4 - tiles[b.slot][k]) <= 1e-3)); }}"""
# The pill through textContent (CSS upper-cases it), the panel figures and the footer.
LABELS = """() => ({ pill: document.querySelector('.pill')?.textContent.trim() ?? null,
  figures: [...document.querySelectorAll('.panel-figure')].map((e) => e.textContent.trim()),
  footer: document.querySelector('.site-footer')?.textContent ?? '' })"""
STILL_STATE = """() => { const el = document.querySelector('[data-hero]'); const img = el.querySelector('.hero-still');
  const seen = (sel) => [...document.querySelectorAll(sel)].some((e) => e.getClientRects().length > 0
    && getComputedStyle(e).visibility !== 'hidden');
  return { complete: img.complete, width: img.naturalWidth, opacity: getComputedStyle(img).opacity,
           live: el.classList.contains('is-live'), canvas: !!el.querySelector('canvas'),
           live_panels: seen('[data-list="live"] .panel'), planned_panels: seen('[data-list="planned"] .panel') }; }"""
STILL_OPAQUE = """() => { const img = document.querySelector('[data-hero] .hero-still');
  return img.complete && getComputedStyle(img).opacity === '1'; }"""
REASON_IS = "(reason) => document.querySelector('[data-hero]').dataset.heroReason === reason"
TILES_MODE = ("() => { const el = document.querySelector('[data-hero]');"
              " return el.dataset.mode === 'tiles' && el.__weave.mode === 'tiles'; }")
HOVERED = ("(id) => { const h = document.querySelector('[data-hero]').__weave.hover;"
           " return h.id === id && h.amount === 1; }")


def frame_budget(baseline_ms):
    """The idle median may not be slower than the display allows: 16.7 ms on a 60 Hz screen, or an empty page's
    frame time plus 1 ms where the display itself runs slower than that."""
    return max(BUDGETS["frame_median_ms"], round(baseline_ms + 1.0, 2))


def page_url(base, query=""):
    """The page at `base` (a site root or a sub-path, with or without its trailing slash), with NOW_QUERY and then
    `query` (a leading '?' optional). NOW_QUERY comes first because URLSearchParams.get keeps the first now=, as in
    capture_still.py's RECIPE."""
    return base.rstrip("/") + "/?" + "&".join(part for part in (NOW_QUERY, query.lstrip("?")) if part)


def wait_settled(page):
    """Wait until the quilt has settled in quilt mode: past the intro (#10), as the tests' wait_for_quilt does."""
    page.wait_for_function(QUILT_SETTLED, timeout=SETTLED_TIMEOUT_MS)


def settle(page):
    page.wait_for_function(SETTLED, timeout=30000)
    return page.eval_on_selector("[data-hero]", HERO)


def new_context(browser, **options):
    """The one place the tools make a context; its clock stays real (see the module docstring)."""
    return browser.new_context(**options)


def median_p95(deltas):
    return round(statistics.median(deltas), 2), round(sorted(deltas)[int(len(deltas) * 0.95)], 2)


def frame_stats(deltas):
    """(median, p95) of a frame loop's deltas, without its first (the wait for the first frame)."""
    return median_p95(deltas[1:])


def window_stats(idle, cycle):
    """(pooled, cycle_only) for #8's window: the idle and cycle deltas pooled as one loop (only the very first
    delta dropped), and the cycle's own (median, p95, max)."""
    return frame_stats(idle + cycle), (*median_p95(cycle), round(max(cycle), 2))


def sew_window(context, base):
    """#16: a ?whatsnew load in `context`, measured over its sew-in once it has settled into the quilt. The caller
    closes every other page first, so one live quilt renders while it is measured. Returns {state, deltas, modes,
    pages (the context's open pages while measured), page}; deltas and modes are None unless the hero went live."""
    page = context.new_page()
    page.add_init_script(SEW_FRAMES)
    page.goto(page_url(base, "whatsnew"))
    out = {"state": settle(page), "deltas": None, "modes": None, "pages": len(context.pages), "page": page}
    if out["state"] == ["live", "ok"]:
        wait_settled(page)
        out["deltas"], out["modes"] = page.evaluate("[window.__sewFrames, window.__sewModes]")
    return out


def run(report, base, headless):
    measures, states = report["measures"], report["states"]
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=headless, args=GPU_ARGS)
        desktop = new_context(browser, viewport=DESKTOP)

        # An empty page shows what this display and browser can do at best (not every screen is exactly 60 Hz).
        page = desktop.new_page()
        page.set_content("<!doctype html><title>Baseline</title>")
        measures["baseline_frame_median_ms"] = frame_stats(page.evaluate(FRAME_TIMES))[0]
        page.close()

        page = desktop.new_page()
        page.add_init_script(INTRO_FRAMES)
        page.goto(page_url(base))
        states["desktop"] = settle(page)
        if states["desktop"] == ["live", "ok"]:
            wait_settled(page)
            page.wait_for_function("performance.getEntriesByName('weave:first-live-frame').length === 1")
            intro = page.evaluate("window.__introFrames")
            measures["intro_frame_max_ms"] = round(max(intro), 2) if intro else None
            measures["first_live_frame_ms"] = round(
                page.evaluate("performance.getEntriesByName('weave:first-live-frame')[0].startTime"), 1)
            page.wait_for_timeout(SETTLE_AFTER_LIVE_MS)
            before = page.eval_on_selector("[data-hero]", FRAMES)
            window = page.evaluate(WINDOW_TIMES)
            pooled, cycle = window_stats(window["idle"], window["cycle"])
            measures["frame_median_ms"], measures["frame_p95_ms"] = pooled
            measures["cycle_frame_median_ms"], measures["cycle_frame_p95_ms"], measures["cycle_frame_max_ms"] = cycle
            states["desktop_cycle"] = window["modes"]
            # The hook outlives a teardown (w302), so the window counts only if the quilt is still live and running.
            state, reason = page.eval_on_selector("[data-hero]", HERO)
            states["desktop_after_idle"] = {"state": state, "reason": reason,
                                            "frames_rose": page.eval_on_selector("[data-hero]", FRAMES) > before}
            if state == "live":
                measures["pick_block_median_ms"] = round(page.eval_on_selector("[data-hero]", PICK_TIMES), 3)
        measures["home_transfer_bytes"] = page.evaluate(TRANSFER)
        measures["headroom_bytes"] = BUDGETS["home_transfer_bytes"] - measures["home_transfer_bytes"]

        # #16: the sew-in, on its own page once the plain one is closed (its live loop would render beside it).
        page.close()
        sew = sew_window(desktop, base)
        states["sew_modes"] = sew["modes"]
        if sew["deltas"] and len(sew["deltas"]) > 1:
            measures["sew_frame_median_ms"], measures["sew_frame_p95_ms"] = frame_stats(sew["deltas"])
            measures["sew_frame_max_ms"] = round(max(sew["deltas"][1:]), 2)
        sew["page"].close()

        calm = new_context(browser, viewport=DESKTOP, reduced_motion="reduce")
        page = calm.new_page()
        page.goto(page_url(base))
        states["reduced_motion"] = settle(page)
        page.wait_for_function("document.querySelector('.hero-still').complete")
        measures["still_size"] = page.eval_on_selector(".hero-still", "img => [img.naturalWidth, img.naturalHeight]")

        phone = new_context(browser, **PHONE)
        page = phone.new_page()
        page.goto(page_url(base))
        states["phone"] = settle(page)
        states["phone_no_horizontal_scroll"] = page.evaluate(NO_SIDEWAYS_SCROLL)
        browser.close()


def first_line(exc):
    return (str(exc).strip().splitlines() or [type(exc).__name__])[0]


def move(items, i, j):
    """`items` with the one at i moved to j: the drag's reorder, computed apart from the page."""
    items = list(items)
    items.insert(j, items.pop(i))
    return items


def still_shown(page):
    """{ok, detail}: the still is loaded at 1600 px and opaque (within 2 s), nothing live is left on the stage, and
    both panel lists show."""
    try:
        page.wait_for_function(STILL_OPAQUE, timeout=2000)
    except PlaywrightError:
        pass
    s = page.evaluate(STILL_STATE)
    problems = []
    if not (s["complete"] and s["width"] == STILL_SIZE[0]):
        problems.append(f"the still is not loaded at {STILL_SIZE[0]} px (complete {s['complete']}, width {s['width']})")
    if s["opacity"] != "1":
        problems.append(f"the still's opacity is {s['opacity']}")
    if s["live"]:
        problems.append("the stage is still is-live")
    if s["canvas"]:
        problems.append("the stage still has a canvas")
    for key in ("live_panels", "planned_panels"):
        if not s[key]:
            problems.append(f"no visible {key.split('_')[0]} panel")
    return {"ok": not problems, "detail": "; ".join(problems)}


def run_states(base, shots_dir, browser, no_webgl, query=""):
    """(checks, shots) for every name in CHECKS. Each page is opened, checked, shot and closed before the next, so
    only one window is open at a time. `query` goes on the desktop rows only (the suite passes ?nowatchdog);
    still_watchdog always loads ?watchdogLimitMs=0. `no_webgl` is a function that returns the WebGL-off browser; it
    is called for that row only, and the caller owns the browser it returns. Every wait predicate is synchronous
    (Issue-9)."""
    checks, shots = {}, {}

    def attempt(name, fn, needs=None):
        if needs is not None and checks.get(needs, {}).get("ok") is not True:
            checks[name] = {"ok": False, "detail": f"skipped: {needs} failed"}
            return
        try:
            fn()
            checks[name] = {"ok": True, "detail": ""}
        except Exception as exc:  # a row's failure, of any kind, is that row's alone
            checks[name] = {"ok": False, "detail": first_line(exc)}

    def shoot(page, name):
        page.screenshot(path=str(shots_dir / STATE_SHOTS[name]), full_page=name in FULL_PAGE_SHOTS)
        shots[name] = f"shots/{STATE_SHOTS[name]}"

    shots_dir.mkdir(parents=True, exist_ok=True)
    context = new_context(browser, viewport=DESKTOP)
    try:
        page = context.new_page()
        page.goto(page_url(base, query))

        def weave(expr):
            return page.eval_on_selector("[data-hero]", f"el => el.__weave{expr}")

        def quilt():
            state = settle(page)
            assert state == ["live", "ok"], f"hero is {state}"
            page.locator("[data-hero]").scroll_into_view_if_needed()
            wait_settled(page)
            count = len(weave(".order"))
            shoot(page, "quilt")
            assert count == 12, f"{count} slots"

        def full_page():
            shoot(page, "full_page")

        def labels():
            found = page.evaluate(LABELS)
            assert found["pill"] == "Prototype · work in progress", f"the pill reads {found['pill']!r}"
            assert any(f.endswith("(sample)") for f in found["figures"]), f"no (sample) figure in {found['figures']}"
            assert "Sample data only" in found["footer"], f"the footer reads {found['footer']!r}"

        def hover():
            first, name = weave(".order[0]"), weave(".slots[0].name")
            page.mouse.move(*page.eval_on_selector("[data-hero]", SLOT_POINT, 0))
            page.wait_for_function(HOVERED, arg=first, timeout=HOVER_SETTLE_MS, polling=50)
            tip = page.eval_on_selector("[data-tooltip]", "t => [t.hidden, t.querySelector('.hero-tip-name').textContent]")
            shoot(page, "hover")
            assert tip == [False, name], f"the tooltip is {tip}, expected shown with {name!r}"

        def tiles():
            page.locator("[data-toggle]").click()
            page.wait_for_function(TILES_MODE, timeout=10000)
            shoot(page, "tiles")

        def reorder():
            expected = move(weave(".order"), 0, 5)
            a, b = (page.eval_on_selector("[data-hero]", SLOT_POINT, slot) for slot in (0, 5))
            page.mouse.move(*a)
            page.mouse.down()
            page.mouse.move(*b, steps=12)
            page.mouse.up()
            page.wait_for_function(TILES_AT, arg=[page.evaluate(TILE_CENTRES), expected], timeout=5000)
            shoot(page, "reorder")

        def sewn_back():
            before = weave(".order")
            # The toggle sits outside the stage, so the pointer leaves the canvas with this click.
            page.locator("[data-toggle]").click()
            wait_settled(page)
            seams = page.eval_on_selector("[data-hero]", SEAMS)
            after = weave(".order")
            shoot(page, "sewn_back")
            assert after == before, f"the order is {after} after the sew-back, was {before}"
            assert seams["sewn"] > 0 and seams["missing"] == 0 and seams["checked"] == 160 * seams["sewn"] \
                and seams["off"] <= 1e-6, \
                f"seams {seams}"

        def paused():
            page.locator("[data-pause]").click()
            pressed = page.get_attribute("[data-pause]", "aria-pressed")
            before = page.eval_on_selector("[data-hero]", FRAMES)
            page.wait_for_timeout(600)
            after = page.eval_on_selector("[data-hero]", FRAMES)
            shoot(page, "paused")
            assert pressed == "true", f"aria-pressed is {pressed}"
            assert after == before, f"frames went {before} -> {after} while paused"

        attempt("quilt", quilt)
        attempt("full_page", full_page, needs="quilt")
        attempt("labels", labels)
        attempt("hover", hover, needs="quilt")
        attempt("tiles", tiles, needs="quilt")
        attempt("reorder", reorder, needs="tiles")
        attempt("sewn_back", sewn_back, needs="tiles")
        attempt("paused", paused, needs="quilt")
    finally:
        context.close()

    def still_row(name, target, expected, row_query="", reason=None, **options):
        def row():
            context = new_context(target(), **options)
            try:
                page = context.new_page()
                page.goto(page_url(base, row_query))
                settle(page)
                if reason is not None:
                    page.wait_for_function(REASON_IS, arg=reason, timeout=20000)
                state = page.eval_on_selector("[data-hero]", HERO)
                shown = still_shown(page)
                narrow = page.evaluate(NO_SIDEWAYS_SCROLL)
                shoot(page, name)
            finally:
                context.close()
            assert state == expected, f"hero is {state} (expected {expected})"
            assert narrow, "the page scrolls sideways"
            assert shown["ok"], shown["detail"]

        attempt(name, row)

    still_row("still_no_webgl", no_webgl, ["still", "no-webgl"], viewport=DESKTOP)
    still_row("still_reduced_motion", lambda: browser, ["still", "reduced-motion"], viewport=DESKTOP,
              reduced_motion="reduce")
    still_row("still_watchdog", lambda: browser, ["still", "too-slow"], row_query="?watchdogLimitMs=0",
              reason="too-slow", viewport=DESKTOP)
    still_row("phone", lambda: browser, ["still", "no-hover"], **PHONE)
    return checks, shots


def run_all_states(report, base, shots_dir, headless):
    """run_states in its own browsers (the GPU flags; the WebGL-off one launched for its row only)."""
    launched = []

    def no_webgl():
        launched.append(pw.chromium.launch(headless=headless, args=NO_WEBGL_ARGS))
        return launched[-1]

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=headless, args=GPU_ARGS)
        try:
            report["checks"], report["shots"] = run_states(base, shots_dir, browser, no_webgl)
        finally:
            for opened in (browser, *launched):
                opened.close()


def budgets_for(measures):
    """BUDGETS, with frame_median_ms set from the measured baseline when there is one."""
    baseline = measures.get("baseline_frame_median_ms")
    return dict(BUDGETS) if baseline is None else {**BUDGETS, "frame_median_ms": frame_budget(baseline)}


def check(report):
    """Every failing row of `report`, named by its key; pure, and closed: a missing measure, state, check or shot
    fails. A --base report (report["base"] set) has the state checks only."""
    failures = [] if report.get("base") else budget_failures(report)
    checks, shots = report.get("checks") or {}, report.get("shots") or {}
    for name in CHECKS:
        entry = checks.get(name)
        if entry is None:
            failures.append(f"{name}: not run")
        elif entry.get("ok") is not True:
            failures.append(f"{name}: {entry.get('detail')}")
    for name in STATE_SHOTS:
        if not shots.get(name):
            failures.append(f"{name}: no screenshot")
    return failures


def budget_failures(report):
    """The local run's rows: every budget, the cycle and sew-in measures, headroom, the still's size and the run's hero
    states."""
    measures, states = report.get("measures") or {}, report.get("states") or {}
    failures = []
    budgets = budgets_for(measures)
    if measures.get("baseline_frame_median_ms") is None:
        failures.append("baseline_frame_median_ms is missing, so frame_median_ms is checked against 16.7")
    idle = states.get("desktop_after_idle")
    idle_ok = isinstance(idle, dict) and idle.get("state") == "live" and idle.get("frames_rose") is True
    cycle = states.get("desktop_cycle")
    for key, limit in budgets.items():
        value = measures.get(key)
        if value is None or value > limit:
            failures.append(f"{key} = {value} (budget {limit})")
        elif key.startswith("frame_"):
            if not idle_ok:
                failures.append(f"{key} = {value} was not measured on a live, running quilt (after the window: {idle})")
            elif cycle != EXPECTED_CYCLE:
                failures.append(f"{key} = {value} was not measured over one unstitch and sew-back cycle"
                                f" (modes: {cycle})")
    for key in CYCLE_MEASURES:
        if measures.get(key) is None:
            failures.append(f"{key} is missing")
    sew_bars = {"sew_frame_median_ms": budgets["frame_median_ms"], "sew_frame_p95_ms": budgets["frame_p95_ms"]}
    for key in SEW_MEASURES:
        value = measures.get(key)
        if value is None:
            failures.append(f"{key} is missing")
        elif key in sew_bars and value > sew_bars[key]:
            failures.append(f"{key} = {value} (budget {sew_bars[key]})")
    if states.get("sew_modes") != EXPECTED_SEW:
        failures.append(f"the sew-in rows were not measured over a sew-in (modes: {states.get('sew_modes')})")
    if measures.get("headroom_bytes") is None:
        failures.append("headroom_bytes: not run")
    if measures.get("still_size") != list(STILL_SIZE):
        failures.append(f"still_size = {measures.get('still_size')} (expected {list(STILL_SIZE)})")
    for name, expected in EXPECTED_STATES.items():
        if states.get(name) != expected:
            failures.append(f"{name}: hero is {states.get(name)} (expected {expected})")
    if states.get("phone_no_horizontal_scroll") is not True:
        failures.append("phone: horizontal scroll at 390 px")
    return failures


def http_url(value):
    if not re.match(r"https?://[^/\s]+", value):
        raise argparse.ArgumentTypeError(f"{value!r} is not an http(s):// URL")
    return value


def build_parser():
    parser = argparse.ArgumentParser(prog="verify.py",
                                     description="Check WEAVE's budgets and hero states on this machine.")
    parser.add_argument("--headless", action="store_true", help="a smoke run only; frame times need a visible window")
    parser.add_argument("--base", metavar="URL", type=http_url,
                        help="check the hero states only, against a deployed copy at URL (no budgets)")
    return parser


def git_stamp():
    """{sha, dirty} of the checkout verify.py runs from (tracked files only); None for both without git."""
    try:
        sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True,
                             check=True).stdout.strip()
        status = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"], cwd=REPO,
                                capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return {"sha": None, "dirty": None}
    return {"sha": sha, "dirty": bool(status.strip())}


def run_dir(out, base, git, headless=False):
    """This run's own directory: runs/{local|base}-<sha7>[-dirty][-headless], or -nogit without git. A headless smoke
    run never shares a folder with the headed run that is the evidence."""
    tag = f"{git['sha'][:7]}{'-dirty' if git['dirty'] else ''}" if git.get("sha") else "nogit"
    return out / "runs" / f"{'base' if base else 'local'}-{tag}{'-headless' if headless else ''}"


def main(argv=None):
    args = build_parser().parse_args(argv)
    if not __debug__:
        # The state rows fail through assert, which -O strips: every row would pass.
        print("verify.py: run without -O (the state checks are asserts)", file=sys.stderr)
        return 2
    report = {"git": git_stamp(), "base": args.base, "headless": args.headless, "budgets": {}, "measures": {},
              "states": {}, "checks": {}, "shots": {}, "failures": []}
    run_path = run_dir(OUT, args.base, report["git"], args.headless)
    shots_dir = run_path / "shots"
    # Only this run's own directory is emptied; a locked file (Windows) may survive, and the run goes on regardless.
    shutil.rmtree(shots_dir, ignore_errors=True)
    shots_dir.mkdir(parents=True, exist_ok=True)
    stopped = []
    try:
        if args.base is None:
            server, base = serve.start(PUBLIC)
            try:
                run(report, base, args.headless)
                run_all_states(report, base, shots_dir, args.headless)
            finally:
                server.shutdown()
                server.server_close()
        else:
            run_all_states(report, args.base, shots_dir, args.headless)
    except Exception as exc:
        stopped.append(f"verify.py stopped: {first_line(exc)}")
    finally:
        if args.base is None:
            report["measures"]["still_bytes"] = (PUBLIC / "assets" / "weave-still.jpg").stat().st_size
            report["budgets"] = budgets_for(report["measures"])
        report["failures"] = check(report) + stopped
        text = json.dumps(report, indent=2)
        (run_path / "report.json").write_text(text, encoding="utf-8")
        # The plain report.json and shots/ are copies of the latest run.
        (OUT / "report.json").write_text(text, encoding="utf-8")
        shutil.rmtree(OUT / "shots", ignore_errors=True)
        shutil.copytree(shots_dir, OUT / "shots", dirs_exist_ok=True)
    print(json.dumps({"git": report["git"], "measures": report["measures"], "states": report["states"],
                      "checks": report["checks"]}, indent=2))
    print(f"Run directory: {run_path}")
    print("\n".join(["FAILURES:", *report["failures"]]) if report["failures"] else "All budgets and states OK.")
    return 1 if report["failures"] else 0


if __name__ == "__main__":
    sys.exit(main())
