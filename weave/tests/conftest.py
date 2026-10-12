import sys
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent / "tools"))
import serve  # noqa: E402
from helpers import canvas_hashes, font_warnings, open_faces, open_paint  # noqa: E402

GPU_ARGS = ["--use-angle=d3d11", "--enable-gpu", "--ignore-gpu-blocklist"]
NO_WEBGL_ARGS = ["--disable-webgl", "--disable-webgl2", "--disable-3d-apis"]


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


@pytest.fixture
def make_page(browser):
    contexts = []

    def _make(target_browser=None, **context_args):
        args = {"viewport": {"width": 1440, "height": 900}, **context_args}
        ctx = (target_browser or browser).new_context(**args)
        contexts.append(ctx)
        return ctx.new_page()

    yield _make
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

    def make(**context_args):
        ctx = browser.new_context(**{"viewport": {"width": 1440, "height": 900}, **context_args})
        contexts.append(ctx)
        return ctx.new_page()

    messages = []
    try:
        page, errors = open_faces(make, base_url, messages=messages)
        assert errors == [] and font_warnings(messages) == []
        assert page.get_attribute("body", "data-painted") == "fonts"
        return canvas_hashes(page)
    finally:
        for ctx in contexts:
            ctx.close()
