"""Check WEAVE's budgets and hero states on this machine (ported from coalesce/tools/verify.py).

From the repo root, with the venv active:

  python weave/tools/verify.py [--headless]

Writes weave/verify-output/report.json and exits 1 if a budget or state check fails. It runs a visible browser by
default so the frame times use the real GPU; --headless is a smoke run only, never evidence for the frame rows.
"""
import argparse
import importlib.util
import json
import statistics
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

WEAVE = Path(__file__).resolve().parents[1]
REPO = WEAVE.parent
PUBLIC = WEAVE / "public"
OUT = WEAVE / "verify-output"
# The root serve.py serves public/ at / (D35). Appended, so it never shadows a module the caller resolves first.
sys.path.append(str(REPO / "tools"))
import serve  # noqa: E402

# A copy of tests/conftest.py's GPU_ARGS (test_verify.py pins the two equal).
GPU_ARGS = ["--use-angle=d3d11", "--enable-gpu", "--ignore-gpu-blocklist"]
BUDGETS = {"home_transfer_bytes": 1_500_000, "first_live_frame_ms": 4000, "frame_median_ms": 16.7,
           "frame_p95_ms": 33.0, "still_bytes": 250_000}
STILL_SIZE = (1600, 1000)
# The hero each profile must end in.
EXPECTED_STATES = {"desktop": ["live", "ok"], "reduced_motion": ["still", "reduced-motion"], "phone": ["still", "no-hover"]}
# The idle window opens no earlier than this after going live: past the watchdog's 2 s ruling.
SETTLE_AFTER_LIVE_MS = 2500

FRAME_TIMES = """() => new Promise((resolve) => {
  const deltas = []; let last = performance.now(); const end = last + 5000;
  const tick = (now) => { deltas.push(now - last); last = now;
    if (now < end) requestAnimationFrame(tick); else resolve(deltas); };
  requestAnimationFrame(tick);
})"""
TRANSFER = """() => performance.getEntriesByType('navigation').concat(performance.getEntriesByType('resource'))
  .reduce((sum, e) => sum + (e.transferSize || e.encodedBodySize || 0), 0)"""
SETTLED = """() => { const d = document.querySelector('[data-hero]').dataset;
  return d.heroState && d.heroReason !== 'loading'; }"""
HERO = "el => [el.dataset.heroState, el.dataset.heroReason]"
FRAMES = "el => Number(el.dataset.heroFrames || 0)"


def frame_budget(baseline_ms):
    """The idle median may not be slower than the display allows: 16.7 ms on a 60 Hz screen, or an empty page's
    frame time plus 1 ms where the display itself runs slower than that."""
    return max(BUDGETS["frame_median_ms"], round(baseline_ms + 1.0, 2))


