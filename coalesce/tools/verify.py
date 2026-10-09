"""Screenshot every hero state and check the budgets on this machine.

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
BUDGETS = {
    "home_transfer_bytes": 1_500_000,
    "glb_bytes": 150_000,
    "still_bytes": 250_000,
    "frame_median_ms": 16.7,
    "frame_p95_ms": 33.0,
}
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


def settle(page):
    page.wait_for_function(SETTLED, timeout=30000)
    return page.eval_on_selector("[data-hero]", "el => [el.dataset.heroState, el.dataset.heroReason]")


def shot(report, page, name, full_page=False):
    page.screenshot(path=str(OUT / f"{name}.png"), full_page=full_page)
    report["screens"].append(f"{name}.png")


def run(report, base, headless):
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=headless, args=GPU_ARGS)
        desktop = browser.new_context(viewport={"width": 1440, "height": 900})

        # An empty page shows what this display and browser can do at best (not every screen is exactly 60 Hz).
        page = desktop.new_page()
        page.set_content("<!doctype html><title>Baseline</title>")
        baseline = page.evaluate(FRAME_TIMES)[1:]
        report["measures"]["baseline_frame_median_ms"] = round(statistics.median(baseline), 2)
        page.close()

        page = desktop.new_page()
        page.goto(f"{base}/")
        report["states"]["home"] = settle(page)
        page.wait_for_timeout(4500)
        shot(report, page, "home-live")
        deltas = page.evaluate(FRAME_TIMES)[1:]
        report["measures"]["frame_median_ms"] = round(statistics.median(deltas), 2)
        report["measures"]["frame_p95_ms"] = round(sorted(deltas)[int(len(deltas) * 0.95)], 2)
        report["measures"]["home_transfer_bytes"] = page.evaluate(TRANSFER)
        box = page.locator("[data-hero]").bounding_box()
        cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
        page.mouse.move(cx, cy)
        page.wait_for_timeout(700)
        shot(report, page, "home-hover")
        page.mouse.click(cx, cy)
        page.wait_for_timeout(350)
        shot(report, page, "home-burst")
        page.locator("[data-pause]").click()
        shot(report, page, "home-paused")
        shot(report, page, "home-full", full_page=True)

        page = desktop.new_page()
        page.goto(f"{base}/help/")
        report["states"]["help"] = settle(page)
        page.wait_for_timeout(4500)
        box = page.locator("[data-hero]").bounding_box()
        page.mouse.move(box["x"] + box["width"] * 0.45, box["y"] + box["height"] * 0.5)
        page.wait_for_timeout(1200)
        shot(report, page, "help-magnifier")
        page.mouse.move(box["x"] + box["width"] * 0.62, box["y"] + box["height"] * 0.7)
        page.wait_for_timeout(1200)
        shot(report, page, "help-magnifier-2")
        shot(report, page, "help-full", full_page=True)

        calm = browser.new_context(viewport={"width": 1440, "height": 900}, reduced_motion="reduce")
        phone = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True,
                                    has_touch=True, device_scale_factor=2)
        for name, url in (("home", "/"), ("help", "/help/")):
            page = calm.new_page()
            page.goto(base + url)
            report["states"][f"{name}-reduced-motion"] = settle(page)
            shot(report, page, f"{name}-reduced-motion")
            page = phone.new_page()
            page.goto(base + url)
            report["states"][f"{name}-phone"] = settle(page)
            if not page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"):
                report["failures"].append(f"{name}: horizontal scroll at 390 px")
            shot(report, page, f"{name}-phone", full_page=True)
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
    report["measures"]["glb_bytes"] = (ASSETS / "coalesce.glb").stat().st_size
    report["measures"]["still_bytes"] = max((ASSETS / n).stat().st_size for n in ("home-still.webp", "help-still.webp"))
    budgets = dict(BUDGETS)
    # The hero may not be slower than the display allows: 16.7 ms on a 60 Hz screen, or an empty page's
    # frame time plus 1 ms where the display itself runs slower than that.
    baseline = report["measures"].get("baseline_frame_median_ms", 0)
    budgets["frame_median_ms"] = max(BUDGETS["frame_median_ms"], round(baseline + 1.0, 2))
    report["budgets"] = budgets
    for key, limit in budgets.items():
        value = report["measures"].get(key)
        if value is None or value > limit:
            report["failures"].append(f"{key} = {value} (budget {limit})")
    for name, (state, reason) in report["states"].items():
        if (state == "live") != (name in ("home", "help")):
            report["failures"].append(f"{name}: hero is {state} ({reason})")
    (OUT / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report["measures"], indent=2))
    print("\n".join(["FAILURES:", *report["failures"]]) if report["failures"] else "All budgets and states OK.")
    return 1 if report["failures"] else 0


if __name__ == "__main__":
    sys.exit(main())
