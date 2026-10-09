import os
import sys
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import serve  # noqa: E402

GPU_ARGS = ["--use-angle=d3d11", "--enable-gpu", "--ignore-gpu-blocklist"]
NO_WEBGL_ARGS = ["--disable-webgl", "--disable-webgl2", "--disable-3d-apis"]
DEFAULT_BLENDER = r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"


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


@pytest.fixture(scope="session")
def blender_exe():
    exe = os.environ.get("BLENDER", DEFAULT_BLENDER)
    if not Path(exe).is_file():
        pytest.skip(f"Blender not found at {exe}")
    return exe
