import os
import re
import sys
from datetime import datetime
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent / "tools"))
import serve  # noqa: E402
# weave/tools holds #12's fixed instant (D11), as Coalesce's conftest puts its tools/ on the path for serve.py.
sys.path.insert(0, str(ROOT / "tools"))
from fixed_clock import FIXED_DATE, FIXED_INSTANT  # noqa: E402
from helpers import canvas_hashes, font_warnings, open_faces, open_paint  # noqa: E402

GPU_ARGS = ["--use-angle=d3d11", "--enable-gpu", "--ignore-gpu-blocklist"]
NO_WEBGL_ARGS = ["--disable-webgl", "--disable-webgl2", "--disable-3d-apis"]

# The default clock (#12): every context the fixture makes is pinned to it before its first page. WEAVE_TEST_CLOCK
# replaces it for a run (#16's in-window run); a bad value fails the run, never falling back to FIXED_INSTANT.
CLOCK_ENV = "WEAVE_TEST_CLOCK"
INSTANT_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(\.\d{1,3})?)?(Z|[+-]\d{2}:\d{2})?")
DEFAULT_CLOCK = FIXED_INSTANT
_DEFAULT = object()


def check_instant(value, name):
    """`value` when it is a full date-time Playwright and Python agree on; else ValueError naming `name`.

    A bare date is refused: Playwright reads it as UTC midnight, the evening before in EDT."""
    if isinstance(value, str) and INSTANT_RE.fullmatch(value):
        try:
            datetime.fromisoformat(value)
            return value
        except ValueError:
            pass
    raise ValueError(f"{name} must be a full local date-time such as 2026-10-10T09:00:00, or one with an "
                     f"offset, never a bare date; got {value!r}")


def resolve_default_clock(environ):
    """The run's default instant: `environ[CLOCK_ENV]` when the key is set (even empty), checked; else FIXED_INSTANT."""
    if CLOCK_ENV in environ:
        return check_instant(environ[CLOCK_ENV], CLOCK_ENV)
    return FIXED_INSTANT


def pytest_configure(config):
    global DEFAULT_CLOCK
    try:
        DEFAULT_CLOCK = resolve_default_clock(os.environ)
    except ValueError as exc:
        raise pytest.UsageError(str(exc)) from exc


@pytest.fixture(scope="session")
def base_url():
    server, url = serve.start(ROOT)
    yield url
    server.shutdown()
    server.server_close()


@pytest.fixture(scope="session")
def playwright_session():
    with sync_playwright() as pw:
        yield pw


@pytest.fixture(scope="session")
def browser(playwright_session):
    b = playwright_session.chromium.launch(args=GPU_ARGS)
    yield b
    b.close()


@pytest.fixture(scope="session")
def browser_no_webgl(playwright_session):
    b = playwright_session.chromium.launch(args=NO_WEBGL_ARGS)
    yield b
    b.close()


def page_factory(browser, contexts):
    """make(target_browser=None, clock=<the default>, **context_args): a page in a new 1440x900 context, recorded in
    `contexts`. The context's clock is pinned to DEFAULT_CLOCK, to `clock` when it is another instant, or left real
    when it is None."""
    def make(target_browser=None, clock=_DEFAULT, **context_args):
        # Read at call time, so the instant is the one pytest_configure resolved.
        if clock is _DEFAULT:
            instant = DEFAULT_CLOCK
        elif clock is None:
            instant = None
        else:
            instant = check_instant(clock, "make_page(clock=...)")
        ctx = (target_browser or browser).new_context(**{"viewport": {"width": 1440, "height": 900}, **context_args})
        # Recorded before the pin, so a context whose pin Playwright rejects is still closed.
        contexts.append(ctx)
        if instant is not None:
            ctx.clock.set_fixed_time(instant)
        return ctx.new_page()

    return make


@pytest.fixture
def make_page(browser):
    contexts = []
    yield page_factory(browser, contexts)
    for ctx in contexts:
        ctx.close()


@pytest.fixture
def js(make_page, base_url):
    page = make_page()
    page.goto(f"{base_url}/tests/blank.html")

    def run(body):
        return page.evaluate(f"async () => {{ {body} }}")

    return run


@pytest.fixture
def paint_js(make_page, base_url):
    """Like `js`, on a blank page with weave.css's real fonts loaded (fontsReady() must say true) and the
    canvas hash helpers defined. `run.page` is the page and `run.console` every (type, text) console message
    since before the font wait."""
    return open_paint(make_page, base_url)


@pytest.fixture(scope="session")
def faces_baseline(browser, base_url):
    """The default faces page's canvas hashes, from one fresh context with the real fonts and no warnings."""
    contexts = []
    messages = []
    try:
        page, errors = open_faces(page_factory(browser, contexts), base_url, messages=messages)
        assert errors == [] and font_warnings(messages) == []
        assert page.get_attribute("body", "data-painted") == "fonts"
        return canvas_hashes(page)
    finally:
        for ctx in contexts:
            ctx.close()