def fixed_instant():
    """#12's frozen instant from weave/tools/fixed_clock.py once it exists; None until then. Never the environment."""
    path = Path(__file__).with_name("fixed_clock.py")
    if not path.is_file():
        return None
    spec = importlib.util.spec_from_file_location("fixed_clock", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.FIXED_INSTANT


def settle(page):
    page.wait_for_function(SETTLED, timeout=30000)
    return page.eval_on_selector("[data-hero]", HERO)


def new_context(browser, **options):
    context = browser.new_context(**options)
    instant = fixed_instant()
    if instant is not None:
        context.clock.set_fixed_time(instant)
    return context


def frame_stats(deltas):
    deltas = deltas[1:]
    return round(statistics.median(deltas), 2), round(sorted(deltas)[int(len(deltas) * 0.95)], 2)


def run(report, base, headless):
    measures, states = report["measures"], report["states"]
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=headless, args=GPU_ARGS)
        desktop = new_context(browser, viewport={"width": 1440, "height": 900})

        # An empty page shows what this display and browser can do at best (not every screen is exactly 60 Hz).
        page = desktop.new_page()
        page.set_content("<!doctype html><title>Baseline</title>")
        measures["baseline_frame_median_ms"] = frame_stats(page.evaluate(FRAME_TIMES))[0]
        page.close()

        page = desktop.new_page()
        page.goto(f"{base}/")
        states["desktop"] = settle(page)
        if states["desktop"] == ["live", "ok"]:
            page.wait_for_function("document.querySelector('[data-hero]').__weave?.mode === 'quilt'"
                                   " && performance.getEntriesByName('weave:first-live-frame').length === 1")
            measures["first_live_frame_ms"] = round(
                page.evaluate("performance.getEntriesByName('weave:first-live-frame')[0].startTime"), 1)
            page.wait_for_timeout(SETTLE_AFTER_LIVE_MS)
            before = page.eval_on_selector("[data-hero]", FRAMES)
            measures["frame_median_ms"], measures["frame_p95_ms"] = frame_stats(page.evaluate(FRAME_TIMES))
            # The hook outlives a teardown (w302), so the window counts only if the quilt is still live and running.
            state, reason = page.eval_on_selector("[data-hero]", HERO)
            states["desktop_after_idle"] = {"state": state, "reason": reason,
                                            "frames_rose": page.eval_on_selector("[data-hero]", FRAMES) > before}
        measures["home_transfer_bytes"] = page.evaluate(TRANSFER)
        measures["headroom_bytes"] = BUDGETS["home_transfer_bytes"] - measures["home_transfer_bytes"]

        calm = new_context(browser, viewport={"width": 1440, "height": 900}, reduced_motion="reduce")
        page = calm.new_page()
        page.goto(f"{base}/")
        states["reduced_motion"] = settle(page)
        page.wait_for_function("document.querySelector('.hero-still').complete")
        measures["still_size"] = page.eval_on_selector(".hero-still", "img => [img.naturalWidth, img.naturalHeight]")

        phone = new_context(browser, viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True,
                            device_scale_factor=2)
        page = phone.new_page()
        page.goto(f"{base}/")
        states["phone"] = settle(page)
        states["phone_no_horizontal_scroll"] = page.evaluate(
            "document.documentElement.scrollWidth <= window.innerWidth")
        browser.close()


def budgets_for(measures):
    """BUDGETS, with frame_median_ms set from the measured baseline when there is one."""
    baseline = measures.get("baseline_frame_median_ms")
    return dict(BUDGETS) if baseline is None else {**BUDGETS, "frame_median_ms": frame_budget(baseline)}


def check(report):
    """Every failing row of `report`, named by its key; pure, and closed: a missing measure or state fails."""
    measures, states = report.get("measures", {}), report.get("states", {})
    failures = []
    budgets = budgets_for(measures)
    if measures.get("baseline_frame_median_ms") is None:
        failures.append("baseline_frame_median_ms is missing, so frame_median_ms is checked against 16.7")
    idle = states.get("desktop_after_idle")
    idle_ok = isinstance(idle, dict) and idle.get("state") == "live" and idle.get("frames_rose") is True
    for key, limit in budgets.items():
        value = measures.get(key)
        if value is None or value > limit:
            failures.append(f"{key} = {value} (budget {limit})")
        elif key.startswith("frame_") and not idle_ok:
            failures.append(f"{key} = {value} was not measured on a live, running quilt (after the window: {idle})")
    if measures.get("still_size") != list(STILL_SIZE):
        failures.append(f"still_size = {measures.get('still_size')} (expected {list(STILL_SIZE)})")
    for name, expected in EXPECTED_STATES.items():
        if states.get(name) != expected:
            failures.append(f"{name}: hero is {states.get(name)} (expected {expected})")
    if states.get("phone_no_horizontal_scroll") is not True:
        failures.append("phone: horizontal scroll at 390 px")
    return failures


def main():
    parser = argparse.ArgumentParser(description="Check WEAVE's budgets and hero states on this machine.")
    parser.add_argument("--headless", action="store_true", help="a smoke run only; frame times need a visible window")
    args = parser.parse_args()
    OUT.mkdir(exist_ok=True)
    report = {"budgets": {}, "measures": {}, "states": {}, "failures": []}
    server, base = serve.start(PUBLIC)
    try:
        run(report, base, args.headless)
    finally:
        server.shutdown()
        server.server_close()
    report["measures"]["still_bytes"] = (PUBLIC / "assets" / "weave-still.jpg").stat().st_size
    report["budgets"] = budgets_for(report["measures"])
    report["failures"] = check(report)
    (OUT / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"measures": report["measures"], "states": report["states"]}, indent=2))
    print("\n".join(["FAILURES:", *report["failures"]]) if report["failures"] else "All budgets and states OK.")
    return 1 if report["failures"] else 0


if __name__ == "__main__":
    sys.exit(main())
