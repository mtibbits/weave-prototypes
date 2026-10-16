"""Capture WEAVE's still from the live rest-pose render (D4, D19, D34).

From the repo root, with the venv active:

  python weave/tools/capture_still.py [--which {home,help,all}] [--out DIR] [--query K=V]...

Opens each target at ?pose=rest&frame=still in headless Chromium (1600 x 1000, scale 1, verify.py's GPU flags and
clock rule), waits until the scene is live, the quilt has settled, the still has faded out and 2.5 s have passed
since the first live frame with frames still advancing, then saves a JPEG at the first quality of a ladder whose file
fits 250 KB. Writes weave/public/assets/<file> (or DIR/<file> with --out) only when every requested target was
captured; a fallback to the still, a stopped loop or an over-budget file writes nothing and exits 1. --which help
exits 2 until the Help page registers its target (#19). --out and --query are for tests.

The watchdog: __weave exposes no watchdog verdict, so the 2.5 s wall-time wait is a lower bound on the watchdog's
2 s window only while frames take no more than 100 ms (its per-frame delta is capped); the state is read again after
the shots, so a teardown during the wait or the shots still writes nothing.
"""
import argparse
import importlib.util
import os
import re
import sys
from pathlib import Path

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

WEAVE = Path(__file__).resolve().parents[1]
PUBLIC = WEAVE / "public"
DEFAULT_OUT = PUBLIC / "assets"


