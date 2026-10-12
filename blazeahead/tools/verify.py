"""Screenshot every page and tour stop, and check the budgets on this machine.

  .venv/Scripts/python tools/verify.py [--headless]

Writes verify-output/*.png and verify-output/report.json and exits 1 if a budget or state check fails.
Runs a visible browser by default so the frame timings use the real GPU.
"""
import argparse
import json
import statistics
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import serve  # noqa: E402

OUT = ROOT / "verify-output"
ASSETS = ROOT / "public" / "assets"
GPU_ARGS = ["--use-angle=d3d11", "--enable-gpu", "--ignore-gpu-blocklist"]
STOPS = ["continuity", "scaffolding", "knowledge", "in-flight"]
BUDGETS = {
    "home_transfer_bytes": 2_500_000,
    "glb_bytes": 600_000,
    "world_json_bytes": 900_000,
    "still_bytes": 300_000,
    "frame_median_ms": 16.7,
    "frame_p95_ms": 33.0,
    "walk_frame_p95_ms": 40.0,
}
FRAME_TIMES = """(ms) => new Promise((resolve) => {
  const deltas = []; let last = performance.now(); const end = last + ms;
  const tick = (now) => { deltas.push(now - last); last = now;
    if (now < end) requestAnimationFrame(tick); else resolve(deltas); };
  requestAnimationFrame(tick);
})"""
TRANSFER = """() => performance.getEntriesByType('navigation').concat(performance.getEntriesByType('resource'))
  .reduce((sum, e) => sum + (e.transferSize || e.encodedBodySize || 0), 0)"""
SETTLED = """() => { const d = document.querySelector('[data-stage]').dataset;
  return d.stageState && d.stageReason !== 'loading'; }"""
AT_STOP = """(i) => document.body.dataset.tourIndex === String(i) && document.body.dataset.tourWalking === 'false'"""


def settle(page):
    page.wait_for_function(SETTLED, timeout=45000)
    return page.eval_on_selector("[data-stage]", "el => [el.dataset.stageState, el.dataset.stageReason]")


def shot(report, page, name, full_page=False):
    page.screenshot(path=str(OUT / f"{name}.png"), full_page=full_page)
    report["screens"].append(f"{name}.png")


def percentile(values, q):
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(len(ordered) * q))]


