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


def capture(browser, base, name, queries):
    raise NotImplementedError


def main(argv=None):
    args = build_parser().parse_args(argv)
    names = list(TARGETS) if args.which == "all" else [args.which]
    for name in names:
        if name not in TARGETS:
            print(f"capture_still.py: no '{name}' target is registered yet; registered: {', '.join(TARGETS)}",
                  file=sys.stderr)
            return 2
    raise NotImplementedError


if __name__ == "__main__":
    sys.exit(main())