def _load_verify():
    """verify.py, loaded by path: its GPU flags, waits, context and still budget are the capture's too."""
    spec = importlib.util.spec_from_file_location("weave_verify", Path(__file__).with_name("verify.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


verify = _load_verify()

# name -> (page path served from weave/public, output file name). #19 adds help; #23 moves home's output.
TARGETS = {"home": ("/index.html", "weave-still.jpg")}
RECIPE = "pose=rest&frame=still"
VIEWPORT = {"width": 1600, "height": 1000}
QUALITIES = (90, 85, 80, 75, 70, 65, 60)
LIMIT = verify.BUDGETS["still_bytes"]
QUERY = re.compile(r"[A-Za-z][A-Za-z0-9_]*=[^&#\s]*")


class CaptureError(Exception):
    """A capture that must write nothing; its text follows `{name}: ` in the message."""


def query_pair(value):
    if not QUERY.fullmatch(value):
        raise argparse.ArgumentTypeError(f"{value!r} is not one K=V pair (a bare flag is written K=)")
    return value


def target_url(base, path, queries):
    """The target's page at the capture recipe, with each extra K=V pair appended in order."""
    return f"{base}{path}?" + "&".join([RECIPE, *queries])


def build_parser():
    parser = argparse.ArgumentParser(prog="capture_still.py",
                                     description="Capture WEAVE's still from the live rest-pose render.")
    parser.add_argument("--which", choices=("home", "help", "all"), default="all",
                        help="the target to capture; all (the default) is every registered target")
    parser.add_argument("--out", metavar="DIR", help=f"write here instead of {DEFAULT_OUT} (for tests)")
    parser.add_argument("--query", metavar="K=V", action="append", default=[], type=query_pair,
                        help="append K=V to the recipe's query (repeatable; for tests)")
    return parser


def open_context(browser):
    """The recipe's context; verify.new_context pins the clock, so the clock rule has one home."""
    return verify.new_context(browser, viewport=VIEWPORT, device_scale_factor=1)


def fit(shoot, qualities=QUALITIES, limit=LIMIT):
    """(quality, bytes) of the first shoot(quality) whose bytes fit `limit`; CaptureError if none does."""
    for quality in qualities:
        data = shoot(quality)
        if len(data) <= limit:
            return quality, data
    raise CaptureError(f"{len(data):,} B at quality {quality} is over {limit:,} B")


# Synchronous predicates (a returned Promise reads as truthy; Issue-9). FADED: the still has faded out under the live
# scene, or the stage has left live (the next check then says why).
FADED = """() => { const el = document.querySelector('[data-hero]');
  if (el.dataset.heroState !== 'live') return true;
  return el.classList.contains('is-live') && getComputedStyle(el.querySelector('.hero-still')).opacity === '0'; }"""
SINCE_LIVE = """() => { const m = performance.getEntriesByName('weave:first-live-frame')[0];
  return m ? performance.now() - m.startTime : null; }"""
AFTER_LIVE = f"(ms) => ({SINCE_LIVE})() >= ms"
STAGE_RECT = "el => { const r = el.getBoundingClientRect(); return [r.x, r.y, r.width, r.height]; }"
STILL_OPACITY = "el => getComputedStyle(el.querySelector('.hero-still')).opacity"


def require_live(page):
    """(state, reason) of the hero; CaptureError when it has fallen back to the still."""
    state, reason = page.eval_on_selector("[data-hero]", verify.HERO)
    if state != "live":
        raise CaptureError(f"the scene fell back to the still ({reason})")
    return state, reason


def wait(page, what, predicate, timeout, arg=None):
    """wait_for_function, with a timeout read as a fallback when the stage has left live."""
    try:
        page.wait_for_function(predicate, arg=arg, timeout=timeout)
    except PlaywrightError as exc:
        require_live(page)
        raise CaptureError(f"timed out waiting for {what}") from exc


def capture(browser, base, name, queries):
    """(bytes, quality, info) of target `name`'s JPEG, taken in memory; CaptureError when it must write nothing."""
    path, _ = TARGETS[name]
    context = open_context(browser)
    try:
        page = context.new_page()
        page.goto(target_url(base, path, queries))
        wait(page, "the hero to settle", verify.SETTLED, 30000)
        require_live(page)
        wait(page, "the settled quilt", verify.QUILT_SETTLED, verify.SETTLED_TIMEOUT_MS)
        before = page.eval_on_selector("[data-hero]", verify.FRAMES)
        wait(page, "the still to fade out", FADED, 5000)
        wait(page, "the watchdog's window", AFTER_LIVE, verify.SETTLE_AFTER_LIVE_MS + 10000,
             arg=verify.SETTLE_AFTER_LIVE_MS)
        # The state first, so a teardown during the wait reports its reason, not a stopped loop.
        state, reason = require_live(page)
        advanced = page.eval_on_selector("[data-hero]", verify.FRAMES) - before
        if advanced <= 0:
            raise CaptureError("the frame loop stopped before the watchdog ruled")
        rect = page.eval_on_selector("[data-hero]", STAGE_RECT)
        if rect != [0, 0, VIEWPORT["width"], VIEWPORT["height"]]:
            raise CaptureError(f"the stage is {rect[2]:g} x {rect[3]:g},"
                               f" not {VIEWPORT['width']} x {VIEWPORT['height']}")
        info = {"state": state, "reason": reason, "after_live_ms": round(page.evaluate(SINCE_LIVE), 1),
                "frames_advanced": advanced, "still_opacity": page.eval_on_selector("[data-hero]", STILL_OPACITY)}
        quality, data = fit(lambda q: page.screenshot(type="jpeg", quality=q))
        require_live(page)
        return data, quality, info
    finally:
        context.close()


def main(argv=None):
    args = build_parser().parse_args(argv)
    names = list(TARGETS) if args.which == "all" else [args.which]
    for name in names:
        if name not in TARGETS:
            print(f"capture_still.py: no '{name}' target is registered yet; registered: {', '.join(TARGETS)}",
                  file=sys.stderr)
            return 2
    out = Path(args.out) if args.out else DEFAULT_OUT
    # Every target is captured in memory first; nothing is written unless all of them succeeded.
    shots = []
    server, base = verify.serve.start(PUBLIC)
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(args=verify.GPU_ARGS)
            try:
                for name in names:
                    try:
                        data, quality, _ = capture(browser, base, name, args.query)
                    except CaptureError as exc:
                        print(f"capture_still.py: {name}: {exc}; nothing written", file=sys.stderr)
                        return 1
                    shots.append((name, data, quality))
            finally:
                browser.close()
    finally:
        server.shutdown()
        server.server_close()
    out.mkdir(parents=True, exist_ok=True)
    for name, data, quality in shots:
        path = out / TARGETS[name][1]
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_bytes(data)
        os.replace(tmp, path)
        print(f"capture_still.py: wrote {path} ({VIEWPORT['width']} x {VIEWPORT['height']}, JPEG quality {quality},"
              f" {len(data):,} B)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