def run(report, base, headless):
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=headless, args=GPU_ARGS)
        desktop = browser.new_context(viewport={"width": 1440, "height": 900})

        # An empty page shows what this display and browser can do at best (not every screen is exactly 60 Hz).
        page = desktop.new_page()
        page.set_content("<!doctype html><title>Baseline</title>")
        baseline = page.evaluate(FRAME_TIMES, 4000)[1:]
        report["measures"]["baseline_frame_median_ms"] = round(statistics.median(baseline), 2)
        page.close()

        # Home: the live trailhead, idle, hover and paused
        page = desktop.new_page()
        page.goto(f"{base}/")
        report["states"]["home"] = settle(page)
        page.wait_for_timeout(3000)
        shot(report, page, "home-live")
        deltas = page.evaluate(FRAME_TIMES, 5000)[1:]
        report["measures"]["frame_median_ms"] = round(statistics.median(deltas), 2)
        report["measures"]["frame_p95_ms"] = round(percentile(deltas, 0.95), 2)
        report["measures"]["home_transfer_bytes"] = page.evaluate(TRANSFER)
        box = page.locator("[data-stage]").bounding_box()
        page.mouse.move(box["x"] + box["width"] * 0.62, box["y"] + box["height"] * 0.86)
        page.wait_for_timeout(700)
        shot(report, page, "home-hover")
        page.locator("[data-pause]").click()
        shot(report, page, "home-paused")
        shot(report, page, "home-full", full_page=True)
        if not page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"):
            report["failures"].append("home: horizontal scroll at 1440 px")

        # Tour: walk from the trailhead through every stop, timing the frames of one walk
        page = desktop.new_page()
        page.goto(f"{base}/tour/")
        report["states"]["tour"] = settle(page)
        page.wait_for_function(AT_STOP, arg=0, timeout=30000)
        page.wait_for_timeout(400)   # the card fades in
        shot(report, page, "tour-continuity")
        for i in range(1, len(STOPS)):
            page.keyboard.press("ArrowRight")
            page.wait_for_function("() => document.body.dataset.tourWalking === 'true'", timeout=5000)
            if i == 1:
                walk = page.evaluate(FRAME_TIMES, 1500)[1:]
                report["measures"]["walk_frame_p95_ms"] = round(percentile(walk, 0.95), 2)
            else:
                page.wait_for_timeout(900)
                if i == 2:
                    shot(report, page, "tour-walking")
            page.wait_for_function(AT_STOP, arg=i, timeout=30000)
            page.wait_for_timeout(400)
            shot(report, page, f"tour-{STOPS[i]}")
            if STOPS[i] == "knowledge":
                page.locator("[data-card-next]").click()
                page.wait_for_timeout(400)
                shot(report, page, "tour-kb-trail")
                page.locator("[data-kb-unfold]").click()
                page.wait_for_function("() => document.querySelector('[data-kb-sheet]').open", timeout=5000)
                page.wait_for_timeout(300)
                shot(report, page, "tour-kb-sheet")
                page.keyboard.press("Escape")
                page.locator("[data-card-prev]").click()
        page.goto(f"{base}/tour/#continuity")
        settle(page)
        page.wait_for_function(AT_STOP, arg=0, timeout=30000)
        page.wait_for_timeout(600)
        rock = page.evaluate("""() => {
            const s = document.querySelector('[data-stage]').__blaze; if (!s || !s.view) return null;
            const r = s.view.canvas.getBoundingClientRect();
            for (let y = 0.25; y < 0.8; y += 0.02) for (let x = 0.1; x < 0.9; x += 0.02)
              if (s.view.rockAt(x * 2 - 1, 1 - y * 2)) return [r.left + x * r.width, r.top + y * r.height];
            return null; }""")
        if rock:
            page.mouse.move(rock[0], rock[1])
            page.wait_for_timeout(300)
            shot(report, page, "tour-rock-tooltip")

        # Help: the junction
        page = desktop.new_page()
        page.goto(f"{base}/help/")
        report["states"]["help"] = settle(page)
        page.wait_for_timeout(2500)
        shot(report, page, "help-live")
        shot(report, page, "help-full", full_page=True)

        # Reduced motion: stills everywhere, the tour still works
        calm = browser.new_context(viewport={"width": 1440, "height": 900}, reduced_motion="reduce")
        for name, url in (("home", "/"), ("tour", "/tour/#knowledge"), ("help", "/help/")):
            page = calm.new_page()
            page.goto(base + url)
            report["states"][f"{name}-reduced-motion"] = settle(page)
            page.wait_for_timeout(500)
            shot(report, page, f"{name}-reduced-motion")
        # A small desktop, and a 1080p laptop at 125 % scaling (a short window)
        for (width, height), suffix, pages in (
                ((1024, 768), "1024", (("home", "/"), ("tour", "/tour/#in-flight"), ("help", "/help/"))),
                ((1536, 730), "short", (("home", "/"), ("tour", "/tour/#scaffolding"), ("tour-kb", "/tour/#knowledge")))):
            ctx = browser.new_context(viewport={"width": width, "height": height})
            for name, url in pages:
                page = ctx.new_page()
                page.goto(base + url)
                settle(page)
                page.wait_for_timeout(800)
                if not page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"):
                    report["failures"].append(f"{name}: horizontal scroll at {width} px")
                shot(report, page, f"{name}-{suffix}")
                if name == "tour-kb":
                    for _ in range(5):          # the last trail page: a lower trail, lit, just above the card
                        page.locator("[data-card-next]").click()
                    page.wait_for_timeout(400)
                    shot(report, page, f"tour-kb-{suffix}-trail")
        browser.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--headless", action="store_true")
    args = parser.parse_args()
    OUT.mkdir(exist_ok=True)
    report = {"screens": [], "states": {}, "measures": {}, "failures": []}
    server, base = serve.start(ROOT / "public")
    try:
        run(report, base, args.headless)
    finally:
        server.shutdown()
    report["measures"]["glb_bytes"] = (ASSETS / "blazeahead.glb").stat().st_size
    report["measures"]["world_json_bytes"] = (ASSETS / "world.json").stat().st_size
    report["measures"]["still_bytes"] = max(p.stat().st_size for p in (ASSETS / "stills").glob("*.webp"))
    budgets = dict(BUDGETS)
    # The scene may not be slower than the display allows: 16.7 ms on a 60 Hz screen, or an empty page's
    # frame time plus 1 ms where the display itself runs slower than that.
    baseline = report["measures"].get("baseline_frame_median_ms", 0)
    budgets["frame_median_ms"] = max(BUDGETS["frame_median_ms"], round(baseline + 1.0, 2))
    report["budgets"] = budgets
    for key, limit in budgets.items():
        value = report["measures"].get(key)
        if value is None or value > limit:
            report["failures"].append(f"{key} = {value} (budget {limit})")
    for name, (state, reason) in report["states"].items():
        if (state == "live") != (name in ("home", "tour", "help")):
            report["failures"].append(f"{name}: stage is {state} ({reason})")
    (OUT / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report["measures"], indent=2))
    print("\n".join(["FAILURES:", *report["failures"]]) if report["failures"] else "All budgets and states OK.")
    return 1 if report["failures"] else 0


if __name__ == "__main__":
    sys.exit(main())
