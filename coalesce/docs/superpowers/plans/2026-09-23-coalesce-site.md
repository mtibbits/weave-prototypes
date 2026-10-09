# Coalesce Project Site Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the two-page static Coalesce site (Home and Help) with a Blender-authored, Three.js-animated crowd hero, packaged as a zip for the team's internal GitLab Pages.

**Architecture:**
- A pure-Python layout module and a headless Blender script produce `coalesce.glb`, `layout.json` and two still images.
- In the browser, pure ES modules (`config.js`, `eligibility.js`, `motion.js`) hold the logic and are unit-tested in Chromium through Playwright.
- `crowd.js` draws with vendored Three.js. `hero.js` wires everything to the page and falls back to the still image whenever 3D shouldn't run.
- There is no build step: `public/` is published as-is.

**Tech Stack:**
- HTML, CSS and ES modules.
- Three.js 0.170.0 (vendored).
- Blender 5.2.2 LTS (headless Python).
- Python 3.13 with pytest and Playwright (Chromium) for tests and tooling.
- Windows PowerShell 5.1 for the release script.

**Spec:** `docs/superpowers/specs/2026-09-23-coalesce-site-design.md`

## Global Constraints

- **Static files only:** no server code, no build step, nothing loaded from the internet at runtime. Every URL inside `public/` is relative.
- **Three.js is pinned to 0.170.0:** `build/three.module.min.js` plus `GLTFLoader.js`, `BufferGeometryUtils.js` and `RoomEnvironment.js`, vendored in `public/vendor/three/` with its `LICENSE`.
- **Fonts:**
  - Instrument Serif (regular and italic) and Instrument Sans (variable, 400–700).
  - Latin-subset `.woff2` files in `public/fonts/`, with `OFL.txt`.
- **Nothing is copied from `cth9191/blender-to-web`** (all rights reserved).
- **Palette and type:**
  - Colors: paper `#F4F0E8`, ink `#1B2423`, muted `#55605E`, teal `#1D5E5B`, terracotta `#C4623A`, line `#E2DBCD`, card `#FFFFFF`.
  - Display font `Instrument Serif`, body font `Instrument Sans`. Single light theme.
- **Copy:** page copy is spec §5 verbatim. A link whose setting is empty shows **Link coming soon**.
- **Budgets (spec §6.6):**
  - Home first-visit transfer ≤ 1.5 MB.
  - `coalesce.glb` ≤ 150 KB; each still ≤ 250 KB.
  - ≤ 300 people, plus 3 spares on Home.
  - Frame median ≤ 16.7 ms and p95 ≤ 33 ms at 1440 × 900 on this laptop (Intel Iris Plus).
- **Crowd count:** spec §6.1 says "about 290", but its own geometry yields about 170. Tests bound the count to 150–300. Don't tune spacing to reach 290.
- **Blender:** `C:\Program Files\Blender Foundation\Blender 5.2\blender.exe` (override with env var `BLENDER`). Always run it with `-b --factory-startup --python-exit-code 1`.
- **Python:** the venv lives at `.venv`. Run everything from the repo root `C:\Programs\src\coalesce-site`, and run tests as `.venv/Scripts/python -m pytest`.
- **Local serving:** use `tools/serve.py`, never bare `python -m http.server`. Windows can map `.js` to `text/plain`, which breaks ES modules.
- **Commits:** use `git commit -F -` with a heredoc. Every message ends with `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.

## Review Focus

1. **Settings pasted wrong.** A trailing slash, no `https://`, a `javascript:` URL, or a number. The link is dropped and shows "Link coming soon"; the page never breaks. Pinned by Task 5 `test_unsafe_or_malformed_links_are_dropped`.
2. **Three.js or `coalesce.glb` can't load** (proxy, 404, offline). The still image stays and there are no uncaught errors. Pinned by Task 10 `test_asset_failure_keeps_still`.
3. **A weak or virtual-desktop GPU.** The hero drops back to the still instead of stuttering. Pinned by the Task 7 watchdog tests and Task 10 `test_slow_machine_falls_back`.
4. **Phones, tablets and "reduce motion" users.** They get the still image and never download Three.js. Pinned by Task 10 `test_reduced_motion_keeps_still_and_skips_three` and `test_touch_device_keeps_still`.
5. **Paused, hidden tab, or scrolled away.** Nothing renders, and on return the motion resumes without a time jump. Pinned by Task 8 `test_advance_caps_large_time_steps` and Task 10 `test_pause_stops_and_resumes_rendering`.

## File Structure

| Path | Responsibility |
|---|---|
| `tools/serve.py` | Local static server with correct MIME types (tests and preview) |
| `tools/fetch_vendor.py` | One-time download of Three.js and the fonts (results are committed) |
| `blender/coalesce_layout.py` | Pure-Python layout: positions, accent flags, camera, magnifier numbers, the `layout.json` document |
| `blender/build_coalesce.py` | Blender: builds meshes, exports GLB + `layout.json`, self-checks, renders stills |
| `public/site-config.js` | The one settings file the owner edits |
| `public/js/config.js` | Validates settings, derives GitLab URLs, fills `[data-link]` / `[data-text]` / `[data-requires]` |
| `public/js/eligibility.js` | Decides live vs. still; frame-time watchdog |
| `public/js/motion.js` | Pure crowd simulation: springs, paths, intro, turnover, burst, hover, magnifier aim |
| `public/js/crowd.js` | Three.js drawing: loads assets, instanced crowd, tilt, pointer ray, magnifier lens |
| `public/js/hero.js` | Orchestration: eligibility, loading, the frame loop, pointer, pause, visibility, watchdog, fallback |
| `public/index.html`, `public/help/index.html`, `public/css/site.css` | The two pages and their styles |
| `tools/verify.py` | Screenshots of every state plus budget measurements |
| `tools/publish-release.ps1` | Uploads the `.xlam` and creates a GitLab release with the direct asset path |
| `tools/package.py` | Builds `dist/coalesce-site.zip` |
| `tests/` | pytest + Playwright tests (not shipped) |

---

### Task 1: Dev server and test harness

**Files:**
- Create: `.gitignore`, `requirements-dev.txt`, `pytest.ini`
- Create: `tools/serve.py`
- Create: `tests/conftest.py`, `tests/helpers.py`, `tests/blank.html`, `tests/harness_probe.js`, `tests/test_harness.py`

**Interfaces:**
- Produces `tools/serve.py`: `start(directory, port=0) -> (server, base_url)` and `Handler`.
- Produces these pytest fixtures:
  - `base_url`: serves the repo root.
  - `browser`: Chromium with GPU flags.
  - `browser_no_webgl`: Chromium with WebGL disabled.
  - `make_page(target_browser=None, **context_args) -> Page`: 1440×900 by default.
  - `js(body) -> Any`: runs an async JS function body inside `/tests/blank.html`, whose import map resolves `three`.
  - `blender_exe`: the Blender executable, or a skip if it's missing.
- Produces `tests/helpers.py`:
  - `collect_errors(page) -> list[str]`
  - `hero_result(page, timeout=20000) -> [state, reason]`
  - `FULL`: a complete settings dict.

- [ ] **Step 1: Create the project files and the venv**

`.gitignore`:
```gitignore
.venv/
__pycache__/
.pytest_cache/
dist/
verify-output/
*.blend1
```

`requirements-dev.txt`:
```text
pytest>=8,<9
playwright>=1.47,<2
```

`pytest.ini`:
```ini
[pytest]
testpaths = tests
addopts = -m "not stills"
markers =
    slow: runs Blender headless (about 30 s)
    stills: renders the Cycles still images (several minutes)
```

Run:
```bash
cd /c/Programs/src/coalesce-site
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements-dev.txt
.venv/Scripts/python -m playwright install chromium
```
Expected: the last command reports Chromium downloaded, with no errors.

- [ ] **Step 2: Write the failing harness tests**

`tests/harness_probe.js`:
```js
export function answer() {
  return 42;
}
```

`tests/test_harness.py`:
```python
import urllib.request


def test_server_serves_js_as_javascript(base_url):
    with urllib.request.urlopen(f"{base_url}/tests/harness_probe.js") as resp:
        assert resp.headers["Content-Type"].startswith("text/javascript")


def test_js_fixture_runs_module_code(js):
    assert js("const m = await import('/tests/harness_probe.js'); return m.answer();") == 42
```

- [ ] **Step 3: Run the tests to see them fail**

Run: `.venv/Scripts/python -m pytest tests/test_harness.py -q`
Expected: ERROR, `fixture 'base_url' not found`.

- [ ] **Step 4: Write the server, fixtures and helpers**

`tools/serve.py`:
```python
"""Serve a folder at http://127.0.0.1 with correct MIME types (Windows can map .js to text/plain).

Usage:  python tools/serve.py [folder] [--port 8000]      (folder defaults to public/)
"""
import argparse
import functools
import http.server
import socketserver
import threading
import time
from pathlib import Path

MIME = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json",
    ".svg": "image/svg+xml",
    ".webp": "image/webp",
    ".png": "image/png",
    ".glb": "model/gltf-binary",
    ".woff2": "font/woff2",
    ".txt": "text/plain; charset=utf-8",
}


class Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map, **MIME}

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, fmt, *args):
        pass


class _Server(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True


def start(directory, port=0):
    """Serve `directory` from a background thread; returns (server, base_url)."""
    handler = functools.partial(Handler, directory=str(directory))
    server = _Server(("127.0.0.1", port), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}"


def main():
    parser = argparse.ArgumentParser(description="Serve a folder locally with correct MIME types.")
    parser.add_argument("folder", nargs="?", default=str(Path(__file__).resolve().parents[1] / "public"))
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    server, url = start(args.folder, args.port)
    print(f"Serving {args.folder} at {url}/  (Ctrl+C to stop)")
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()
```

`tests/conftest.py`:
```python
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
```

`tests/helpers.py`:
```python
"""Shared test helpers. pytest puts tests/ on sys.path, so test modules import this directly."""

FULL = {
    "teamName": "Manpower Systems",
    "gitlabProjectUrl": "https://gitlab.example.com/ops/coalesce/",
    "xlamFileName": "Coalesce.xlam",
    "downloadLink": "direct",
    "version": "2.4.0",
    "releaseDate": "23 Sep 2026",
    "links": {
        "docs": "https://wiki.example.com/coalesce",
        "tutorial": "https://training.example.com/coalesce",
        "serviceDesk": "https://jira.example.com/servicedesk/customer/portal/7",
        "access": "https://access.example.com/coalesce",
    },
}


def collect_errors(page):
    """Record uncaught page errors and console errors from now on; returns the live list."""
    errors = []
    page.on("pageerror", lambda exc: errors.append(f"pageerror: {exc}"))
    page.on("console", lambda msg: errors.append(f"console.error: {msg.text}") if msg.type == "error" else None)
    return errors


def hero_result(page, timeout=20000):
    """Wait until the hero settles (live, or still for a reason other than loading); returns [state, reason]."""
    page.wait_for_function(
        "() => { const d = document.querySelector('[data-hero]')?.dataset;"
        " return !!d && !!d.heroState && d.heroReason !== 'loading'; }",
        timeout=timeout,
    )
    return page.eval_on_selector("[data-hero]", "el => [el.dataset.heroState, el.dataset.heroReason]")
```

`tests/blank.html`:
```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Test harness</title>
  <script type="importmap">
    { "imports": { "three": "/public/vendor/three/build/three.module.min.js", "three/addons/": "/public/vendor/three/examples/jsm/" } }
  </script>
</head>
<body></body>
</html>
```

- [ ] **Step 5: Run the tests to see them pass**

Run: `.venv/Scripts/python -m pytest tests/test_harness.py -q`
Expected: `2 passed`.

- [ ] **Step 6: Commit**

```bash
git add .gitignore requirements-dev.txt pytest.ini tools/serve.py tests/
git commit -q -F - <<'EOF'
test: add local server and Playwright test harness

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
EOF
```

---

### Task 2: Vendor Three.js and the fonts

**Files:**
- Create: `tools/fetch_vendor.py`, `tests/test_vendor.py`
- Generated (committed):
  - `public/vendor/three/build/three.module.min.js`
  - `public/vendor/three/examples/jsm/loaders/GLTFLoader.js`
  - `public/vendor/three/examples/jsm/utils/BufferGeometryUtils.js`
  - `public/vendor/three/examples/jsm/environments/RoomEnvironment.js`
  - `public/vendor/three/LICENSE`
  - `public/fonts/InstrumentSans.woff2`, `public/fonts/InstrumentSerif-Regular.woff2`, `public/fonts/InstrumentSerif-Italic.woff2`, `public/fonts/OFL.txt`

**Interfaces:**
- Consumes the `js` fixture (Task 1).
- Produces the import specifiers `three` and `three/addons/...`, resolved by each page's import map. Produces the font files that `css/site.css` (Task 6) references.

- [ ] **Step 1: Write the failing tests**

`tests/test_vendor.py`:
```python
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
THREE = ROOT / "public" / "vendor" / "three"
FONTS = ROOT / "public" / "fonts"
THREE_FILES = [
    "build/three.module.min.js",
    "examples/jsm/loaders/GLTFLoader.js",
    "examples/jsm/utils/BufferGeometryUtils.js",
    "examples/jsm/environments/RoomEnvironment.js",
    "LICENSE",
]
FONT_FILES = ["InstrumentSans.woff2", "InstrumentSerif-Regular.woff2", "InstrumentSerif-Italic.woff2"]


def test_three_files_present_with_license():
    for rel in THREE_FILES:
        assert (THREE / rel).is_file(), rel
    assert "MIT" in (THREE / "LICENSE").read_text(encoding="utf-8")


def test_three_and_addons_load_in_the_browser(js):
    result = js("""
        const THREE = await import('three');
        const { GLTFLoader } = await import('three/addons/loaders/GLTFLoader.js');
        const { RoomEnvironment } = await import('three/addons/environments/RoomEnvironment.js');
        return [THREE.REVISION, typeof GLTFLoader, typeof RoomEnvironment];
    """)
    assert result == ["170", "function", "function"]


def test_fonts_present_with_license():
    for name in FONT_FILES:
        data = (FONTS / name).read_bytes()
        assert data[:4] == b"wOF2", name
        assert len(data) > 10_000, name
    assert "SIL OPEN FONT LICENSE" in (FONTS / "OFL.txt").read_text(encoding="utf-8").upper()
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `.venv/Scripts/python -m pytest tests/test_vendor.py -q`
Expected: 3 failed (files missing; the browser test fails to import `three`).

- [ ] **Step 3: Write the fetch script**

`tools/fetch_vendor.py`:
```python
"""Download the pinned third-party files the site ships with (run once; the results are committed).

  Three.js 0.170.0 (MIT) from the npm registry           -> public/vendor/three/
  Instrument Serif + Instrument Sans (SIL OFL), latin     -> public/fonts/
"""
import io
import re
import tarfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"
THREE_VERSION = "0.170.0"
THREE_TGZ = f"https://registry.npmjs.org/three/-/three-{THREE_VERSION}.tgz"
THREE_FILES = [
    "build/three.module.min.js",
    "examples/jsm/loaders/GLTFLoader.js",
    "examples/jsm/utils/BufferGeometryUtils.js",
    "examples/jsm/environments/RoomEnvironment.js",
    "LICENSE",
]
FONT_CSS = ("https://fonts.googleapis.com/css2?family=Instrument+Sans:wght@400..700"
            "&family=Instrument+Serif:ital@0;1&display=swap")
FONT_FILES = {
    ("Instrument Sans", "normal"): "InstrumentSans.woff2",
    ("Instrument Serif", "normal"): "InstrumentSerif-Regular.woff2",
    ("Instrument Serif", "italic"): "InstrumentSerif-Italic.woff2",
}
OFL_URLS = {
    "Instrument Sans": "https://raw.githubusercontent.com/google/fonts/main/ofl/instrumentsans/OFL.txt",
    "Instrument Serif": "https://raw.githubusercontent.com/google/fonts/main/ofl/instrumentserif/OFL.txt",
}
BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/128.0 Safari/537.36")


def fetch(url):
    request = urllib.request.Request(url, headers={"User-Agent": BROWSER_UA})
    with urllib.request.urlopen(request, timeout=60) as resp:
        return resp.read()


def vendor_three():
    out = PUBLIC / "vendor" / "three"
    with tarfile.open(fileobj=io.BytesIO(fetch(THREE_TGZ)), mode="r:gz") as tgz:
        for rel in THREE_FILES:
            member = tgz.extractfile(f"package/{rel}")
            if member is None:
                raise SystemExit(f"three {THREE_VERSION} has no {rel}")
            dest = out / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(member.read())
            print("wrote", dest.relative_to(ROOT))


def vendor_fonts():
    out = PUBLIC / "fonts"
    out.mkdir(parents=True, exist_ok=True)
    css = fetch(FONT_CSS).decode("utf-8")
    wanted = dict(FONT_FILES)
    for subset, body in re.findall(r"/\*\s*([\w-]+)\s*\*/\s*@font-face\s*\{(.*?)\}", css, flags=re.S):
        if subset != "latin":
            continue
        family = re.search(r"font-family:\s*'([^']+)'", body).group(1)
        style = re.search(r"font-style:\s*(\w+)", body).group(1)
        url = re.search(r"url\((https://[^)]+\.woff2)\)", body).group(1)
        name = wanted.pop((family, style), None)
        if name:
            (out / name).write_bytes(fetch(url))
            print("wrote", (out / name).relative_to(ROOT))
    if wanted:
        raise SystemExit(f"Google Fonts CSS had no latin face for {sorted(wanted)}")
    licences = [f"==== {family} ====\n\n{fetch(url).decode('utf-8')}" for family, url in OFL_URLS.items()]
    (out / "OFL.txt").write_text("\n\n".join(licences), encoding="utf-8")
    print("wrote", (out / "OFL.txt").relative_to(ROOT))


if __name__ == "__main__":
    vendor_three()
    vendor_fonts()
```

- [ ] **Step 4: Run it, then run the tests to see them pass**

Run: `.venv/Scripts/python tools/fetch_vendor.py` (expected: nine `wrote …` lines), then `.venv/Scripts/python -m pytest tests/test_vendor.py -q`.
Expected: `3 passed`.

- [ ] **Step 5: Commit**

```bash
git add tools/fetch_vendor.py tests/test_vendor.py public/vendor public/fonts
git commit -q -F - <<'EOF'
build: vendor Three.js 0.170.0 and the Instrument fonts

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
EOF
```

---
### Task 3: The figure layout (pure Python)

**Files:**
- Create: `blender/coalesce_layout.py`, `tests/test_layout.py`

**Interfaces:**
- Produces `coalesce_layout` with:
  - Constants: `TOKEN_SCALE`, `CAMERA_TARGET`, `LENS_MM`, `SENSOR_MM`, `STILL_SIZE`, `MAGNIFIER` (dict: `lensRadius`, `rimOuter`, `standoff`, `handleAngleDeg`, `restAim`).
  - Functions: `front_y(x, z)`, `crowd_positions() -> list[(x, y, z)]` (Blender space), `accent_flags(count) -> list[bool]`, `camera_position() -> (x, y, z)`, `vertical_fov_deg() -> float`, `to_web(p) -> [x, y, z]`, `help_focus_index(positions) -> int`, `layout_document(blender_version) -> dict`.
- The `layout_document` dict **is** the `layout.json` schema that the browser code consumes:
  ```json
  {"version":1,"generator":"...","blender":"5.2.2 LTS","tokenScale":0.4,
   "people":[[x,y,z],...],"accent":[0|1,...],"figureCenter":[x,y,z],
   "camera":{"position":[x,y,z],"target":[x,y,z],"vfovDeg":31.05,"aspect":1.2963},
   "magnifier":{"lensRadius":0.9,"rimOuter":1.06,"standoff":1.2,"handleAngleDeg":-52.0,"restAim":[0.95,1.5]}}
  ```
  All web coordinates are Y-up with +Z toward the viewer.

- [ ] **Step 1: Write the failing tests**

`tests/test_layout.py`:
```python
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "blender"))
import coalesce_layout as L  # noqa: E402


def test_crowd_size_within_budget():
    assert 150 <= len(L.crowd_positions()) <= 300


def test_people_stand_on_the_front_surface():
    for x, y, z in L.crowd_positions():
        assert y < 0, (x, y, z)
        assert abs(y - L.front_y(x, z + 0.14)) < 1e-3


def test_layout_document_is_deterministic_and_json_ready():
    a = L.layout_document("test")
    assert a == L.layout_document("test")
    json.dumps(a)


def test_accent_share_is_small_and_aligned():
    doc = L.layout_document()
    assert len(doc["accent"]) == len(doc["people"])
    assert 0.02 <= sum(doc["accent"]) / len(doc["accent"]) <= 0.14


def test_web_space_is_y_up_facing_the_camera():
    doc = L.layout_document()
    ys = [p[1] for p in doc["people"]]
    zs = [p[2] for p in doc["people"]]
    assert min(ys) >= 0 and max(ys) < 5.2
    assert min(zs) > 0
    cam = doc["camera"]
    assert cam["position"][2] > 10
    assert 25 < cam["vfovDeg"] < 40
    assert abs(cam["aspect"] - 1400 / 1080) < 1e-3


def test_help_focus_is_near_the_resting_aim():
    positions = L.crowd_positions()
    x, _, z = positions[L.help_focus_index(positions)]
    ax, ay = L.MAGNIFIER["restAim"]
    assert abs(x - ax) < 0.3 and abs(z + 0.14 - ay) < 0.3
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `.venv/Scripts/python -m pytest tests/test_layout.py -q`
Expected: ERROR, `ModuleNotFoundError: No module named 'coalesce_layout'`.

- [ ] **Step 3: Write the layout module**

`blender/coalesce_layout.py`:
```python
"""Where the small people stand, and where the camera looks from.

Pure Python (no bpy), shared by blender/build_coalesce.py and the tests.
Blender space: X right, Y depth (negative = toward the viewer), Z up.
Web space (layout.json, glTF): X right, Y up, Z toward the viewer; see to_web().
"""
import math
import random

TOKEN_SCALE = 0.40
GRID_DX = 0.265
GRID_DZ = 0.30
HEAD_Z, HEAD_R = 3.62, 1.2
SHOULDER_A, SHOULDER_B, SHOULDER_C = 2.45, 1.35, 2.35
ACCENT_RATE = 0.07
SEED = 7

CAMERA_TARGET = (0.35, 0.0, 2.45)
CAMERA_ELEVATION_DEG = 12.0
CAMERA_DISTANCE = 15.0
LENS_MM = 50.0
SENSOR_MM = 36.0
STILL_SIZE = (1400, 1080)

MAGNIFIER = {
    "lensRadius": 0.9,
    "rimOuter": 1.06,
    "standoff": 1.2,
    "handleAngleDeg": -52.0,
    "restAim": [0.95, 1.5],  # web x, y where the Help still (and the live lens) starts
}


def front_y(x, z):
    """Most-forward (most negative) Y of the head-and-shoulders volume at (x, z), or None outside it."""
    best = None
    q = HEAD_R ** 2 - x * x - (z - HEAD_Z) ** 2
    if q > 0:
        best = -math.sqrt(q)
    if z >= 0:
        q2 = 1 - (x / SHOULDER_A) ** 2 - (z / SHOULDER_C) ** 2
        if q2 > 0:
            y2 = -SHOULDER_B * math.sqrt(q2)
            best = y2 if best is None else min(best, y2)
    return best


def crowd_positions():
    """Base position of every person, packed on the figure's front surface, bottom row first."""
    positions = []
    for row in range(int(5.2 / GRID_DZ) + 1):
        z = row * GRID_DZ
        x = -3.0 + (GRID_DX / 2 if row % 2 else 0.0)
        while x <= 3.0 + 1e-9:
            y = front_y(x, z + 0.14)
            if y is not None and front_y(x, z + 0.27) is not None:
                positions.append((round(x, 4), round(y, 4), round(z, 4)))
            x += GRID_DX
    return positions


def accent_flags(count, rate=ACCENT_RATE, seed=SEED):
    rng = random.Random(seed)
    return [rng.random() < rate for _ in range(count)]


def camera_position():
    el = math.radians(CAMERA_ELEVATION_DEG)
    tx, ty, tz = CAMERA_TARGET
    return (tx, ty - CAMERA_DISTANCE * math.cos(el), tz + CAMERA_DISTANCE * math.sin(el))


def vertical_fov_deg():
    half_width = math.atan(SENSOR_MM / 2 / LENS_MM)
    aspect = STILL_SIZE[0] / STILL_SIZE[1]
    return math.degrees(2 * math.atan(math.tan(half_width) / aspect))


def to_web(point):
    x, y, z = point
    return [round(x, 4) + 0.0, round(z, 4) + 0.0, round(-y, 4) + 0.0]


def help_focus_index(positions):
    """Index of the person nearest the magnifier's resting aim (web x, y == Blender x, z)."""
    ax, ay = MAGNIFIER["restAim"]
    return min(range(len(positions)),
               key=lambda i: (positions[i][0] - ax) ** 2 + (positions[i][2] + 0.14 - ay) ** 2)


def layout_document(blender_version="unknown"):
    people = crowd_positions()
    zs = [p[2] for p in people]
    centre = (0.0, 0.0, round((min(zs) + max(zs)) / 2, 4))
    return {
        "version": 1,
        "generator": "blender/build_coalesce.py",
        "blender": blender_version,
        "tokenScale": TOKEN_SCALE,
        "people": [to_web(p) for p in people],
        "accent": [1 if flag else 0 for flag in accent_flags(len(people))],
        "figureCenter": to_web(centre),
        "camera": {
            "position": to_web(camera_position()),
            "target": to_web(CAMERA_TARGET),
            "vfovDeg": round(vertical_fov_deg(), 4),
            "aspect": round(STILL_SIZE[0] / STILL_SIZE[1], 4),
        },
        "magnifier": dict(MAGNIFIER),
    }
```

- [ ] **Step 4: Run the tests to see them pass**

Run: `.venv/Scripts/python -m pytest tests/test_layout.py -q`
Expected: `6 passed`.

- [ ] **Step 5: Commit**

```bash
git add blender/coalesce_layout.py tests/test_layout.py
git commit -q -F - <<'EOF'
feat: add the crowd layout shared by Blender and the website

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
EOF
```

---

### Task 4: Blender build: GLB, layout.json, self-check and stills

**Files:**
- Create: `blender/build_coalesce.py`, `tests/test_blender_build.py`
- Generated (committed):
  - `public/assets/coalesce.glb`, `public/assets/layout.json`
  - `public/assets/home-still.webp`, `public/assets/help-still.webp`
  - `blender/coalesce.blend`

**Interfaces:**
- Consumes `coalesce_layout` (Task 3).
- Produces `coalesce.glb` with mesh nodes `Person`, `MagnifierRim`, `MagnifierCollar` and `MagnifierHandle`:
  - All at the origin, Y-up.
  - The magnifier is in lens-local space: the lens faces +Z and the handle points down-right.
- Produces `layout.json` (the Task 3 schema) and the two 1400×1080 transparent WebP stills.
- The script prints `SELFCHECK {json}` and `BUILD OK` on success. With `--python-exit-code 1`, any failure exits non-zero.

- [ ] **Step 1: Write the failing tests**

`tests/test_blender_build.py`:
```python
import json
import struct
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "blender"))
import coalesce_layout as L  # noqa: E402

WEB_MESHES = {"Person", "MagnifierRim", "MagnifierCollar", "MagnifierHandle"}


def run_build(blender_exe, *extra, timeout=900):
    cmd = [blender_exe, "-b", "--factory-startup", "--python-exit-code", "1",
           "--python", str(ROOT / "blender" / "build_coalesce.py"), "--", *extra]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def glb_json(path):
    data = Path(path).read_bytes()
    magic, version, length = struct.unpack_from("<4sII", data, 0)
    assert magic == b"glTF" and version == 2 and length == len(data)
    chunk_length, chunk_type = struct.unpack_from("<I4s", data, 12)
    assert chunk_type == b"JSON"
    return json.loads(data[20:20 + chunk_length])


def webp_size(path):
    data = Path(path).read_bytes()
    assert data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    kind = data[12:16]
    if kind == b"VP8X":
        return 1 + int.from_bytes(data[24:27], "little"), 1 + int.from_bytes(data[27:30], "little")
    if kind == b"VP8 ":
        w, h = struct.unpack_from("<HH", data, 26)
        return w & 0x3FFF, h & 0x3FFF
    if kind == b"VP8L":
        bits = int.from_bytes(data[21:25], "little")
        return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
    raise AssertionError(f"unknown WebP chunk {kind!r}")


def output_of(result):
    return result.stdout[-4000:] + result.stderr[-4000:]


@pytest.mark.slow
def test_build_exports_pieces_and_layout(blender_exe, tmp_path):
    result = run_build(blender_exe, "--out", str(tmp_path), "--blend", str(tmp_path / "c.blend"))
    assert result.returncode == 0, output_of(result)
    assert "BUILD OK" in result.stdout
    line = next(l for l in result.stdout.splitlines() if l.startswith("SELFCHECK {"))
    triangles = json.loads(line.split(" ", 1)[1])
    assert WEB_MESHES <= set(triangles)
    assert triangles["Person"] <= 900
    glb = tmp_path / "coalesce.glb"
    assert glb.stat().st_size <= 150_000
    assert WEB_MESHES <= {node.get("name") for node in glb_json(glb)["nodes"]}
    layout = json.loads((tmp_path / "layout.json").read_text(encoding="utf-8"))
    assert layout["people"] == L.layout_document()["people"]
    assert layout["blender"].startswith("5.2")
    assert (tmp_path / "c.blend").is_file()


@pytest.mark.stills
def test_stills_render_at_size_within_budget(blender_exe, tmp_path):
    result = run_build(blender_exe, "--out", str(tmp_path), "--blend", str(tmp_path / "c.blend"),
                       "--stills", "--samples", "8", timeout=1800)
    assert result.returncode == 0, output_of(result)
    for name in ("home-still.webp", "help-still.webp"):
        assert webp_size(tmp_path / name) == (1400, 1080), name
        assert (tmp_path / name).stat().st_size <= 250_000, name
```

- [ ] **Step 2: Run the fast test to see it fail**

Run: `.venv/Scripts/python -m pytest tests/test_blender_build.py -q`
Expected: 1 failed. Blender exits non-zero because `build_coalesce.py` doesn't exist.

- [ ] **Step 3: Write the Blender build script**

`blender/build_coalesce.py`:
```python
"""Build the Coalesce 3D pieces in Blender (headless) and export them for the website.

  blender -b --factory-startup --python-exit-code 1 --python blender/build_coalesce.py -- [options]

  --out DIR      where coalesce.glb, layout.json and the stills go   (default: public/assets)
  --blend PATH   where to save the editable .blend                    (default: blender/coalesce.blend)
  --stills       also render home-still.webp and help-still.webp with Cycles (minutes)
  --samples N    Cycles samples for the Home still; Help uses twice as many (default: 32)
"""
import argparse
import json
import math
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import coalesce_layout as L  # noqa: E402

PALETTE = {"teal": "#1D5E5B", "terra": "#C4623A", "ink": "#1B2423", "paper": "#F4F0E8"}
WEB_MESHES = ("Person", "MagnifierRim", "MagnifierCollar", "MagnifierHandle")
PERSON_MAX_TRIS = 900


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(HERE.parent / "public" / "assets"))
    parser.add_argument("--blend", default=str(HERE / "coalesce.blend"))
    parser.add_argument("--stills", action="store_true")
    parser.add_argument("--samples", type=int, default=32)
    return parser.parse_args(argv)


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def lin(hexstr):
    h = hexstr.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c)


def node_tree(idblock):
    try:
        idblock.use_nodes = True  # always on in Blender 5, still needed on 4.x
    except Exception:
        pass
    return idblock.node_tree


def principled(name, hexcol, rough=0.4, metal=0.0, coat=0.0):
    mat = bpy.data.materials.new(name)
    bsdf = next(n for n in node_tree(mat).nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Base Color"].default_value = (*lin(hexcol), 1.0)
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metal
    bsdf.inputs["Coat Weight"].default_value = coat
    return mat


def glass(name):
    mat = bpy.data.materials.new(name)
    bsdf = next(n for n in node_tree(mat).nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Roughness"].default_value = 0.02
    bsdf.inputs["IOR"].default_value = 1.5
    bsdf.inputs["Transmission Weight"].default_value = 1.0
    return mat


def finish_mesh(name, bm, mat, smooth_angle=40):
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for poly in me.polygons:
        poly.use_smooth = True
    me.set_sharp_from_angle(angle=math.radians(smooth_angle))
    me.materials.append(mat)
    return me


def bevel_ring(bm, z, offset, segments):
    edges = [e for e in bm.edges if all(abs(v.co.z - z) < 1e-4 for v in e.verts)]
    verts = list({v for e in edges for v in e.verts})
    bmesh.ops.bevel(bm, geom=edges + verts, offset=offset, offset_type="OFFSET",
                    profile_type="SUPERELLIPSE", segments=segments, profile=0.5,
                    affect="EDGES", clamp_overlap=True)


def person_mesh(mat, name="Person"):
    """Rounded 'shoulders' body with a separate head (the classic person icon), about 600 triangles."""
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=20,
                          radius1=0.30, radius2=0.30, depth=0.34)
    bmesh.ops.translate(bm, verts=bm.verts[:], vec=(0, 0, 0.17))
    bevel_ring(bm, 0.34, 0.14, 5)
    bevel_ring(bm, 0.0, 0.025, 1)
    bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=10, radius=0.16,
                              matrix=Matrix.Translation((0, 0, 0.555)))
    return finish_mesh(name, bm, mat)


def ring_mesh(name, mat, r_in, r_out, half_depth, steps=96):
    """Flat ring in the XZ plane (it faces -Y, the camera); its thickness runs along Y."""
    bm = bmesh.new()
    loops = []
    for i in range(steps):
        t = 2 * math.pi * i / steps
        c, s = math.cos(t), math.sin(t)
        loops.append([bm.verts.new((r * c, y, r * s)) for r, y in
                      ((r_in, -half_depth), (r_out, -half_depth), (r_out, half_depth), (r_in, half_depth))])
    for a, b in zip(loops, loops[1:] + loops[:1]):
        for k in range(4):
            bm.faces.new((a[k], a[(k + 1) % 4], b[(k + 1) % 4], b[k]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return finish_mesh(name, bm, mat, smooth_angle=35)


def rod_mesh(name, mat, radius, length, start, angle_deg, segments=24):
    """Cylinder lying in the XZ plane along `angle_deg`, spanning [start, start + length] from the origin."""
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=segments,
                          radius1=radius, radius2=radius, depth=length)
    bmesh.ops.translate(bm, verts=bm.verts[:], vec=(0, 0, start + length / 2))
    a = math.radians(angle_deg)
    turn = Vector((0, 0, 1)).rotation_difference(Vector((math.cos(a), 0.0, math.sin(a))))
    bmesh.ops.transform(bm, matrix=turn.to_matrix().to_4x4(), verts=bm.verts[:])
    return finish_mesh(name, bm, mat, smooth_angle=35)


def magnifier_meshes(ink):
    m = L.MAGNIFIER
    return [
        ring_mesh("MagnifierRim", ink, m["lensRadius"], m["rimOuter"], 0.1),
        rod_mesh("MagnifierCollar", ink, 0.14, 0.34, m["rimOuter"], m["handleAngleDeg"]),
        rod_mesh("MagnifierHandle", ink, 0.105, 1.35, m["rimOuter"] + 0.34, m["handleAngleDeg"]),
    ]


def link(me, location=(0, 0, 0), rotation=None, scale=1.0):
    ob = bpy.data.objects.new(me.name, me)
    ob.location = location
    if rotation is not None:
        ob.rotation_mode = "QUATERNION"
        ob.rotation_quaternion = rotation
    ob.scale = (scale, scale, scale)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def build_web_pieces():
    teal = principled("Teal", PALETTE["teal"], rough=0.38, coat=0.3)
    ink = principled("Ink", PALETTE["ink"], rough=0.3, metal=0.5, coat=0.4)
    return [link(me) for me in [person_mesh(teal), *magnifier_meshes(ink)]]


def export_glb(objects, path):
    for ob in bpy.context.scene.objects:
        ob.select_set(ob in objects)
    bpy.context.view_layer.objects.active = objects[0]
    bpy.ops.export_scene.gltf(filepath=str(path), export_format="GLB", use_selection=True,
                              export_apply=True, export_yup=True, export_normals=True,
                              export_materials="EXPORT", export_cameras=False,
                              export_lights=False, export_animations=False)


def self_check(path):
    """Re-import the GLB into an empty scene and confirm the pieces the website needs are there."""
    reset()
    bpy.ops.import_scene.gltf(filepath=str(path))
    found = {}
    for ob in bpy.context.scene.objects:
        if ob.type == "MESH":
            ob.data.calc_loop_triangles()
            found[ob.name] = len(ob.data.loop_triangles)
    missing = [name for name in WEB_MESHES if name not in found]
    if missing:
        raise RuntimeError(f"self-check failed: {path.name} is missing {missing}")
    if found["Person"] > PERSON_MAX_TRIS:
        raise RuntimeError(f"self-check failed: Person has {found['Person']} triangles (max {PERSON_MAX_TRIS})")
    print("SELFCHECK " + json.dumps(found, sort_keys=True))


# ---------------------------------------------------------------- stills

def area_light(name, location, target, energy, size, color=(1, 1, 1)):
    light = bpy.data.lights.new(name, "AREA")
    light.energy, light.size, light.color = energy, size, color
    ob = bpy.data.objects.new(name, light)
    ob.location = location
    ob.rotation_euler = (Vector(target) - Vector(location)).to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.collection.objects.link(ob)


def lights():
    area_light("Key", (-6, -8, 8), (0, 0, 2.5), 1300, 6, (1.0, 0.97, 0.92))
    area_light("Fill", (7, -6, 3), (0, 0, 2.5), 350, 6)
    area_light("Rim", (0, 6, 7), (0, 0, 2.5), 700, 5)


def studio_world(seen_through=None):
    world = bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    nt = node_tree(world)
    bg = next(n for n in nt.nodes if n.type == "BACKGROUND")
    folder = Path(bpy.utils.system_resource("DATAFILES", path="studiolights/world") or ".")
    hdri = folder / "studio.exr"
    if hdri.is_file():
        env = nt.nodes.new("ShaderNodeTexEnvironment")
        env.image = bpy.data.images.load(str(hdri))
        nt.links.new(env.outputs["Color"], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = 0.5
    if seen_through:  # refracted rays see the page colour instead of the studio HDRI
        out = next(n for n in nt.nodes if n.type == "OUTPUT_WORLD")
        path = nt.nodes.new("ShaderNodeLightPath")
        flat = nt.nodes.new("ShaderNodeBackground")
        flat.inputs["Color"].default_value = (*lin(seen_through), 1.0)
        mix = nt.nodes.new("ShaderNodeMixShader")
        nt.links.new(path.outputs["Is Transmission Ray"], mix.inputs[0])
        nt.links.new(bg.outputs["Background"], mix.inputs[1])
        nt.links.new(flat.outputs["Background"], mix.inputs[2])
        nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])


def still_camera():
    cam = bpy.data.cameras.new("Camera")
    cam.lens, cam.sensor_width = L.LENS_MM, L.SENSOR_MM
    ob = bpy.data.objects.new("Camera", cam)
    ob.location = L.camera_position()
    ob.rotation_euler = (Vector(L.CAMERA_TARGET) - ob.location).to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.collection.objects.link(ob)
    bpy.context.scene.camera = ob
    return ob


def render(path, samples, transparent_glass=False):
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = samples
    scene.cycles.use_adaptive_sampling = True
    scene.cycles.use_denoising = True
    scene.cycles.max_bounces = 8
    scene.cycles.film_transparent_glass = transparent_glass
    scene.render.film_transparent = True
    scene.render.resolution_x, scene.render.resolution_y = L.STILL_SIZE
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "WEBP"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.quality = 82
    scene.render.filepath = str(path)
    scene.view_settings.view_transform = "AgX"
    for look in ("AgX - Medium High Contrast", "Medium High Contrast"):
        try:
            scene.view_settings.look = look
            break
        except TypeError:
            continue
    bpy.ops.render.render(write_still=True)
    print("RENDERED", path)


def crowd(teal, terra, is_terra):
    for i, position in enumerate(L.crowd_positions()):
        link(terra if is_terra(i) else teal, location=position, scale=L.TOKEN_SCALE)


def people_meshes():
    teal = person_mesh(principled("Teal", PALETTE["teal"], rough=0.35, coat=0.35), "PersonTeal")
    terra = person_mesh(principled("Terra", PALETTE["terra"], rough=0.32, coat=0.35), "PersonTerra")
    return teal, terra


def render_stills(out, samples):
    positions = L.crowd_positions()

    reset()
    teal, terra = people_meshes()
    accents = L.accent_flags(len(positions))
    crowd(teal, terra, lambda i: accents[i])
    studio_world()
    lights()
    still_camera()
    render(Path(out) / "home-still.webp", samples)

    reset()
    teal, terra = people_meshes()
    focus = L.help_focus_index(positions)
    crowd(teal, terra, lambda i: i == focus)
    studio_world(seen_through=PALETTE["paper"])
    lights()
    cam = still_camera()
    centre = Vector(positions[focus]) + Vector((0, 0, 0.14))
    lens_at = centre + (cam.location - centre).normalized() * L.MAGNIFIER["standoff"]
    facing = Vector((0, -1, 0)).rotation_difference((cam.location - lens_at).normalized())
    ink = principled("Ink", PALETTE["ink"], rough=0.3, metal=0.5, coat=0.4)
    for me in magnifier_meshes(ink):
        link(me, location=lens_at, rotation=facing)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=64, v_segments=32, radius=L.MAGNIFIER["lensRadius"] + 0.02)
    for v in bm.verts:
        v.co.y *= 0.18  # flatten along the viewing axis: a biconvex lens that magnifies about 2x
    lens = bpy.data.meshes.new("Lens")
    bm.to_mesh(lens)
    bm.free()
    for poly in lens.polygons:
        poly.use_smooth = True
    lens.materials.append(glass("Glass"))
    link(lens, location=lens_at, rotation=facing)
    render(Path(out) / "help-still.webp", samples * 2, transparent_glass=True)


def main():
    args = parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    reset()
    pieces = build_web_pieces()
    glb = out / "coalesce.glb"
    export_glb(pieces, glb)
    bpy.ops.wm.save_as_mainfile(filepath=str(Path(args.blend).resolve()))
    doc = L.layout_document(bpy.app.version_string)
    (out / "layout.json").write_text(json.dumps(doc, separators=(",", ":")), encoding="utf-8")
    self_check(glb)
    if args.stills:
        render_stills(out, args.samples)
    print("BUILD OK")


main()
```

- [ ] **Step 4: Run the fast test to see it pass**

Run: `.venv/Scripts/python -m pytest tests/test_blender_build.py -q`
Expected: `1 passed, 1 deselected` (about 30 s).

- [ ] **Step 5: Run the stills test**

Run: `.venv/Scripts/python -m pytest tests/test_blender_build.py -m stills -q`
Expected: `1 passed` (a few minutes at 8 samples).

- [ ] **Step 6: Build the real assets and look at them**

Run:
```bash
"/c/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b --factory-startup --python-exit-code 1 --python blender/build_coalesce.py -- --stills
```
Expected: `RENDERED …home-still.webp`, `RENDERED …help-still.webp`, `BUILD OK` (several minutes).

Then open both stills with the image viewer (Read tool) and compare them to the approved mockups (B page and B Help page). Check that:
- the figure reads as one head-and-shoulders made of small teal people;
- Home has a few terracotta people;
- Help has one terracotta person enlarged under the lens, and the handle is not cut off by the frame.

If the handle is clipped, lower `restAim` y in `coalesce_layout.MAGNIFIER` by 0.2 and rebuild.

- [ ] **Step 7: Commit**

```bash
git add blender/build_coalesce.py blender/coalesce.blend tests/test_blender_build.py public/assets
git commit -q -F - <<'EOF'
feat: Blender build for the crowd pieces, layout and still images

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
EOF
```

---
### Task 5: The settings file and link wiring

**Files:**
- Create: `public/site-config.js`, `public/js/config.js`, `tests/test_config.py`

**Interfaces:**
- Consumes the `js` fixture and `helpers.FULL` (Task 1).
- Produces these exports from `public/js/config.js`:
  - `MISSING_LABEL = 'Link coming soon'`, `DEFAULT_TEAM = 'the Coalesce team'`.
  - `safeUrl(value) -> string`
  - `resolveConfig(cfg) -> { teamName, version, releaseDate, urls: { docs, tutorial, serviceDesk, access, project, releases, download } }`
  - `applyConfig(root, resolved)`
  - `boot(win = window)`
- Page contract:
  - `[data-link="<url key>"]` gets an href. A missing link becomes `aria-disabled="true"` with class `is-missing`. If the element has a `[data-cta]` child, that child's text becomes "Link coming soon"; otherwise the element gets `title="Link coming soon"`.
  - `[data-text="teamName|version|releaseDate"]` gets that text.
  - `[data-requires="<key>"]` is hidden while that value is empty.

- [ ] **Step 1: Write the failing tests**

`tests/test_config.py`:
```python
import json

import pytest

from helpers import FULL

FIXTURE_HTML = """
<a id="docs" data-link="docs" href="#"><span data-cta>Read the docs</span></a>
<a id="dl" data-link="download" href="#"><span data-cta>Download Coalesce</span></a>
<a id="nav" data-link="access" href="#">Get access</a>
<span id="team" data-text="teamName">placeholder</span>
<p id="ver" data-requires="version">Version <span data-text="version"></span><span id="date" data-requires="releaseDate">, <span data-text="releaseDate"></span></span></p>
"""


def resolve(js, cfg):
    return js(f"const m = await import('/public/js/config.js'); return m.resolveConfig({json.dumps(cfg)});")


def apply(js, cfg):
    return js(f"""
        document.body.innerHTML = {json.dumps(FIXTURE_HTML)};
        const m = await import('/public/js/config.js');
        m.applyConfig(document, m.resolveConfig({json.dumps(cfg)}));
        const q = (s) => document.querySelector(s);
        return {{
          docsHref: q('#docs').getAttribute('href'), docsText: q('#docs').textContent.trim(),
          dlHref: q('#dl').getAttribute('href'), dlDisabled: q('#dl').getAttribute('aria-disabled'),
          dlText: q('#dl').textContent.trim(), dlMissing: q('#dl').classList.contains('is-missing'),
          navTitle: q('#nav').getAttribute('title'), navText: q('#nav').textContent.trim(),
          team: q('#team').textContent, verHidden: q('#ver').hidden, dateHidden: q('#date').hidden,
          verText: q('#ver').innerText.trim(),
        }};
    """)


def test_full_settings_derive_gitlab_urls(js):
    r = resolve(js, FULL)
    assert r["urls"]["project"] == "https://gitlab.example.com/ops/coalesce"
    assert r["urls"]["releases"] == "https://gitlab.example.com/ops/coalesce/-/releases"
    assert r["urls"]["download"] == (
        "https://gitlab.example.com/ops/coalesce/-/releases/permalink/latest/downloads/Coalesce.xlam")
    assert r["urls"]["serviceDesk"] == FULL["links"]["serviceDesk"]
    assert (r["teamName"], r["version"], r["releaseDate"]) == ("Manpower Systems", "2.4.0", "23 Sep 2026")


def test_release_page_is_the_default_download(js):
    cfg = {k: v for k, v in FULL.items() if k != "downloadLink"}
    assert resolve(js, cfg)["urls"]["download"] == (
        "https://gitlab.example.com/ops/coalesce/-/releases/permalink/latest")


def test_empty_settings_fall_back_quietly(js):
    r = resolve(js, {})
    assert all(value == "" for value in r["urls"].values())
    assert r["teamName"] == "the Coalesce team"


@pytest.mark.parametrize("bad", ["javascript:alert(1)", "www.example.com/docs", "   ", "ftp://x.example", 42, None])
def test_unsafe_or_malformed_links_are_dropped(js, bad):
    r = resolve(js, {"gitlabProjectUrl": bad, "links": {"docs": bad}})
    assert r["urls"]["docs"] == ""
    assert r["urls"]["download"] == "" and r["urls"]["releases"] == "" and r["urls"]["project"] == ""


def test_apply_fills_links_and_text(js):
    r = apply(js, {**FULL, "releaseDate": ""})
    assert r["docsHref"] == FULL["links"]["docs"] and r["docsText"] == "Read the docs"
    assert r["team"] == "Manpower Systems"
    assert r["verHidden"] is False and r["dateHidden"] is True
    assert r["verText"] == "Version 2.4.0"


def test_apply_marks_missing_links(js):
    r = apply(js, {})
    assert r["dlHref"] is None and r["dlDisabled"] == "true" and r["dlMissing"] is True
    assert r["dlText"] == "Link coming soon"
    assert r["navTitle"] == "Link coming soon" and r["navText"] == "Get access"
    assert r["team"] == "the Coalesce team"
    assert r["verHidden"] is True


def test_boot_reads_window_settings(js):
    href = js(f"""
        document.body.innerHTML = {json.dumps(FIXTURE_HTML)};
        window.COALESCE_SITE = {json.dumps(FULL)};
        const m = await import('/public/js/config.js');
        m.boot(window);
        return document.querySelector('#docs').getAttribute('href');
    """)
    assert href == FULL["links"]["docs"]
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `.venv/Scripts/python -m pytest tests/test_config.py -q`
Expected: every test fails with `Failed to fetch dynamically imported module …/public/js/config.js`.

- [ ] **Step 3: Write the settings file and config.js**

`public/site-config.js`:
```js
// Coalesce site settings: the only file you need to edit.
// Paste full links that start with https://. Leave a link empty ('') and the page shows "Link coming soon".
window.COALESCE_SITE = {
  teamName: '',                  // shown in the footer and on the Help page, e.g. 'the Manpower Systems team'
  gitlabProjectUrl: '',          // e.g. 'https://gitlab.example.com/ops/coalesce'
  xlamFileName: 'Coalesce.xlam',
  downloadLink: 'release-page',  // 'release-page' opens the newest release; 'direct' downloads the file (see README)
  version: '',                   // shown under the Download button, e.g. '2.4.0'
  releaseDate: '',               // e.g. '23 Sep 2026'
  links: {
    docs: '',                    // usage docs / SOP
    tutorial: '',                // the interactive tutorial
    serviceDesk: '',             // your Jira service desk portal
    access: '',                  // how to request access
  },
};
```

`public/js/config.js`:
```js
// Reads the owner's settings (window.COALESCE_SITE, from site-config.js) and wires them into the page:
//   [data-link="key"]      gets the resolved URL, or turns into "Link coming soon" when there isn't one
//   [data-text="key"]      gets the text value (teamName, version, releaseDate)
//   [data-requires="key"]  stays hidden while that value is empty

export const MISSING_LABEL = 'Link coming soon';
export const DEFAULT_TEAM = 'the Coalesce team';
const SAFE_URL = /^(https?:\/\/|mailto:|\/|\.\.?\/)/i;

const trimmed = (value) => (typeof value === 'string' ? value.trim() : '');

export function safeUrl(value) {
  const url = trimmed(value);
  return SAFE_URL.test(url) ? url : '';
}

export function resolveConfig(cfg = {}) {
  const links = cfg.links || {};
  const project = safeUrl(cfg.gitlabProjectUrl).replace(/\/+$/, '');
  const onGitLab = /^https?:\/\//i.test(project);
  const file = trimmed(cfg.xlamFileName) || 'Coalesce.xlam';
  const latest = `${project}/-/releases/permalink/latest`;
  let download = '';
  if (onGitLab) download = cfg.downloadLink === 'direct' ? `${latest}/downloads/${encodeURIComponent(file)}` : latest;
  return {
    teamName: trimmed(cfg.teamName) || DEFAULT_TEAM,
    version: trimmed(cfg.version),
    releaseDate: trimmed(cfg.releaseDate),
    urls: {
      docs: safeUrl(links.docs),
      tutorial: safeUrl(links.tutorial),
      serviceDesk: safeUrl(links.serviceDesk),
      access: safeUrl(links.access),
      project: onGitLab ? project : '',
      releases: onGitLab ? `${project}/-/releases` : '',
      download,
    },
  };
}

export function applyConfig(root, resolved) {
  for (const el of root.querySelectorAll('[data-link]')) {
    const url = resolved.urls[el.dataset.link] || '';
    if (url) {
      el.setAttribute('href', url);
      el.removeAttribute('aria-disabled');
      el.classList.remove('is-missing');
      continue;
    }
    el.removeAttribute('href');
    el.setAttribute('aria-disabled', 'true');
    el.classList.add('is-missing');
    const cta = el.querySelector('[data-cta]');
    if (cta) cta.textContent = MISSING_LABEL;
    else el.setAttribute('title', MISSING_LABEL);
  }
  for (const el of root.querySelectorAll('[data-text]')) {
    const value = resolved[el.dataset.text];
    if (typeof value === 'string' && value) el.textContent = value;
  }
  for (const el of root.querySelectorAll('[data-requires]')) {
    el.hidden = !resolved[el.dataset.requires];
  }
}

export function boot(win = window) {
  applyConfig(win.document, resolveConfig(win.COALESCE_SITE || {}));
}
```

- [ ] **Step 4: Run the tests to see them pass**

Run: `.venv/Scripts/python -m pytest tests/test_config.py -q`
Expected: `12 passed`.

- [ ] **Step 5: Commit**

```bash
git add public/site-config.js public/js/config.js tests/test_config.py
git commit -q -F - <<'EOF'
feat: settings file and safe link wiring

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
EOF
```

---

### Task 6: The Home and Help pages

**Files:**
- Create: `public/index.html`, `public/help/index.html`, `public/css/site.css`, `public/assets/favicon.svg`
- Create: `public/js/hero.js` (a stub that Task 10 replaces)
- Create: `tests/test_pages.py`

**Interfaces:**
- Consumes: `config.js` `boot()` (Task 5); the stills and fonts (Tasks 2 and 4).
- Produces the page hooks that `hero.js` (Task 10) relies on:
  - `.hero-figure` wraps `[data-hero]` (the stage: `role="img"`, holding `img.hero-still`) and `button[data-pause]` (starts `hidden`).
  - `.hero-stage.is-live` fades the still out.
  - Each page's inline module calls `mountHero(stage, { variant, assetsBase, watchdog, watchdogLimitMs })`. The query string `?nowatchdog` turns the watchdog off, and `?watchdogLimitMs=N` overrides its limit (both are test hooks).

- [ ] **Step 1: Write the failing tests**

`tests/test_pages.py`:
```python
import json

import pytest

from helpers import FULL, collect_errors

PAGES = {"home": "/public/index.html", "help": "/public/help/index.html"}


def open_page(make_page, base_url, name, **context_args):
    page = make_page(**context_args)
    errors = collect_errors(page)
    page.goto(base_url + PAGES[name])
    page.wait_for_load_state("networkidle")
    return page, errors


@pytest.mark.parametrize("name", PAGES)
def test_page_loads_cleanly_with_its_fonts(make_page, base_url, name):
    page, errors = open_page(make_page, base_url, name)
    statuses = page.evaluate("""async () => {
        await Promise.all([...document.fonts].map((f) => f.load().catch(() => null)));
        return [...document.fonts].map((f) => f.status);
    }""")
    assert len(statuses) == 3 and set(statuses) == {"loaded"}
    assert errors == []


@pytest.mark.parametrize("name", PAGES)
def test_empty_settings_show_link_coming_soon(make_page, base_url, name):
    page, _ = open_page(make_page, base_url, name)
    links = page.eval_on_selector_all(
        "[data-link]", "els => els.map((e) => [e.getAttribute('href'), e.getAttribute('aria-disabled')])")
    assert links and all(href is None and disabled == "true" for href, disabled in links)
    assert page.locator("[data-cta]", has_text="Link coming soon").count() >= 3


@pytest.mark.parametrize("name", PAGES)
def test_filled_settings_wire_every_link(make_page, base_url, name):
    page = make_page()
    page.route("**/site-config.js", lambda route: route.fulfill(
        content_type="text/javascript", body=f"window.COALESCE_SITE = {json.dumps(FULL)};"))
    page.goto(base_url + PAGES[name])
    page.wait_for_load_state("networkidle")
    hrefs = page.eval_on_selector_all("[data-link]", "els => els.map((e) => e.getAttribute('href'))")
    assert hrefs and all(h and h.startswith("https://") for h in hrefs), hrefs
    assert page.locator("footer [data-text=teamName]").inner_text() == "Manpower Systems"


@pytest.mark.parametrize("name", PAGES)
@pytest.mark.parametrize("width", [390, 1440])
def test_no_horizontal_scroll(make_page, base_url, name, width):
    page, _ = open_page(make_page, base_url, name, viewport={"width": width, "height": 844})
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")


@pytest.mark.parametrize("name", PAGES)
def test_accessibility_basics(make_page, base_url, name):
    page, _ = open_page(make_page, base_url, name)
    assert page.locator("a.skip-link").get_attribute("href") == "#main"
    assert page.locator("main#main").count() == 1
    assert page.locator("h1").count() == 1
    stage = page.locator("[data-hero]")
    assert stage.get_attribute("role") == "img" and len(stage.get_attribute("aria-label")) > 40
    assert page.evaluate("[...document.images].every((i) => i.hasAttribute('alt'))")


def test_help_nav_marks_the_current_page(make_page, base_url):
    page, _ = open_page(make_page, base_url, "help")
    assert page.locator(".site-nav a[aria-current=page]").inner_text() == "Help"
    assert page.locator("a.brand").get_attribute("href") == "../"


def test_home_install_steps_in_order(make_page, base_url):
    page, _ = open_page(make_page, base_url, "home")
    assert page.locator("#install .steps li h3").all_inner_texts() == ["Download", "Unblock it", "Add it to Excel"]
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `.venv/Scripts/python -m pytest tests/test_pages.py -q`
Expected: failures. The pages don't exist, so they return 404 and the locators find nothing.

- [ ] **Step 3: Write the stub hero and the favicon**

`public/js/hero.js`:
```js
// Placeholder until the live hero lands (Task 10): the pages keep their still image.
export async function mountHero(stage) {
  stage.dataset.heroState = 'still';
  stage.dataset.heroReason = 'not-built';
  return { state: 'still', reason: 'not-built' };
}
```

`public/assets/favicon.svg`:
```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 30 30"><circle cx="13" cy="9" r="5.5" fill="#1D5E5B"/><path d="M3 27a10 9.5 0 0 1 20 0z" fill="#1D5E5B"/><circle cx="26.5" cy="17" r="2.4" fill="#C4623A"/></svg>
```

- [ ] **Step 4: Write the stylesheet**

`public/css/site.css`:
```css
/* Coalesce site styles: direction B (paper and teal), from the design spec. */

@font-face {
  font-family: "Instrument Sans";
  src: url("../fonts/InstrumentSans.woff2") format("woff2");
  font-weight: 400 700;
  font-style: normal;
  font-display: swap;
}
@font-face {
  font-family: "Instrument Serif";
  src: url("../fonts/InstrumentSerif-Regular.woff2") format("woff2");
  font-weight: 400;
  font-style: normal;
  font-display: swap;
}
@font-face {
  font-family: "Instrument Serif";
  src: url("../fonts/InstrumentSerif-Italic.woff2") format("woff2");
  font-weight: 400;
  font-style: italic;
  font-display: swap;
}

:root {
  --paper: #F4F0E8;
  --ink: #1B2423;
  --muted: #55605E;
  --teal: #1D5E5B;
  --teal-deep: #164A48;
  --on-teal: #FFFFFF;
  --terra: #C4623A;
  --line: #E2DBCD;
  --card: #FFFFFF;
  --code: #EFE9DD;
  --serif: "Instrument Serif", Georgia, "Times New Roman", serif;
  --sans: "Instrument Sans", system-ui, -apple-system, "Segoe UI", sans-serif;
  --gutter: clamp(16px, 5vw, 80px);
  --max: 1280px;
  color-scheme: light;
}

*, *::before, *::after { box-sizing: border-box; }
[hidden] { display: none !important; }
html { background: var(--paper); }
body { margin: 0; background: var(--paper); color: var(--ink); font-family: var(--sans); font-size: 17px; line-height: 1.55; }
img { max-width: 100%; height: auto; }
a { color: var(--teal); }
a:hover { color: var(--teal-deep); }
:focus-visible { outline: 3px solid var(--terra); outline-offset: 3px; }

.skip-link { position: absolute; left: 12px; top: -64px; z-index: 30; padding: 10px 16px; border-radius: 8px; background: var(--ink); color: var(--paper); }
.skip-link:focus { top: 12px; color: var(--paper); }

/* Header */
.site-header { display: flex; flex-wrap: wrap; align-items: center; gap: 12px 40px; max-width: var(--max); min-height: 88px; margin: 0 auto; padding-inline: var(--gutter); }
.brand { display: flex; align-items: center; gap: 12px; color: var(--ink); text-decoration: none; }
.brand:hover { color: var(--ink); }
.brand-name { font-family: var(--serif); font-size: 32px; line-height: 1; }
.site-nav { display: flex; flex-wrap: wrap; gap: 4px 28px; flex: 1; }
.site-nav a { padding-block: 10px; color: var(--ink); text-decoration: none; }
.site-nav a:hover { color: var(--teal); text-decoration: underline; }
.site-nav a[aria-current="page"] { color: var(--teal); font-weight: 600; text-decoration: underline; text-decoration-thickness: 2px; text-underline-offset: 6px; }

/* Buttons */
.btn { display: inline-flex; align-items: center; justify-content: center; gap: 8px; min-height: 48px; padding: 0 24px; border-radius: 10px; font-size: 16px; font-weight: 600; text-decoration: none; }
.btn svg { width: 18px; height: 18px; flex: none; }
.btn-primary { background: var(--teal); color: var(--on-teal); }
.btn-primary:hover { background: var(--teal-deep); color: var(--on-teal); }
.btn-ghost { border: 1.5px solid var(--teal); color: var(--teal); }
.btn-ghost:hover { background: rgba(29, 94, 91, 0.06); color: var(--teal-deep); }

/* Links whose setting is still empty */
.is-missing { cursor: default; opacity: 0.65; }
.btn.is-missing { background: transparent; border: 1.5px dashed var(--line); color: var(--muted); }
.card.is-missing .card-cta { color: var(--muted); }

/* Hero */
.hero { max-width: var(--max); margin: 0 auto; padding-inline: var(--gutter); }
.hero-figure { position: relative; width: 100%; }
.hero-stage { position: relative; width: 100%; aspect-ratio: 1400 / 1080; }
.hero-stage > .hero-still,
.hero-stage > canvas { position: absolute; inset: 0; display: block; width: 100%; height: 100%; }
.hero-stage > .hero-still { transition: opacity 0.6s ease; }
.hero-stage.is-live > .hero-still { opacity: 0; }
.hero-stage > canvas { touch-action: pan-y; cursor: pointer; }
.hero-pause { position: absolute; right: 8px; bottom: 8px; min-height: 44px; padding: 0 16px; border: 1px solid var(--line); border-radius: 999px; background: rgba(255, 255, 255, 0.88); color: var(--ink); font: inherit; font-size: 14px; cursor: pointer; }
.hero-copy { display: flex; flex-direction: column; gap: 24px; }
h1 { margin: 0; font-family: var(--serif); font-weight: 400; font-size: clamp(48px, 7.5vw, 92px); line-height: 0.98; letter-spacing: -0.02em; text-wrap: balance; }
h1 em { color: var(--terra); }
.lede { max-width: 36em; margin: 0; font-size: clamp(17px, 1.6vw, 20px); color: var(--muted); }
.actions { display: flex; flex-wrap: wrap; gap: 14px; }
.release-line { margin: 0; font-size: 14px; color: var(--muted); }

.hero-home { display: flex; flex-direction: column; align-items: center; padding-bottom: 72px; text-align: center; }
.hero-home .hero-figure { width: min(760px, 100%); }
.hero-home .hero-copy { position: relative; align-items: center; margin-top: -40px; }
.hero-home .actions { justify-content: center; }

.hero-help { display: grid; grid-template-columns: minmax(0, 5fr) minmax(0, 7fr); align-items: center; gap: 24px 48px; padding-bottom: 56px; }
.eyebrow { margin: 0; font-size: 13px; font-weight: 600; letter-spacing: 0.16em; text-transform: uppercase; color: var(--teal); }

/* Sections */
.section { max-width: var(--max); margin: 0 auto; padding: 64px var(--gutter); border-top: 1px solid var(--line); }
.section-head { display: flex; flex-wrap: wrap; align-items: flex-end; justify-content: space-between; gap: 8px 24px; margin-bottom: 32px; }
h2 { margin: 0; font-family: var(--serif); font-weight: 400; font-size: clamp(34px, 4vw, 48px); line-height: 1.05; }
.section-head p { margin: 0; color: var(--muted); }

.cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); gap: 20px; }
.cards-3 { grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); }
.card { display: flex; flex-direction: column; gap: 12px; min-height: 220px; padding: 28px; border: 1px solid var(--line); border-radius: 14px; background: var(--card); color: var(--ink); text-decoration: none; }
.card:hover { border-color: var(--teal); color: var(--ink); }
.card .icon { width: 30px; height: 30px; color: var(--teal); }
.card-title { font-size: 20px; font-weight: 600; }
.card-text { flex: 1; font-size: 15px; color: var(--muted); }
.card-cta { display: inline-flex; align-items: center; gap: 6px; font-size: 15px; font-weight: 600; color: var(--teal); }
.card-cta svg { width: 16px; height: 16px; }

/* Install steps */
.steps { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 20px; margin: 0; padding: 0; list-style: none; counter-reset: step; }
.steps li { position: relative; padding: 24px 24px 24px 76px; border: 1px solid var(--line); border-radius: 14px; background: var(--card); counter-increment: step; }
.steps li::before { content: counter(step); position: absolute; left: 22px; top: 22px; display: grid; place-items: center; width: 38px; height: 38px; border-radius: 50%; background: var(--teal); color: var(--on-teal); font-family: var(--serif); font-size: 22px; }
.steps h3 { margin: 0 0 6px; font-size: 18px; }
.steps p { margin: 0; font-size: 15px; color: var(--muted); }
.note { margin: 20px 0 0; font-size: 15px; color: var(--muted); }
code { padding: 1px 6px; border-radius: 5px; background: var(--code); font-family: "Cascadia Mono", Consolas, ui-monospace, monospace; font-size: 0.92em; }

/* Footer */
.site-footer { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 12px 24px; max-width: var(--max); margin: 0 auto; padding: 28px var(--gutter) 40px; border-top: 1px solid var(--line); font-size: 14px; color: var(--muted); }
.site-footer nav { display: flex; flex-wrap: wrap; gap: 8px 24px; }
.site-footer a { color: var(--ink); }

@media (max-width: 860px) {
  .hero-help { grid-template-columns: 1fr; }
  .hero-help .hero-figure { order: -1; }
  .hero-home .hero-copy { margin-top: -16px; }
}
```

- [ ] **Step 5: Write the Home page**

`public/index.html`:
```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Coalesce</title>
  <meta name="description" content="Download and install Coalesce, the Excel add-in that pulls manpower data into one workbook, and find its docs, release notes and help.">
  <link rel="icon" href="assets/favicon.svg" type="image/svg+xml">
  <link rel="preload" href="fonts/InstrumentSerif-Regular.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="stylesheet" href="css/site.css">
  <script src="site-config.js"></script>
  <script type="importmap">
    { "imports": { "three": "./vendor/three/build/three.module.min.js", "three/addons/": "./vendor/three/examples/jsm/" } }
  </script>
</head>
<body>
  <a class="skip-link" href="#main">Skip to content</a>

  <header class="site-header">
    <a class="brand" href="./" aria-label="Coalesce home">
      <svg width="30" height="30" viewBox="0 0 30 30" aria-hidden="true"><circle cx="13" cy="9" r="5.5" fill="#1D5E5B"/><path d="M3 27a10 9.5 0 0 1 20 0z" fill="#1D5E5B"/><circle cx="26.5" cy="17" r="2.4" fill="#C4623A"/></svg>
      <span class="brand-name">Coalesce</span>
    </a>
    <nav class="site-nav" aria-label="Main">
      <a data-link="docs" href="#">Docs</a>
      <a data-link="releases" href="#">Releases</a>
      <a data-link="access" href="#">Get access</a>
      <a href="help/">Help</a>
    </nav>
    <a class="btn btn-primary" data-link="download" href="#">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3v12"/><path d="m7 10 5 5 5-5"/><path d="M5 21h14"/></svg>
      <span data-cta>Download Coalesce</span>
    </a>
  </header>

  <main id="main">
    <section class="hero hero-home" aria-labelledby="home-title">
      <div class="hero-figure">
        <div class="hero-stage" data-hero role="img" aria-label="A large head-and-shoulders figure made of many small people. People part when the pointer passes over them, newcomers arrive and others leave.">
          <img class="hero-still" src="assets/home-still.webp" width="1400" height="1080" alt="" fetchpriority="high">
        </div>
        <button class="hero-pause" type="button" data-pause aria-pressed="false" hidden>Pause motion</button>
      </div>
      <div class="hero-copy">
        <h1 id="home-title">Many people.<br><em>One</em> clear picture.</h1>
        <p class="lede">Coalesce pulls your manpower data into one Excel workbook, organized across tabs, and emails it up and down the chain to parent and subordinate organizations.</p>
        <div class="actions">
          <a class="btn btn-primary" data-link="download" href="#">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3v12"/><path d="m7 10 5 5 5-5"/><path d="M5 21h14"/></svg>
            <span data-cta>Download Coalesce</span>
          </a>
          <a class="btn btn-ghost" data-link="docs" href="#"><span data-cta>Read the docs</span></a>
        </div>
        <p class="release-line" data-requires="version" hidden>Version <span data-text="version"></span><span data-requires="releaseDate">, <span data-text="releaseDate"></span></span> · <a data-link="releases" href="#"><span data-cta>Release notes</span></a></p>
      </div>
    </section>

    <section class="section" id="install" aria-labelledby="install-title">
      <div class="section-head">
        <h2 id="install-title">Install in three steps</h2>
      </div>
      <ol class="steps">
        <li>
          <h3>Download</h3>
          <p>Get <a data-link="download" href="#">Coalesce.xlam</a> and save it in the folder Excel opens when you click <strong>Browse</strong> in step 3.</p>
        </li>
        <li>
          <h3>Unblock it</h3>
          <p>If Excel blocks its macros, right-click the file, choose <strong>Properties</strong>, tick <strong>Unblock</strong>, then click <strong>OK</strong>.</p>
        </li>
        <li>
          <h3>Add it to Excel</h3>
          <p>Go to <strong>File → Options → Add-ins</strong>. Next to <strong>Manage</strong>, pick <strong>Excel Add-ins</strong> and click <strong>Go…</strong>, then <strong>Browse…</strong>, choose <code>Coalesce.xlam</code> and click <strong>OK</strong>.</p>
        </li>
      </ol>
      <p class="note">Updating? Close Excel, download the new version and replace the old file.</p>
    </section>

    <section class="section" aria-labelledby="links-title">
      <div class="section-head">
        <h2 id="links-title">Project home</h2>
        <p>Docs, releases, access and help, all in one place.</p>
      </div>
      <div class="cards">
        <a class="card" data-link="docs" href="#">
          <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M2 5h7a3 3 0 0 1 3 3v12a2 2 0 0 0-2-2H2z"/><path d="M22 5h-7a3 3 0 0 0-3 3v12a2 2 0 0 1 2-2h8z"/></svg>
          <span class="card-title">Documentation</span>
          <span class="card-text">Usage docs and the SOP: how to use each screen, and the procedure behind every step.</span>
          <span class="card-cta" data-cta>Read the docs <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 12h14"/><path d="m12 5 7 7-7 7"/></svg></span>
        </a>
        <a class="card" data-link="releases" href="#">
          <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12.586 2.586A2 2 0 0 0 11.172 2H4a2 2 0 0 0-2 2v7.172a2 2 0 0 0 .586 1.414l8.704 8.704a2.426 2.426 0 0 0 3.42 0l6.58-6.58a2.426 2.426 0 0 0 0-3.42z"/><circle cx="7.5" cy="7.5" r="1"/></svg>
          <span class="card-title">Release notes</span>
          <span class="card-text">What changed in each version of Coalesce.</span>
          <span class="card-cta" data-cta>See releases <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 12h14"/><path d="m12 5 7 7-7 7"/></svg></span>
        </a>
        <a class="card" data-link="access" href="#">
          <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M2.586 17.414A2 2 0 0 0 2 18.828V21a1 1 0 0 0 1 1h3a1 1 0 0 0 1-1v-1a1 1 0 0 1 1-1h1a1 1 0 0 0 1-1v-1a1 1 0 0 1 1-1h.172a2 2 0 0 0 1.414-.586l.814-.814a6.5 6.5 0 1 0-4-4z"/><circle cx="16.5" cy="7.5" r="1"/></svg>
          <span class="card-title">Get access</span>
          <span class="card-text">Request access and find out which permissions you need.</span>
          <span class="card-cta" data-cta>Request access <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 12h14"/><path d="m12 5 7 7-7 7"/></svg></span>
        </a>
        <a class="card" href="help/">
          <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="4"/><path d="m4.93 4.93 4.24 4.24"/><path d="m14.83 9.17 4.24-4.24"/><path d="m14.83 14.83 4.24 4.24"/><path d="m9.17 14.83-4.24 4.24"/></svg>
          <span class="card-title">Help</span>
          <span class="card-text">The service desk, the interactive tutorial and the SOP.</span>
          <span class="card-cta">Get help <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 12h14"/><path d="m12 5 7 7-7 7"/></svg></span>
        </a>
      </div>
    </section>
  </main>

  <footer class="site-footer">
    <span>Coalesce · maintained by <span data-text="teamName">the Coalesce team</span></span>
    <nav aria-label="Footer">
      <a data-link="project" href="#">GitLab project</a>
      <a data-link="serviceDesk" href="#">Report an issue</a>
    </nav>
  </footer>

  <script type="module">
    import { boot } from './js/config.js';
    boot();
  </script>
  <script type="module">
    import { mountHero } from './js/hero.js';
    const query = new URLSearchParams(location.search);
    mountHero(document.querySelector('[data-hero]'), {
      variant: 'home',
      assetsBase: 'assets/',
      watchdog: !query.has('nowatchdog'),
      watchdogLimitMs: query.has('watchdogLimitMs') ? Number(query.get('watchdogLimitMs')) : 45,
    });
  </script>
</body>
</html>
```

- [ ] **Step 6: Write the Help page**

`public/help/index.html`:
```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Help · Coalesce</title>
  <meta name="description" content="Get help with Coalesce: open a service desk ticket, take the interactive tutorial, or read the usage docs and SOP.">
  <link rel="icon" href="../assets/favicon.svg" type="image/svg+xml">
  <link rel="preload" href="../fonts/InstrumentSerif-Regular.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="stylesheet" href="../css/site.css">
  <script src="../site-config.js"></script>
  <script type="importmap">
    { "imports": { "three": "../vendor/three/build/three.module.min.js", "three/addons/": "../vendor/three/examples/jsm/" } }
  </script>
</head>
<body>
  <a class="skip-link" href="#main">Skip to content</a>

  <header class="site-header">
    <a class="brand" href="../" aria-label="Coalesce home">
      <svg width="30" height="30" viewBox="0 0 30 30" aria-hidden="true"><circle cx="13" cy="9" r="5.5" fill="#1D5E5B"/><path d="M3 27a10 9.5 0 0 1 20 0z" fill="#1D5E5B"/><circle cx="26.5" cy="17" r="2.4" fill="#C4623A"/></svg>
      <span class="brand-name">Coalesce</span>
    </a>
    <nav class="site-nav" aria-label="Main">
      <a data-link="docs" href="#">Docs</a>
      <a data-link="releases" href="#">Releases</a>
      <a data-link="access" href="#">Get access</a>
      <a href="./" aria-current="page">Help</a>
    </nav>
    <a class="btn btn-primary" data-link="download" href="#">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3v12"/><path d="m7 10 5 5 5-5"/><path d="M5 21h14"/></svg>
      <span data-cta>Download Coalesce</span>
    </a>
  </header>

  <main id="main">
    <section class="hero hero-help" aria-labelledby="help-title">
      <div class="hero-copy">
        <p class="eyebrow">Help</p>
        <h1 id="help-title">Let's take a <em>closer</em> look.</h1>
        <p class="lede">Stuck on a step, or not sure what comes next? Learn it with the tutorial, look it up in the SOP, or open a service desk ticket.</p>
      </div>
      <div class="hero-figure">
        <div class="hero-stage" data-hero role="img" aria-label="The same figure made of many small people, with a magnifying glass that enlarges one of them. The glass follows the pointer.">
          <img class="hero-still" src="../assets/help-still.webp" width="1400" height="1080" alt="" fetchpriority="high">
        </div>
        <button class="hero-pause" type="button" data-pause aria-pressed="false" hidden>Pause motion</button>
      </div>
    </section>

    <section class="section" aria-labelledby="ways-title">
      <div class="section-head">
        <h2 id="ways-title">Get help</h2>
        <p>Not sure which? Start with the tutorial.</p>
      </div>
      <div class="cards cards-3">
        <a class="card" data-link="serviceDesk" href="#">
          <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M2 9a3 3 0 0 1 0 6v2a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-2a3 3 0 0 1 0-6V7a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2Z"/><path d="M13 5v2"/><path d="M13 17v2"/><path d="M13 11v2"/></svg>
          <span class="card-title">Service desk</span>
          <span class="card-text">Report a problem or request a change. Tickets go to <span data-text="teamName">the Coalesce team</span> in Jira.</span>
          <span class="card-cta" data-cta>Open a ticket <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 12h14"/><path d="m12 5 7 7-7 7"/></svg></span>
        </a>
        <a class="card" data-link="tutorial" href="#">
          <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"/><path d="M10 8l6 4-6 4z"/></svg>
          <span class="card-title">Interactive tutorial</span>
          <span class="card-text">A guided walkthrough of onboarding and offboarding someone in Coalesce.</span>
          <span class="card-cta" data-cta>Start the tutorial <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 12h14"/><path d="m12 5 7 7-7 7"/></svg></span>
        </a>
        <a class="card" data-link="docs" href="#">
          <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="8" y="2" width="8" height="4" rx="1"/><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><path d="M12 11h4"/><path d="M12 16h4"/><path d="M8 11h.01"/><path d="M8 16h.01"/></svg>
          <span class="card-title">Usage docs &amp; SOP</span>
          <span class="card-text">How to use each screen, and the standard operating procedure behind every step.</span>
          <span class="card-cta" data-cta>Read the SOP <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 12h14"/><path d="m12 5 7 7-7 7"/></svg></span>
        </a>
      </div>
    </section>
  </main>

  <footer class="site-footer">
    <span>Coalesce · maintained by <span data-text="teamName">the Coalesce team</span></span>
    <nav aria-label="Footer">
      <a data-link="project" href="#">GitLab project</a>
      <a data-link="serviceDesk" href="#">Report an issue</a>
    </nav>
  </footer>

  <script type="module">
    import { boot } from '../js/config.js';
    boot();
  </script>
  <script type="module">
    import { mountHero } from '../js/hero.js';
    const query = new URLSearchParams(location.search);
    mountHero(document.querySelector('[data-hero]'), {
      variant: 'help',
      assetsBase: '../assets/',
      watchdog: !query.has('nowatchdog'),
      watchdogLimitMs: query.has('watchdogLimitMs') ? Number(query.get('watchdogLimitMs')) : 45,
    });
  </script>
</body>
</html>
```

- [ ] **Step 7: Run the tests to see them pass**

Run: `.venv/Scripts/python -m pytest tests/test_pages.py -q`
Expected: `14 passed`.

- [ ] **Step 8: Commit**

```bash
git add public/index.html public/help public/css public/assets/favicon.svg public/js/hero.js tests/test_pages.py
git commit -q -F - <<'EOF'
feat: Home and Help pages with the still-image hero

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
EOF
```

---
### Task 7: Live or still? (eligibility and the frame watchdog)

**Files:**
- Create: `public/js/eligibility.js`, `tests/test_eligibility.py`

**Interfaces:**
- Produces:
  - `readEnvironment(win = window) -> { webgl, reducedMotion, canHover, saveData }` (all booleans).
  - `decideMode(env) -> { live: boolean, reason: 'ok'|'no-webgl'|'reduced-motion'|'no-hover'|'save-data' }`. Reasons are checked in that order, so the first failing check wins.
  - `class FrameWatchdog({ windowMs = 2000, limitMs = 45, minFrames = 3 })` with `add(frameMs) -> 'pending'|'ok'|'too-slow'`. The verdict comes from the median frame time once `windowMs` of frames has accumulated, and it never changes afterwards.

- [ ] **Step 1: Write the failing tests**

`tests/test_eligibility.py`:
```python
import json

import pytest

OK_ENV = {"webgl": True, "reducedMotion": False, "canHover": True, "saveData": False}


def decide(js, env):
    return js(f"const m = await import('/public/js/eligibility.js'); return m.decideMode({json.dumps(env)});")


def watchdog(js, frames, **options):
    return js(f"""
        const m = await import('/public/js/eligibility.js');
        const dog = new m.FrameWatchdog({json.dumps(options)});
        return {json.dumps(frames)}.map((f) => dog.add(f));
    """)


@pytest.mark.parametrize("override, reason", [
    ({}, "ok"),
    ({"webgl": False}, "no-webgl"),
    ({"reducedMotion": True}, "reduced-motion"),
    ({"canHover": False}, "no-hover"),
    ({"saveData": True}, "save-data"),
    ({"webgl": False, "reducedMotion": True}, "no-webgl"),
])
def test_decide_mode(js, override, reason):
    result = decide(js, {**OK_ENV, **override})
    assert result == {"live": reason == "ok", "reason": reason}


def test_watchdog_passes_smooth_animation(js):
    verdicts = watchdog(js, [16.7] * 130)
    assert verdicts[0] == "pending" and verdicts.index("ok") == 119


def test_watchdog_fails_slow_animation(js):
    verdicts = watchdog(js, [60] * 40)
    assert verdicts.index("too-slow") == 33 and verdicts[-1] == "too-slow"


def test_watchdog_ignores_one_long_hitch(js):
    assert watchdog(js, [900] + [16] * 80)[-1] == "ok"


def test_watchdog_verdict_is_final(js):
    assert watchdog(js, [60] * 40 + [5] * 200)[-1] == "too-slow"


def test_read_environment_in_desktop_chromium(js):
    env = js("const m = await import('/public/js/eligibility.js'); return m.readEnvironment(window);")
    assert env == OK_ENV
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `.venv/Scripts/python -m pytest tests/test_eligibility.py -q`
Expected: 11 failed (module not found).

- [ ] **Step 3: Write eligibility.js**

`public/js/eligibility.js`:
```js
// Decides whether the live 3D hero may run on this device, and watches its frame times once it does.

export function readEnvironment(win = window) {
  const media = (query) => typeof win.matchMedia === 'function' && win.matchMedia(query).matches;
  let webgl = false;
  try {
    const canvas = win.document.createElement('canvas');
    const gl = canvas.getContext('webgl2') || canvas.getContext('webgl');
    webgl = Boolean(gl);
    const lose = gl && gl.getExtension('WEBGL_lose_context');
    if (lose) lose.loseContext();
  } catch (err) {
    webgl = false;
  }
  const connection = win.navigator && win.navigator.connection;
  return {
    webgl,
    reducedMotion: media('(prefers-reduced-motion: reduce)'),
    canHover: media('(hover: hover) and (pointer: fine)'),
    saveData: Boolean(connection && connection.saveData),
  };
}

export function decideMode(env) {
  if (!env.webgl) return { live: false, reason: 'no-webgl' };
  if (env.reducedMotion) return { live: false, reason: 'reduced-motion' };
  if (!env.canHover) return { live: false, reason: 'no-hover' };
  if (env.saveData) return { live: false, reason: 'save-data' };
  return { live: true, reason: 'ok' };
}

export class FrameWatchdog {
  constructor({ windowMs = 2000, limitMs = 45, minFrames = 3 } = {}) {
    this.windowMs = windowMs;
    this.limitMs = limitMs;
    this.minFrames = minFrames;
    this.samples = [];
    this.elapsed = 0;
    this.verdict = 'pending';
  }

  add(frameMs) {
    if (this.verdict !== 'pending') return this.verdict;
    this.samples.push(frameMs);
    this.elapsed += frameMs;
    if (this.elapsed >= this.windowMs && this.samples.length >= this.minFrames) {
      const sorted = [...this.samples].sort((a, b) => a - b);
      const median = sorted[Math.floor(sorted.length / 2)];
      this.verdict = median > this.limitMs ? 'too-slow' : 'ok';
    }
    return this.verdict;
  }
}
```

- [ ] **Step 4: Run the tests to see them pass**

Run: `.venv/Scripts/python -m pytest tests/test_eligibility.py -q`
Expected: `11 passed`.

- [ ] **Step 5: Commit**

```bash
git add public/js/eligibility.js tests/test_eligibility.py
git commit -q -F - <<'EOF'
feat: decide live vs still, with a frame-time watchdog

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
EOF
```

---

### Task 8: The crowd simulation (pure motion)

**Files:**
- Create: `public/js/motion.js`, `tests/test_motion.py`

**Interfaces:**
- Consumes a layout with the Task 3 schema (`people`, `accent`, `figureCenter`).
- Produces these exports:
  - `STEP` (1/120), `MAX_DT` (0.05), `HOVER`
  - `hexToLinear(hex) -> [r, g, b]`, `COLORS` (`teal`, `terra`, `paper`, all linear RGB)
  - `mulberry32(seed) -> () => number`
  - `ease`
  - `pathPoint(path, now, out) -> u`
  - `hoverOffset(home, ptr, amount, out, opts = HOVER) -> out`
- Produces `class CrowdSim(layout, { variant = 'home' | 'help', seed = 7 })`:
  - Fields:
    - `tokens`: an array of `{ home, mode, path, p, v, s, sT, col, colT, colRate, rx, rz, assimAt, busyUntil }`, where `mode` is one of `'home'|'intro'|'burst'|'leave'|'arrive'|'spare'`.
    - `clock`, `turnovers`, `hover` (`{ enabled, ptr, amount }`), `pointer` (`{ inside, target }`), `focusIndex`, `center`.
  - Methods:
    - `setPointer(point | null, inside)`
    - `intro()`
    - `burst(origin)`
    - `turnover() -> boolean`
    - `setFocus(index)`
    - `nearest(x, y) -> index | -1`
    - `advance(dt)` (seconds, clamped to [0, 0.05])
  - Home: 3 spare tokens, accents on, hover parting on, turnovers on. Help: no spares, all teal, hover off, turnovers off.
- Produces `class MagnifierSim(sim, restAim, { seed = 11 })`:
  - Fields: `pos: [x, y]`, `target`, `bounds`.
  - Methods: `advance(dt)` (follows `sim.pointer` while it's inside, drifts between people every 3 s otherwise, and keeps `sim.focusIndex` on the person nearest the lens); `aimPoint() -> [x, y, z]`.
  - Call `advance` after `sim.advance`.

- [ ] **Step 1: Write the failing tests**

`tests/test_motion.py`:
```python
import json

LAYOUT = {
    "people": [[x * 0.5 - 1.0, y * 0.5, 1.0] for y in range(5) for x in range(5)],
    "accent": [1 if i % 10 == 0 else 0 for i in range(25)],
    "figureCenter": [0.0, 1.0, 0.0],
}
PRELUDE = (
    "const m = await import('/public/js/motion.js');"
    f"const layout = {json.dumps(LAYOUT)};"
    "const settle = (sim, seconds, mag) => { for (let i = 0; i < Math.round(seconds * 60); i++)"
    " { sim.advance(1 / 60); if (mag) mag.advance(1 / 60); } };"
    "const far = (t) => Math.hypot(t.p[0] - t.home[0], t.p[1] - t.home[1], t.p[2] - t.home[2]);"
)


def run(js, body):
    return js(PRELUDE + body)


def test_hex_to_linear_matches_srgb(js):
    white, black, teal = run(js, "return [m.hexToLinear('#FFFFFF'), m.hexToLinear('#000000'), m.COLORS.teal];")
    assert white == [1, 1, 1] and black == [0, 0, 0]
    assert all(abs(a - b) < 5e-4 for a, b in zip(teal, [0.0123, 0.1119, 0.1046]))


def test_path_point_hits_endpoints_and_bulges(js):
    start, middle, end, later = run(js, """
        const path = { from: [0, 0, 0], to: [2, 0, 0], t0: 1, dur: 2, ease: 'inout', arc: [0, 1, 0] };
        const out = [0, 0, 0];
        const at = (t) => { m.pathPoint(path, t, out); return out.slice(); };
        return [at(0), at(2), at(3), at(9)];
    """)
    assert start == [0, 0, 0]
    assert all(abs(a - b) < 1e-9 for a, b in zip(middle, [1, 1, 0]))
    assert all(abs(a - b) < 1e-9 for a, b in zip(end, [2, 0, 0])) and later == end


def test_hover_offset_pushes_nearby_people_only(js):
    r = run(js, """
        const out = [0, 0, 0];
        return {
          near: m.hoverOffset([0.3, 0, 0], [0, 0, 0], 1, out).slice(),
          farAway: m.hoverOffset([2, 0, 0], [0, 0, 0], 1, out).slice(),
          off: m.hoverOffset([0.3, 0, 0], [0, 0, 0], 0, out).slice(),
        };
    """)
    assert r["near"][0] > 0.2 and abs(r["near"][1]) < 1e-9 and r["near"][2] > 0.2
    assert r["farAway"] == [0, 0, 0] and r["off"] == [0, 0, 0]


def test_spring_brings_a_displaced_person_home(js):
    assert run(js, """
        const sim = new m.CrowdSim(layout); sim.turnovers = false;
        const t = sim.tokens[12]; t.p[0] += 1;
        settle(sim, 3);
        return far(t);
    """) < 0.01


def test_intro_hides_everyone_then_assembles_the_figure(js):
    r = run(js, """
        const sim = new m.CrowdSim(layout); sim.turnovers = false;
        sim.intro();
        const before = sim.tokens.filter((t) => t.home).map((t) => [t.mode, t.s]);
        settle(sim, 6);
        const people = sim.tokens.filter((t) => t.home);
        return { before, modes: [...new Set(people.map((t) => t.mode))],
                 minScale: Math.min(...people.map((t) => t.s)), worst: Math.max(...people.map(far)) };
    """)
    assert all(mode == "intro" and s == 0 for mode, s in r["before"])
    assert r["modes"] == ["home"] and r["minScale"] > 0.99 and r["worst"] < 0.02


def test_turnover_swaps_one_person_and_keeps_the_count(js):
    r = run(js, """
        const sim = new m.CrowdSim(layout); sim.turnovers = false; sim.clock = 10;
        const ok = sim.turnover();
        const leaver = sim.tokens.find((t) => t.mode === 'leave');
        const arriver = sim.tokens.find((t) => t.mode === 'arrive');
        const slot = arriver.path.to.slice();
        settle(sim, 14);
        return {
          ok, leaverMode: leaver.mode, leaverScale: leaver.s,
          arriverMode: arriver.mode, arriverHome: arriver.home, slot,
          colorGap: Math.max(...arriver.col.map((c, i) => Math.abs(c - m.COLORS.teal[i]))),
          atHome: sim.tokens.filter((t) => t.mode === 'home').length,
        };
    """)
    assert r["ok"] is True
    assert r["leaverMode"] == "spare" and r["leaverScale"] < 0.01
    assert r["arriverMode"] == "home" and r["arriverHome"] == r["slot"]
    assert r["colorGap"] < 0.01 and r["atHome"] == 25


def test_burst_scatters_everyone_and_the_figure_reforms(js):
    r = run(js, """
        const sim = new m.CrowdSim(layout); sim.turnovers = false;
        sim.burst([0, 1, 0]);
        const bursting = sim.tokens.filter((t) => t.mode === 'burst').length;
        settle(sim, 0.7);
        const spread = Math.max(...sim.tokens.filter((t) => t.home).map(far));
        settle(sim, 5);
        const people = sim.tokens.filter((t) => t.home);
        return { bursting, spread, modes: [...new Set(people.map((t) => t.mode))], worst: Math.max(...people.map(far)) };
    """)
    assert r["bursting"] == 25 and r["spread"] > 1.0
    assert r["modes"] == ["home"] and r["worst"] < 0.02


def test_help_variant_has_no_accents_spares_or_turnovers(js):
    r = run(js, """
        const sim = new m.CrowdSim(layout, { variant: 'help' });
        const allTeal = sim.tokens.every((t) => t.col.every((c, i) => c === m.COLORS.teal[i]));
        settle(sim, 10);
        return { count: sim.tokens.length, allTeal, turnovers: sim.turnovers, hover: sim.hover.enabled,
                 modes: [...new Set(sim.tokens.map((t) => t.mode))] };
    """)
    assert r == {"count": 25, "allTeal": True, "turnovers": False, "hover": False, "modes": ["home"]}


def test_advance_caps_large_time_steps(js):
    r = run(js, """
        const sim = new m.CrowdSim(layout);
        sim.intro();
        sim.advance(5);
        return { clock: sim.clock, modes: [...new Set(sim.tokens.filter((t) => t.home).map((t) => t.mode))] };
    """)
    assert abs(r["clock"] - 0.05) < 1e-9 and r["modes"] == ["intro"]


def test_home_pointer_parts_nearby_people_then_they_return(js):
    r = run(js, """
        const sim = new m.CrowdSim(layout); sim.turnovers = false;
        sim.setPointer([0, 1, 1], true);
        settle(sim, 1);
        const near = far(sim.tokens[13]);
        const corner = far(sim.tokens[0]);
        sim.setPointer(null, false);
        settle(sim, 3);
        return { near, corner, worst: Math.max(...sim.tokens.filter((t) => t.home).map(far)) };
    """)
    assert r["near"] > 0.3 and r["corner"] < 0.05 and r["worst"] < 0.02


def test_magnifier_follows_the_pointer_and_highlights_one_person(js):
    r = run(js, """
        const sim = new m.CrowdSim(layout, { variant: 'help' });
        const mag = new m.MagnifierSim(sim, [0, 1]);
        sim.setPointer([0.5, 1.5, 1], true);
        settle(sim, 1, mag);
        const first = { pos: mag.pos.slice(), focus: sim.focusIndex, expected: sim.nearest(mag.pos[0], mag.pos[1]) };
        sim.setPointer([-1, 0.2, 1], true);
        settle(sim, 1, mag);
        return { first, second: sim.focusIndex,
                 terra: sim.tokens.filter((t) => t.colT[0] > t.colT[1]).length,
                 previous: sim.tokens[first.focus].colT };
    """)
    assert abs(r["first"]["pos"][0] - 0.5) < 0.02 and abs(r["first"]["pos"][1] - 1.5) < 0.02
    assert r["first"]["focus"] == r["first"]["expected"] >= 0
    assert r["second"] != r["first"]["focus"] and r["terra"] == 1
    assert r["previous"][0] < r["previous"][1]


def test_magnifier_drifts_between_people_when_nobody_points(js):
    r = run(js, """
        const sim = new m.CrowdSim(layout, { variant: 'help' });
        const mag = new m.MagnifierSim(sim, [3, 3]);
        settle(sim, 8, mag);
        return { moved: Math.hypot(mag.pos[0] - 3, mag.pos[1] - 3), focus: sim.focusIndex };
    """)
    assert r["moved"] > 0.5 and r["focus"] >= 0
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `.venv/Scripts/python -m pytest tests/test_motion.py -q`
Expected: 12 failed (module not found).

- [ ] **Step 3: Write motion.js**

`public/js/motion.js`:
```js
// Crowd motion for the Coalesce hero: pure data and maths, no Three.js.
// Coordinates are layout.json's web space: x right, y up, z toward the viewer.

export const STEP = 1 / 120;
export const MAX_DT = 0.05;
export const HOVER = { radius: 1.2, push: 0.8, lift: 0.9 };
const TOKEN_MIDDLE = 0.14; // height of a person's middle above their base at tokenScale 0.4

export function hexToLinear(hex) {
  const h = hex.replace('#', '');
  return [0, 2, 4].map((i) => {
    const c = parseInt(h.slice(i, i + 2), 16) / 255;
    return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  });
}

export const COLORS = {
  teal: hexToLinear('#1D5E5B'),
  terra: hexToLinear('#C4623A'),
  paper: hexToLinear('#F4F0E8'),
};

export function mulberry32(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export const ease = {
  out: (u) => 1 - (1 - u) ** 3,
  inout: (u) => (u < 0.5 ? 4 * u * u * u : 1 - (-2 * u + 2) ** 3 / 2),
};

const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));

export function pathPoint(path, now, out) {
  const u = clamp((now - path.t0) / path.dur, 0, 1);
  const e = ease[path.ease](u);
  const bulge = Math.sin(Math.PI * e);
  for (let i = 0; i < 3; i++) {
    out[i] = path.from[i] + (path.to[i] - path.from[i]) * e + (path.arc ? path.arc[i] * bulge : 0);
  }
  return u;
}

export function hoverOffset(home, ptr, amount, out, opts = HOVER) {
  out[0] = 0;
  out[1] = 0;
  out[2] = 0;
  if (amount < 0.001) return out;
  const dx = home[0] - ptr[0];
  const dy = home[1] - ptr[1];
  const d = Math.hypot(dx, dy);
  if (d >= opts.radius) return out;
  let f = 1 - d / opts.radius;
  f = f * f * (3 - 2 * f) * amount;
  const inv = d > 1e-4 ? 1 / d : 0;
  out[0] = dx * inv * opts.push * f;
  out[1] = dy * inv * opts.push * f;
  out[2] = opts.lift * f;
  return out;
}

function makeToken(home, color, mode) {
  const spare = mode === 'spare';
  return {
    home, mode, path: null,
    p: home ? home.slice() : [0, -50, 0], v: [0, 0, 0],
    s: spare ? 0 : 1, sT: spare ? 0 : 1,
    col: color.slice(), colT: color.slice(), colRate: 0.9,
    rx: 0, rz: 0, assimAt: 0, busyUntil: 0,
  };
}

function randArc(rand, size) {
  return [(rand() - 0.5) * size, (rand() - 0.5) * size, rand() * size];
}

function updateTokens(tokens, now, dt) {
  for (const t of tokens) {
    const path = t.path;
    if (path) {
      const u = clamp((now - path.t0) / path.dur, 0, 1);
      if (path.hideUntilStart) t.sT = now < path.t0 ? 0 : 1;
      if (t.mode === 'leave') t.sT = 1 - u;
      if (u >= 1) {
        if (path.next) {
          t.path = { ...path.next, from: t.p.slice(), t0: now };
        } else {
          t.path = null;
          t.mode = path.endMode;
          if (path.onDone) path.onDone(t, now);
        }
      }
    }
    if (t.assimAt && now >= t.assimAt) {
      t.colT = COLORS.teal.slice();
      t.assimAt = 0;
    }
    t.s += (t.sT - t.s) * Math.min(1, dt * 5);
    const rate = Math.min(1, dt * (t.mode === 'leave' ? 1.6 : t.colRate));
    for (let i = 0; i < 3; i++) t.col[i] += (t.colT[i] - t.col[i]) * rate;
  }
}

const target = [0, 0, 0];
const offset = [0, 0, 0];

function stepPhysics(tokens, now, h, hover) {
  for (const t of tokens) {
    let k = 38;
    let zeta = 0.5;
    if (t.path) {
      pathPoint(t.path, now, target);
      k = 70;
      zeta = 0.8;
    } else if (t.mode === 'home') {
      if (hover.enabled) hoverOffset(t.home, hover.ptr, hover.amount, offset);
      else offset.fill(0);
      for (let i = 0; i < 3; i++) target[i] = t.home[i] + offset[i];
    } else {
      for (let i = 0; i < 3; i++) target[i] = t.p[i];
    }
    const c = 2 * Math.sqrt(k) * zeta;
    for (let i = 0; i < 3; i++) {
      t.v[i] += (k * (target[i] - t.p[i]) - c * t.v[i]) * h;
      t.p[i] += t.v[i] * h;
    }
  }
}

function updateTilt(t, dt) {
  let rz = clamp(-t.v[0] * 0.12, -0.7, 0.7);
  let rx = clamp(t.v[2] * 0.1 - t.v[1] * 0.05, -0.7, 0.7);
  if (t.mode === 'home' && t.home) {
    rz += clamp(-(t.p[0] - t.home[0]) * 0.45, -0.6, 0.6);
    rx += clamp((t.p[2] - t.home[2]) * 0.35, -0.6, 0.6);
  }
  const a = Math.min(1, dt * 10);
  t.rz += (rz - t.rz) * a;
  t.rx += (rx - t.rx) * a;
}

export class CrowdSim {
  constructor(layout, { variant = 'home', seed = 7 } = {}) {
    this.variant = variant;
    this.rand = mulberry32(seed);
    this.center = layout.figureCenter.slice();
    const accents = variant === 'home';
    this.tokens = layout.people.map((home, i) =>
      makeToken(home.slice(), accents && layout.accent[i] ? COLORS.terra : COLORS.teal, 'home'));
    if (variant === 'home') {
      for (let k = 0; k < 3; k++) this.tokens.push(makeToken(null, COLORS.teal, 'spare'));
    }
    this.turnovers = variant === 'home';
    this.hover = { enabled: variant === 'home', ptr: [0, 99, 0], amount: 0 };
    this.pointer = { inside: false, target: [0, 99, 0] };
    this.clock = 0;
    this.acc = 0;
    this.quietUntil = 0;
    this.nextTurn = 0;
    this.focusIndex = -1;
  }

  setPointer(point, inside) {
    const entering = inside && !this.pointer.inside;
    this.pointer.inside = Boolean(inside && point);
    if (point) {
      this.pointer.target = point.slice();
      if (entering) this.hover.ptr = point.slice();
    }
  }

  // Everyone flies in from a loose crowd around the figure (page load).
  intro() {
    const [cx, cy, cz] = this.center;
    for (const t of this.tokens) {
      if (!t.home) continue;
      const angle = this.rand() * Math.PI * 2;
      const r = 6 + this.rand() * 4;
      const from = [cx + Math.cos(angle) * r, cy + Math.sin(angle) * r * 0.7, cz - 2 + this.rand() * 5];
      t.p = from.slice();
      t.v = [0, 0, 0];
      t.s = 0;
      t.sT = 0;
      t.mode = 'intro';
      t.path = {
        from, to: t.home.slice(), t0: this.clock + 0.1 + this.rand() ** 0.7 * 1.3, dur: 1.7 + this.rand() * 0.8,
        ease: 'out', arc: randArc(this.rand, 1.2), hideUntilStart: true, endMode: 'home',
      };
    }
    this.quietUntil = this.clock + 3.6;
  }

  // Click: people burst outward from the click point, then re-form.
  burst(origin) {
    for (const t of this.tokens) {
      if (t.mode !== 'home') continue;
      let dx = t.home[0] - origin[0];
      let dy = t.home[1] - origin[1];
      let d = Math.hypot(dx, dy);
      if (d < 1e-3) {
        dx = this.rand() - 0.5;
        dy = this.rand() - 0.5;
        d = Math.hypot(dx, dy) || 1;
      }
      const k = (1.6 + this.rand() * 2.4) / d;
      const out = [
        t.p[0] + dx * k + (this.rand() - 0.5) * 1.4,
        t.p[1] + dy * k + (this.rand() - 0.5) * 1.4,
        t.p[2] + 1 + this.rand() * 2.4,
      ];
      t.mode = 'burst';
      t.path = {
        from: t.p.slice(), to: out, t0: this.clock + d * 0.035, dur: 0.55, ease: 'out', arc: null,
        next: { to: t.home.slice(), dur: 1.5 + this.rand() * 0.9, ease: 'inout', arc: randArc(this.rand, 0.6), endMode: 'home' },
      };
    }
    this.quietUntil = Math.max(this.quietUntil, this.clock + 3.2);
  }

  // Onboarding / offboarding: one person drifts out and fades; a newcomer arrives from the right and takes the spot.
  turnover() {
    const now = this.clock;
    const spare = this.tokens.find((t) => t.mode === 'spare');
    const candidates = this.tokens.filter((t, i) =>
      t.mode === 'home' && !t.assimAt && now > t.busyUntil && i !== this.focusIndex);
    if (!spare || candidates.length === 0) return false;
    const leaver = candidates[Math.floor(this.rand() * candidates.length)];
    const slot = leaver.home.slice();
    const [cx, cy, cz] = this.center;
    let ox = slot[0] - cx;
    let oy = slot[1] - cy;
    const length = Math.hypot(ox, oy);
    if (length < 1e-4) {
      ox = -1;
      oy = 0;
    } else {
      ox /= length;
      oy /= length;
    }
    leaver.home = null;
    leaver.mode = 'leave';
    leaver.colT = COLORS.paper.slice();
    leaver.path = {
      from: slot.slice(), to: [slot[0] + ox * 3.4, slot[1] + oy * 1.4 - 0.3, slot[2] + 1.8],
      t0: now, dur: 2.6, ease: 'inout', arc: [0, 0.5, 0.4], endMode: 'spare',
      onDone: (t) => {
        t.s = 0;
        t.sT = 0;
      },
    };
    const spawn = [cx + 5.4, cy - 1.4 + this.rand() * 2.4, cz + 0.8];
    spare.p = spawn.slice();
    spare.v = [0, 0, 0];
    spare.s = 0;
    spare.sT = 1;
    spare.col = COLORS.terra.slice();
    spare.colT = COLORS.terra.slice();
    spare.colRate = 0.9;
    spare.mode = 'arrive';
    spare.path = {
      from: spawn, to: slot, t0: now + 0.8, dur: 3, ease: 'inout', arc: [0, 0.7, 1.6], endMode: 'home',
      onDone: (t, when) => {
        t.home = slot;
        t.assimAt = when + 2.4;
        t.busyUntil = when + 8;
      },
    };
    return true;
  }

  setFocus(index) {
    if (index === this.focusIndex) return;
    const previous = this.tokens[this.focusIndex];
    if (previous) {
      previous.colT = COLORS.teal.slice();
      previous.colRate = 6;
    }
    this.focusIndex = index;
    const next = this.tokens[index];
    if (next) {
      next.colT = COLORS.terra.slice();
      next.colRate = 6;
    }
  }

  nearest(x, y) {
    let best = -1;
    let bestDistance = Infinity;
    this.tokens.forEach((t, i) => {
      if (t.mode !== 'home' || !t.home) return;
      const d = (t.home[0] - x) ** 2 + (t.home[1] + TOKEN_MIDDLE - y) ** 2;
      if (d < bestDistance) {
        bestDistance = d;
        best = i;
      }
    });
    return best;
  }

  advance(dt) {
    const h = Math.min(MAX_DT, Math.max(0, dt));
    this.clock += h;
    const now = this.clock;
    this.hover.amount += ((this.pointer.inside ? 1 : 0) - this.hover.amount) * Math.min(1, h * 5);
    const follow = Math.min(1, h * 16);
    for (let i = 0; i < 3; i++) this.hover.ptr[i] += (this.pointer.target[i] - this.hover.ptr[i]) * follow;
    if (this.turnovers && now > this.quietUntil && now > this.nextTurn) {
      this.turnover();
      this.nextTurn = now + 3.2 + this.rand() * 1.6;
    }
    updateTokens(this.tokens, now, h);
    this.acc += h;
    while (this.acc >= STEP) {
      stepPhysics(this.tokens, now, STEP, this.hover);
      this.acc -= STEP;
    }
    for (const t of this.tokens) updateTilt(t, h);
  }
}

// Help page: where the magnifying glass points, and which person it picks out.
export class MagnifierSim {
  constructor(sim, restAim, { seed = 11 } = {}) {
    this.sim = sim;
    this.rand = mulberry32(seed);
    this.pos = restAim.slice(0, 2);
    this.target = restAim.slice(0, 2);
    this.nextDrift = 3;
    this.bounds = { minX: Infinity, maxX: -Infinity, minY: Infinity, maxY: -Infinity };
    for (const t of sim.tokens) {
      if (!t.home) continue;
      this.bounds.minX = Math.min(this.bounds.minX, t.home[0]);
      this.bounds.maxX = Math.max(this.bounds.maxX, t.home[0]);
      this.bounds.minY = Math.min(this.bounds.minY, t.home[1]);
      this.bounds.maxY = Math.max(this.bounds.maxY, t.home[1] + 2 * TOKEN_MIDDLE);
    }
  }

  advance(dt) {
    const h = Math.min(MAX_DT, Math.max(0, dt));
    const { pointer, clock } = this.sim;
    if (pointer.inside) {
      const b = this.bounds;
      this.target = [clamp(pointer.target[0], b.minX, b.maxX), clamp(pointer.target[1], b.minY, b.maxY)];
      this.nextDrift = clock + 1.5;
    } else if (clock >= this.nextDrift) {
      const homes = this.sim.tokens.filter((t) => t.mode === 'home');
      const pick = homes[Math.floor(this.rand() * homes.length)];
      if (pick) this.target = [pick.home[0], pick.home[1] + TOKEN_MIDDLE];
      this.nextDrift = clock + 3;
    }
    const follow = Math.min(1, h * (pointer.inside ? 8 : 1.6));
    this.pos[0] += (this.target[0] - this.pos[0]) * follow;
    this.pos[1] += (this.target[1] - this.pos[1]) * follow;
    this.sim.setFocus(this.sim.nearest(this.pos[0], this.pos[1]));
  }

  aimPoint() {
    const focus = this.sim.tokens[this.sim.focusIndex];
    const z = focus && focus.home ? focus.home[2] + 0.1 : this.sim.center[2] + 1;
    return [this.pos[0], this.pos[1], z];
  }
}
```

- [ ] **Step 4: Run the tests to see them pass**

Run: `.venv/Scripts/python -m pytest tests/test_motion.py -q`
Expected: `12 passed`.

- [ ] **Step 5: Commit**

```bash
git add public/js/motion.js tests/test_motion.py
git commit -q -F - <<'EOF'
feat: crowd simulation with intro, turnover, burst, hover and magnifier aim

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
EOF
```

---
### Task 9: Drawing the crowd and the magnifier (Three.js view)

**Files:**
- Create: `public/js/crowd.js`, `tests/test_crowd.py`

**Interfaces:**
- Consumes: `coalesce.glb` and `layout.json` (Task 4); the `tokens` from `CrowdSim` and `aimPoint()` from `MagnifierSim` (Task 8).
- Produces `loadAssets(base) -> Promise<{ layout, person: BufferGeometry, magnifierParts: BufferGeometry[3] }>`. It rejects if a file is missing or a mesh isn't found.
- Produces `class CrowdView(canvas, assets, { preserveDrawingBuffer = false })`:
  - Fields: `renderer`, `scene`, `camera`, `pivot`, `figure`, `material`, `mesh`, `layout`.
  - Methods: `sync(tokens, scale)`, `setTilt(x, y)`, `pointerToFigure(ndcX, ndcY, planeZ = 1) -> [x, y, z] | null` (figure coordinates), `resize(width, height, pixelRatio)`, `render()`, `dispose()`.
- Produces `class MagnifierView(view, assets, { magnification = 2 })`:
  - Field: `group` (rim, collar and handle; layer 1).
  - Methods: `update(aim)`, `render()` (replaces `view.render()` on Help), `dispose()`.
- How the lens is drawn:
  1. Draw the scene normally.
  2. Clear depth, then punch a transparent hole in the lens shape and mark it in the stencil buffer.
  3. Redraw the crowd through a projection zoomed 2× about the lens centre, clipped to the stencil.
  4. Draw a glare overlay on top.
- The result is real magnification with the page showing through, and colors identical to the rest of the canvas.

- [ ] **Step 1: Write the failing tests**

`tests/test_crowd.py`:
```python
RENDER = """
    const { loadAssets, CrowdView, MagnifierView } = await import('/public/js/crowd.js');
    const { CrowdSim, MagnifierSim } = await import('/public/js/motion.js');
    const assets = await loadAssets('/public/assets/');
    const canvas = document.createElement('canvas');
    document.body.append(canvas);
    const view = new CrowdView(canvas, assets, { preserveDrawingBuffer: true });
    view.resize(700, 540, 1);
    const sim = new CrowdSim(assets.layout, { variant: VARIANT });
    let lens = null;
    if (VARIANT === 'help') {
      const aim = new MagnifierSim(sim, assets.layout.magnifier.restAim);
      aim.advance(0.016);
      lens = new MagnifierView(view, assets);
      view.sync(sim.tokens, assets.layout.tokenScale);
      lens.update(aim.aimPoint());
      lens.render();
    } else {
      view.sync(sim.tokens, assets.layout.tokenScale);
      view.render();
    }
    const gl = view.renderer.getContext();
    const pixels = new Uint8Array(4 * 700 * 540);
    gl.readPixels(0, 0, 700, 540, gl.RGBA, gl.UNSIGNED_BYTE, pixels);
    let opaque = 0;
    for (let i = 3; i < pixels.length; i += 4) if (pixels[i] > 0) opaque += 1;
    return { count: view.mesh.count, people: assets.layout.people.length, opaque,
             lensParts: lens ? lens.group.children.length : 0, glError: gl.getError() };
"""


def render_frame(js, variant):
    return js(RENDER.replace("VARIANT", repr(variant)))


def test_home_view_draws_the_crowd(js):
    r = render_frame(js, "home")
    assert r["count"] == r["people"] + 3
    assert r["opaque"] > 700 * 540 * 0.05
    assert r["glError"] == 0


def test_help_view_draws_the_crowd_and_the_magnifier(js):
    r = render_frame(js, "help")
    assert r["count"] == r["people"]
    assert r["lensParts"] == 3
    assert r["opaque"] > 700 * 540 * 0.05
    assert r["glError"] == 0


def test_pointer_ray_meets_the_figure_plane(js):
    r = js("""
        const { loadAssets, CrowdView } = await import('/public/js/crowd.js');
        const assets = await loadAssets('/public/assets/');
        const view = new CrowdView(document.createElement('canvas'), assets);
        return { hit: view.pointerToFigure(0, 0), target: assets.layout.camera.target };
    """)
    x, y, z = r["hit"]
    assert abs(x - r["target"][0]) < 0.05
    assert r["target"][1] < y < r["target"][1] + 0.5
    assert abs(z - 1.0) < 1e-6


def test_missing_assets_reject(js):
    message = js("""
        const { loadAssets } = await import('/public/js/crowd.js');
        try { await loadAssets('/public/no-such-folder/'); return 'resolved'; }
        catch (err) { return String(err && err.message || err); }
    """)
    assert message != "resolved"
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `.venv/Scripts/python -m pytest tests/test_crowd.py -q`
Expected: 4 failed (`crowd.js` not found).

- [ ] **Step 3: Write crowd.js**

`public/js/crowd.js`:
```js
// Three.js side of the hero: loads the Blender export and draws the crowd (plus the Help magnifier).
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';

const INK = 0x1b2423;

export async function loadAssets(base) {
  const [gltf, layout] = await Promise.all([
    new GLTFLoader().loadAsync(`${base}coalesce.glb`),
    fetch(`${base}layout.json`).then((res) => {
      if (!res.ok) throw new Error(`layout.json: HTTP ${res.status}`);
      return res.json();
    }),
  ]);
  gltf.scene.updateMatrixWorld(true);
  const geometry = (name) => {
    const node = gltf.scene.getObjectByName(name);
    if (!node || !node.isMesh) throw new Error(`coalesce.glb has no mesh named ${name}`);
    return node.geometry.clone().applyMatrix4(node.matrixWorld);
  };
  return {
    layout,
    person: geometry('Person'),
    magnifierParts: ['MagnifierRim', 'MagnifierCollar', 'MagnifierHandle'].map((name) => geometry(name)),
  };
}

export class CrowdView {
  constructor(canvas, assets, { preserveDrawingBuffer = false } = {}) {
    const { layout } = assets;
    this.layout = layout;
    this.renderer = new THREE.WebGLRenderer({
      canvas, antialias: true, alpha: true, stencil: true, powerPreference: 'high-performance', preserveDrawingBuffer,
    });
    this.renderer.setClearColor(0x000000, 0);
    this.renderer.toneMapping = THREE.AgXToneMapping;
    this.renderer.toneMappingExposure = 1.05;

    this.scene = new THREE.Scene();
    const pmrem = new THREE.PMREMGenerator(this.renderer);
    this.envTexture = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
    pmrem.dispose();
    this.scene.environment = this.envTexture;
    this.scene.environmentIntensity = 0.85;
    const key = new THREE.DirectionalLight(0xfff1e0, 2.2);
    key.position.set(-5, 8, 6);
    const rim = new THREE.DirectionalLight(0xffffff, 1.1);
    rim.position.set(4, 6, -6);
    this.scene.add(key, rim);

    const cam = layout.camera;
    this.camera = new THREE.PerspectiveCamera(cam.vfovDeg, cam.aspect, 0.1, 100);
    this.camera.position.fromArray(cam.position);
    this.camera.lookAt(new THREE.Vector3().fromArray(cam.target));
    this.camera.layers.enable(1);
    this.camera.updateMatrixWorld(true);

    // The figure tilts around its own centre: the pivot sits at the centre and the figure is offset back.
    const c = layout.figureCenter;
    this.pivot = new THREE.Group();
    this.pivot.position.fromArray(c);
    this.figure = new THREE.Group();
    this.figure.position.set(-c[0], -c[1], -c[2]);
    this.pivot.add(this.figure);
    this.scene.add(this.pivot);

    this.material = new THREE.MeshPhysicalMaterial({
      color: 0xffffff, roughness: 0.4, clearcoat: 0.3, clearcoatRoughness: 0.35,
    });
    this.mesh = new THREE.InstancedMesh(assets.person, this.material, layout.people.length + 3);
    this.mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
    this.mesh.frustumCulled = false;
    this.mesh.setColorAt(0, new THREE.Color(1, 1, 1));
    this.figure.add(this.mesh);

    this._dummy = new THREE.Object3D();
    this._color = new THREE.Color();
    this._raycaster = new THREE.Raycaster();
    this._plane = new THREE.Plane(new THREE.Vector3(0, 0, 1), 0);
    this._inverse = new THREE.Matrix4();
    this._ndc = new THREE.Vector2();
  }

  sync(tokens, scale) {
    const d = this._dummy;
    tokens.forEach((t, i) => {
      d.position.set(t.p[0], t.p[1], t.p[2]);
      d.rotation.set(t.rx, 0, t.rz);
      d.scale.setScalar(scale * Math.max(t.s, 1e-4));
      d.updateMatrix();
      this.mesh.setMatrixAt(i, d.matrix);
      this.mesh.setColorAt(i, this._color.setRGB(t.col[0], t.col[1], t.col[2]));
    });
    this.mesh.count = tokens.length;
    this.mesh.instanceMatrix.needsUpdate = true;
    this.mesh.instanceColor.needsUpdate = true;
  }

  setTilt(x, y) {
    this.pivot.rotation.set(x, y, 0);
  }

  // Where a pointer (normalized device coordinates) meets the plane z = planeZ, in figure coordinates.
  pointerToFigure(ndcX, ndcY, planeZ = 1.0) {
    this.scene.updateMatrixWorld(true);
    this._ndc.set(ndcX, ndcY);
    this._raycaster.setFromCamera(this._ndc, this.camera);
    this._inverse.copy(this.figure.matrixWorld).invert();
    const ray = this._raycaster.ray.clone().applyMatrix4(this._inverse);
    this._plane.constant = -planeZ;
    const hit = ray.intersectPlane(this._plane, new THREE.Vector3());
    return hit ? [hit.x, hit.y, hit.z] : null;
  }

  resize(width, height, pixelRatio) {
    this.renderer.setPixelRatio(pixelRatio);
    this.renderer.setSize(width, height, false);
    this.camera.aspect = width / height;
    this.camera.updateProjectionMatrix();
  }

  render() {
    this.renderer.render(this.scene, this.camera);
  }

  dispose() {
    this.mesh.geometry.dispose();
    this.mesh.dispose();
    this.material.dispose();
    this.envTexture.dispose();
    this.renderer.dispose();
  }
}

function glareTexture() {
  const size = 256;
  const canvas = document.createElement('canvas');
  canvas.width = size;
  canvas.height = size;
  const g = canvas.getContext('2d');
  const shine = g.createRadialGradient(size * 0.34, size * 0.3, 0, size * 0.34, size * 0.3, size * 0.55);
  shine.addColorStop(0, 'rgba(255,255,255,0.32)');
  shine.addColorStop(1, 'rgba(255,255,255,0)');
  g.fillStyle = shine;
  g.fillRect(0, 0, size, size);
  const edge = g.createRadialGradient(size / 2, size / 2, size * 0.36, size / 2, size / 2, size * 0.5);
  edge.addColorStop(0, 'rgba(27,36,35,0)');
  edge.addColorStop(1, 'rgba(27,36,35,0.2)');
  g.fillStyle = edge;
  g.fillRect(0, 0, size, size);
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
}

export class MagnifierView {
  constructor(view, assets, { magnification = 2 } = {}) {
    this.view = view;
    this.magnification = magnification;
    const { lensRadius, standoff } = view.layout.magnifier;
    this.standoff = standoff;

    this.group = new THREE.Group();
    this.inkMaterial = new THREE.MeshPhysicalMaterial({ color: INK, roughness: 0.3, metalness: 0.5, clearcoat: 0.4 });
    for (const geometry of assets.magnifierParts) this.group.add(new THREE.Mesh(geometry, this.inkMaterial));
    this.group.traverse((object) => object.layers.set(1));
    view.figure.add(this.group);

    const disc = new THREE.CircleGeometry(lensRadius, 64);
    this.mask = new THREE.Mesh(disc, new THREE.MeshBasicMaterial({
      color: 0x000000, transparent: true, opacity: 0, blending: THREE.NoBlending, depthWrite: false,
      stencilWrite: true, stencilRef: 1, stencilFunc: THREE.AlwaysStencilFunc, stencilZPass: THREE.ReplaceStencilOp,
    }));
    this.glare = new THREE.Mesh(disc, new THREE.MeshBasicMaterial({
      map: glareTexture(), transparent: true, depthTest: false, depthWrite: false,
    }));
    this.mask.matrixAutoUpdate = false;
    this.glare.matrixAutoUpdate = false;
    this.maskScene = new THREE.Scene();
    this.maskScene.add(this.mask);
    this.glareScene = new THREE.Scene();
    this.glareScene.add(this.glare);

    this.zoomCamera = new THREE.PerspectiveCamera();
    this.zoomCamera.layers.set(0);
    this._aim = new THREE.Vector3();
    this._eye = new THREE.Vector3();
    this._centre = new THREE.Vector3();
    this._zoom = new THREE.Matrix4();
  }

  // Place the glass between the viewer and `aim` (figure coordinates), facing the viewer.
  update(aim) {
    const { scene, figure, camera } = this.view;
    scene.updateMatrixWorld(true);
    this._aim.fromArray(aim);
    this._eye.copy(camera.position);
    figure.worldToLocal(this._eye);
    this._eye.sub(this._aim).normalize();
    this.group.position.copy(this._aim).addScaledVector(this._eye, this.standoff);
    this.group.lookAt(camera.position);
    this.group.updateMatrixWorld(true);
    this.mask.matrix.copy(this.group.matrixWorld);
    this.glare.matrix.copy(this.group.matrixWorld);
  }

  render() {
    const { renderer, scene, camera, material } = this.view;
    renderer.render(scene, camera);
    renderer.autoClear = false;
    renderer.clearDepth();
    renderer.clearStencil();
    renderer.render(this.maskScene, camera);
    this.aimZoomCamera();
    material.stencilWrite = true;
    material.stencilFunc = THREE.EqualStencilFunc;
    material.stencilRef = 1;
    material.stencilZPass = THREE.KeepStencilOp;
    renderer.render(scene, this.zoomCamera);
    material.stencilWrite = false;
    material.stencilFunc = THREE.AlwaysStencilFunc;
    renderer.render(this.glareScene, camera);
    renderer.autoClear = true;
  }

  // The zoom camera sees what the main camera sees, scaled up about the lens centre on screen.
  aimZoomCamera() {
    const { camera } = this.view;
    const zoom = this.zoomCamera;
    zoom.position.copy(camera.position);
    zoom.quaternion.copy(camera.quaternion);
    zoom.updateMatrixWorld(true);
    this.group.getWorldPosition(this._centre).project(camera);
    const m = this.magnification;
    this._zoom.set(
      m, 0, 0, this._centre.x * (1 - m),
      0, m, 0, this._centre.y * (1 - m),
      0, 0, 1, 0,
      0, 0, 0, 1,
    );
    zoom.projectionMatrix.multiplyMatrices(this._zoom, camera.projectionMatrix);
    zoom.projectionMatrixInverse.copy(zoom.projectionMatrix).invert();
  }

  dispose() {
    this.view.figure.remove(this.group);
    this.inkMaterial.dispose();
    this.mask.geometry.dispose();
    this.mask.material.dispose();
    this.glare.material.map.dispose();
    this.glare.material.dispose();
  }
}
```

- [ ] **Step 4: Run the tests to see them pass**

Run: `.venv/Scripts/python -m pytest tests/test_crowd.py -q`
Expected: `4 passed`.

- [ ] **Step 5: Commit**

```bash
git add public/js/crowd.js tests/test_crowd.py
git commit -q -F - <<'EOF'
feat: Three.js view for the crowd and the Help magnifier lens

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
EOF
```

---

### Task 10: The live hero (orchestration, fallbacks and controls)

**Files:**
- Modify: `public/js/hero.js` (replace the Task 6 stub entirely)
- Create: `tests/test_hero.py`

**Interfaces:**
- Consumes: `eligibility.js` (Task 7), `motion.js` (Task 8), `crowd.js` (Task 9) and the page hooks (Task 6).
- Produces `mountHero(stage, { variant = 'home', assetsBase = 'assets/', watchdog = true, watchdogLimitMs = 45 }) -> Promise<{ state, reason }>`.
  - It sets `stage.dataset.heroState` to `'live'|'still'` and `stage.dataset.heroReason` to one of: `ok`, `loading`, `no-webgl`, `reduced-motion`, `no-hover`, `save-data`, `load-failed`, `webgl-failed`, `too-slow`, `context-lost`.
  - `stage.dataset.heroFrames` counts rendered frames.
  - `stage.__coalesce = { sim, aim, view, stop }` is a handle for tests and debugging.
  - `crowd.js` and `motion.js` are imported **dynamically**, only after the device qualifies.

- [ ] **Step 1: Write the failing tests**

`tests/test_hero.py`:
```python
import pytest

from helpers import collect_errors, hero_result

HOME = "/public/index.html"
HELP = "/public/help/index.html"


def frames(page):
    return page.eval_on_selector("[data-hero]", "el => Number(el.dataset.heroFrames || 0)")


def wait_for_intro(page):
    page.wait_for_function(
        "() => (document.querySelector('[data-hero]').__coalesce?.sim.clock || 0) > 4", timeout=30000)


@pytest.mark.parametrize("url", [HOME, HELP])
def test_goes_live_on_desktop(make_page, base_url, url):
    page = make_page()
    errors = collect_errors(page)
    page.goto(f"{base_url}{url}?nowatchdog")
    assert hero_result(page) == ["live", "ok"]
    assert page.locator("[data-hero] canvas").count() == 1
    assert page.locator("[data-pause]").is_visible()
    first = frames(page)
    page.wait_for_timeout(600)
    assert frames(page) > first
    assert errors == []


def test_pause_stops_and_resumes_rendering(make_page, base_url):
    page = make_page()
    page.goto(f"{base_url}{HOME}?nowatchdog")
    assert hero_result(page) == ["live", "ok"]
    pause = page.locator("[data-pause]")
    pause.click()
    assert pause.get_attribute("aria-pressed") == "true" and pause.inner_text() == "Play motion"
    page.wait_for_timeout(200)
    stopped_at = frames(page)
    clock = page.eval_on_selector("[data-hero]", "el => el.__coalesce.sim.clock")
    page.wait_for_timeout(800)
    assert frames(page) == stopped_at
    pause.click()
    page.wait_for_timeout(600)
    assert frames(page) > stopped_at
    resumed_clock = page.eval_on_selector("[data-hero]", "el => el.__coalesce.sim.clock")
    assert resumed_clock - clock < 1.0  # continues from where it stopped, no jump


def test_reduced_motion_keeps_still_and_skips_three(make_page, base_url):
    page = make_page(reduced_motion="reduce")
    requested = []
    page.on("request", lambda request: requested.append(request.url))
    page.goto(f"{base_url}{HOME}")
    assert hero_result(page) == ["still", "reduced-motion"]
    page.wait_for_load_state("networkidle")
    assert not any("three.module" in url or "coalesce.glb" in url for url in requested)
    assert page.locator("[data-hero] canvas").count() == 0
    assert page.locator(".hero-still").is_visible()
    assert page.locator("[data-pause]").is_hidden()


def test_touch_device_keeps_still(make_page, base_url):
    page = make_page(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
    page.goto(f"{base_url}{HOME}")
    assert hero_result(page) == ["still", "no-hover"]


def test_no_webgl_keeps_still(make_page, base_url, browser_no_webgl):
    page = make_page(target_browser=browser_no_webgl)
    page.goto(f"{base_url}{HOME}")
    assert hero_result(page) == ["still", "no-webgl"]


def test_asset_failure_keeps_still(make_page, base_url):
    page = make_page()
    errors = collect_errors(page)
    page.route("**/coalesce.glb", lambda route: route.abort())
    page.goto(f"{base_url}{HOME}?nowatchdog")
    assert hero_result(page) == ["still", "load-failed"]
    assert page.locator(".hero-still").is_visible()
    assert not [e for e in errors if e.startswith("pageerror")]


def test_slow_machine_falls_back(make_page, base_url):
    page = make_page()
    page.goto(f"{base_url}{HOME}?watchdogLimitMs=0")
    page.wait_for_function(
        "document.querySelector('[data-hero]').dataset.heroReason === 'too-slow'", timeout=20000)
    assert page.locator("[data-hero] canvas").count() == 0
    assert page.locator("[data-pause]").is_hidden()
    assert page.locator(".hero-still").is_visible()


def test_home_hover_parts_people_and_click_scatters_them(make_page, base_url):
    page = make_page()
    page.goto(f"{base_url}{HOME}?nowatchdog")
    assert hero_result(page) == ["live", "ok"]
    wait_for_intro(page)
    box = page.locator("[data-hero]").bounding_box()
    x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    page.mouse.move(x, y)
    page.wait_for_timeout(1500)
    moved = page.eval_on_selector("[data-hero]", """el => Math.max(...el.__coalesce.sim.tokens
        .filter((t) => t.mode === 'home')
        .map((t) => Math.hypot(t.p[0] - t.home[0], t.p[1] - t.home[1], t.p[2] - t.home[2])))""")
    assert moved > 0.25
    page.mouse.click(x, y)
    page.wait_for_timeout(100)
    bursting = page.eval_on_selector("[data-hero]", "el => el.__coalesce.sim.tokens.filter((t) => t.mode === 'burst').length")
    assert bursting > 50


def test_help_magnifier_follows_the_pointer_and_highlights_one_person(make_page, base_url):
    page = make_page()
    page.goto(f"{base_url}{HELP}?nowatchdog")
    assert hero_result(page) == ["live", "ok"]
    wait_for_intro(page)
    box = page.locator("[data-hero]").bounding_box()
    page.mouse.move(box["x"] + box["width"] * 0.40, box["y"] + box["height"] * 0.45)
    page.wait_for_timeout(1500)
    first = page.eval_on_selector("[data-hero]", """el => {
        const { sim, aim } = el.__coalesce;
        return { focus: sim.focusIndex, pos: aim.pos.slice(), target: aim.target.slice(),
                 terra: sim.tokens.filter((t) => t.colT[0] > t.colT[1]).length };
    }""")
    assert first["focus"] >= 0 and first["terra"] == 1
    assert abs(first["pos"][0] - first["target"][0]) < 0.1 and abs(first["pos"][1] - first["target"][1]) < 0.1
    page.mouse.move(box["x"] + box["width"] * 0.62, box["y"] + box["height"] * 0.70)
    page.wait_for_timeout(1500)
    second = page.eval_on_selector("[data-hero]", "el => el.__coalesce.sim.focusIndex")
    assert second >= 0 and second != first["focus"]


def test_help_has_no_arrivals_or_departures(make_page, base_url):
    page = make_page()
    page.goto(f"{base_url}{HELP}?nowatchdog")
    assert hero_result(page) == ["live", "ok"]
    page.wait_for_timeout(8000)
    modes = page.eval_on_selector("[data-hero]", "el => [...new Set(el.__coalesce.sim.tokens.map((t) => t.mode))]")
    assert set(modes) <= {"home", "intro"}
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `.venv/Scripts/python -m pytest tests/test_hero.py -q`
Expected: failures. The stub always reports `still`/`not-built`, so the tests expecting other results fail. `test_touch_device_keeps_still` and `test_no_webgl_keeps_still` fail too, because the stub reports `not-built`.

- [ ] **Step 3: Replace hero.js with the real orchestration**

`public/js/hero.js`:
```js
// Mounts the live 3D hero, or leaves the still image in place when 3D shouldn't or can't run.
// Three.js and the 3D assets download only after the device qualifies.
import { readEnvironment, decideMode, FrameWatchdog } from './eligibility.js';

const MAX_PIXEL_RATIO = 1.75;

export async function mountHero(stage, options = {}) {
  if (!stage) return { state: 'still', reason: 'no-stage' };
  const { variant = 'home', assetsBase = 'assets/', watchdog = true, watchdogLimitMs = 45 } = options;
  const setState = (state, reason) => {
    stage.dataset.heroState = state;
    stage.dataset.heroReason = reason;
    return { state, reason };
  };
  const decision = decideMode(readEnvironment(window));
  if (!decision.live) return setState('still', decision.reason);
  setState('still', 'loading');
  let modules;
  try {
    const [crowd, motion] = await Promise.all([import('./crowd.js'), import('./motion.js')]);
    modules = { crowd, motion, assets: await crowd.loadAssets(assetsBase) };
  } catch (err) {
    console.warn('Coalesce: the 3D figure could not load, so the still image stays.', err);
    return setState('still', 'load-failed');
  }
  return startLive(stage, modules, { variant, watchdog, watchdogLimitMs, setState });
}

function startLive(stage, { crowd, motion, assets }, { variant, watchdog, watchdogLimitMs, setState }) {
  const canvas = document.createElement('canvas');
  canvas.setAttribute('aria-hidden', 'true');
  let view;
  let lens = null;
  try {
    view = new crowd.CrowdView(canvas, assets);
    if (variant === 'help') lens = new crowd.MagnifierView(view, assets);
  } catch (err) {
    console.warn('Coalesce: WebGL setup failed, so the still image stays.', err);
    return setState('still', 'webgl-failed');
  }
  const { layout } = assets;
  const sim = new motion.CrowdSim(layout, { variant });
  const aim = lens ? new motion.MagnifierSim(sim, layout.magnifier.restAim) : null;
  const pauseButton = stage.parentElement.querySelector('[data-pause]');
  const dog = watchdog ? new FrameWatchdog({ limitMs: watchdogLimitMs }) : null;
  const tilt = { x: 0, y: 0, targetX: 0, targetY: 0 };
  let paused = false;
  let onScreen = true;
  let stopped = false;
  let rafId = 0;
  let last = 0;
  let frames = 0;

  stage.append(canvas);
  stage.classList.add('is-live');
  sim.intro();

  const resize = () => {
    const width = stage.clientWidth;
    const height = stage.clientHeight;
    if (width && height) view.resize(width, height, Math.min(window.devicePixelRatio || 1, MAX_PIXEL_RATIO));
  };
  const sizeObserver = new ResizeObserver(resize);
  sizeObserver.observe(stage);
  resize();

  function frame(now) {
    rafId = 0;
    if (stopped) return;
    const dtMs = last ? Math.min(100, now - last) : 1000 / 60;
    last = now;
    if (dog && dog.add(dtMs) === 'too-slow') {
      stop('too-slow');
      return;
    }
    const dt = dtMs / 1000;
    sim.advance(dt);
    if (aim) aim.advance(dt);
    const follow = Math.min(1, dt * 3);
    tilt.x += (tilt.targetX - tilt.x) * follow;
    tilt.y += (tilt.targetY - tilt.y) * follow;
    view.setTilt(tilt.x, tilt.y);
    view.sync(sim.tokens, layout.tokenScale);
    if (lens) {
      lens.update(aim.aimPoint());
      lens.render();
    } else {
      view.render();
    }
    frames += 1;
    stage.dataset.heroFrames = String(frames);
    schedule();
  }

  function schedule() {
    if (!rafId && !stopped && !paused && onScreen && !document.hidden) rafId = requestAnimationFrame(frame);
  }

  function unschedule() {
    if (rafId) cancelAnimationFrame(rafId);
    rafId = 0;
    last = 0;
  }

  const toNdc = (event) => {
    const r = canvas.getBoundingClientRect();
    return [((event.clientX - r.left) / r.width) * 2 - 1, 1 - ((event.clientY - r.top) / r.height) * 2];
  };
  canvas.addEventListener('pointermove', (event) => {
    const [x, y] = toNdc(event);
    tilt.targetX = -y * 0.1;
    tilt.targetY = x * 0.24;
    sim.setPointer(view.pointerToFigure(x, y), true);
  });
  canvas.addEventListener('pointerleave', () => {
    tilt.targetX = 0;
    tilt.targetY = 0;
    sim.setPointer(null, false);
  });
  canvas.addEventListener('click', (event) => {
    if (paused) return;
    const [x, y] = toNdc(event);
    const point = view.pointerToFigure(x, y);
    if (point) sim.burst(point);
  });
  canvas.addEventListener('webglcontextlost', (event) => {
    event.preventDefault();
    stop('context-lost');
  });

  const onPause = () => {
    paused = !paused;
    pauseButton.setAttribute('aria-pressed', String(paused));
    pauseButton.textContent = paused ? 'Play motion' : 'Pause motion';
    if (paused) unschedule();
    else schedule();
  };
  if (pauseButton) {
    pauseButton.hidden = false;
    pauseButton.addEventListener('click', onPause);
  }

  const visibility = new IntersectionObserver((entries) => {
    onScreen = entries[entries.length - 1].isIntersecting;
    if (onScreen) schedule();
    else unschedule();
  });
  visibility.observe(stage);
  const onVisibilityChange = () => {
    if (document.hidden) unschedule();
    else schedule();
  };
  document.addEventListener('visibilitychange', onVisibilityChange);

  function stop(reason) {
    if (stopped) return;
    stopped = true;
    unschedule();
    sizeObserver.disconnect();
    visibility.disconnect();
    document.removeEventListener('visibilitychange', onVisibilityChange);
    if (pauseButton) {
      pauseButton.hidden = true;
      pauseButton.removeEventListener('click', onPause);
    }
    canvas.remove();
    stage.classList.remove('is-live');
    if (lens) lens.dispose();
    view.dispose();
    setState('still', reason);
  }

  stage.__coalesce = { sim, aim, view, stop };
  setState('live', 'ok');
  schedule();
  return { state: 'live', reason: 'ok', stop };
}
```

- [ ] **Step 4: Run the hero tests to see them pass**

Run: `.venv/Scripts/python -m pytest tests/test_hero.py -q`
Expected: `11 passed`.

If `test_touch_device_keeps_still` gets `["live", "ok"]`, this Chromium's mobile emulation isn't switching the `hover`/`pointer` media features. Stop and report it; don't weaken the assertion. The phone fallback depends on that media query.

- [ ] **Step 5: Run the whole suite**

Run: `.venv/Scripts/python -m pytest -q`
Expected: all tests pass (the stills test stays deselected).

- [ ] **Step 6: Commit**

```bash
git add public/js/hero.js tests/test_hero.py
git commit -q -F - <<'EOF'
feat: live 3D hero with still-image fallbacks, pause and watchdog

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
EOF
```

---
### Task 11: Visual verification and budgets

**Files:**
- Create: `tools/verify.py`
- Modify (only if the screenshots show problems): `public/css/site.css`, `blender/coalesce_layout.py`

**Interfaces:**
- Consumes the finished pages (Tasks 5–10).
- Produces `verify-output/*.png` and `verify-output/report.json` (gitignored). The exit code is 1 if a budget or an expected state fails.

- [ ] **Step 1: Write the verification script**

`tools/verify.py`:
```python
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
    for key, limit in BUDGETS.items():
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
```

- [ ] **Step 2: Run it**

Run: `.venv/Scripts/python tools/verify.py`
Expected:
- A browser window opens and closes. The script prints the measures and ends with `All budgets and states OK.`
- Twelve PNGs appear in `verify-output/`.
- If a budget fails, the printout names it. Fix the cause, never the budget:
  - Frame time: lower `MAX_PIXEL_RATIO` in `hero.js` to 1.5.
  - Transfer size: re-encode the stills at a lower `quality` in `build_coalesce.py`.

- [ ] **Step 3: Review every screenshot**

Open each PNG in `verify-output/` (Read tool) and check it against the approved mockups (canvas direction B and the B Help page).

| Screenshot | Must show |
|---|---|
| `home-live` | The whole figure assembled, headline overlapping its lower edge without covering people's heads, and both buttons |
| `home-hover` | A visible parting where the pointer is |
| `home-burst` | People scattered |
| `home-paused` | The button reads "Play motion" |
| `help-magnifier`, `help-magnifier-2` | The lens over the figure, one terracotta person enlarged inside it, the page color (not black) between people in the lens, and the handle attached down-right |
| `*-reduced-motion` | The Blender still, no pause button |
| `*-phone` | Single column, readable text, still image, no clipped cards |

Fix any problem you find:
- Layout and overlap issues belong in `site.css` (for example, `.hero-home .hero-copy` `margin-top`).
- Lens framing belongs in `coalesce_layout.MAGNIFIER` (`standoff`, `restAim`). Rebuild with the Task 4 Step 6 command after changing it.

Then re-run Step 2.

- [ ] **Step 4: Run the whole suite again**

Run: `.venv/Scripts/python -m pytest -q`
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add tools/verify.py public blender
git commit -q -F - <<'EOF'
test: add screenshot and budget verification; visual fixes from review

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
EOF
```

---

### Task 12: Release script for the Download button

**Files:**
- Create: `tools/publish-release.ps1`, `tests/test_publish_release.py`

**Interfaces:**
- Consumes nothing from the site code.
- Produces this usage: `publish-release.ps1 -GitLabUrl <url> -Project <group/name> -Version <x.y.z> -File <path> [-Ref main] [-Notes text] [-DryRun]`.
- A normal run does two things:
  1. `PUT {api}/packages/generic/coalesce/{Version}/{file}` uploads the add-in.
  2. `POST {api}/releases` creates tag `v{Version}` with one asset link: `link_type` `package`, `direct_asset_path` `/{file}`.
- `-DryRun` prints the two request lines and the JSON body instead of sending them.

- [ ] **Step 1: Write the failing tests**

`tests/test_publish_release.py`:
```python
import json
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "publish-release.ps1"


def powershell():
    exe = shutil.which("powershell") or shutil.which("powershell.exe")
    if not exe:
        pytest.skip("Windows PowerShell is not available")
    return exe


def test_script_has_no_syntax_errors():
    command = ("$errors = $null; [void][System.Management.Automation.Language.Parser]::ParseFile("
               f"'{SCRIPT}', [ref]$null, [ref]$errors); $errors.Count")
    result = subprocess.run([powershell(), "-NoProfile", "-Command", command], capture_output=True, text=True, check=True)
    assert result.stdout.strip() == "0"


def test_dry_run_builds_a_release_with_the_direct_asset_path(tmp_path):
    xlam = tmp_path / "Coalesce.xlam"
    xlam.write_bytes(b"PK\x03\x04 not a real add-in")
    result = subprocess.run(
        [powershell(), "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(SCRIPT),
         "-GitLabUrl", "https://gitlab.example.com/", "-Project", "ops/coalesce",
         "-Version", "2.4.0", "-File", str(xlam), "-DryRun"],
        capture_output=True, text=True, check=True)
    lines = result.stdout.splitlines()
    api = "https://gitlab.example.com/api/v4/projects/ops%2Fcoalesce"
    assert lines[0] == f"PUT  {api}/packages/generic/coalesce/2.4.0/Coalesce.xlam"
    assert lines[1] == f"POST {api}/releases"
    body = json.loads("\n".join(lines[2:]))
    assert body["tag_name"] == "v2.4.0" and body["ref"] == "main"
    link = body["assets"]["links"][0]
    assert link["direct_asset_path"] == "/Coalesce.xlam"
    assert link["url"] == f"{api}/packages/generic/coalesce/2.4.0/Coalesce.xlam"
    assert link["link_type"] == "package"
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `.venv/Scripts/python -m pytest tests/test_publish_release.py -q`
Expected: 2 failed (the script doesn't exist).

- [ ] **Step 3: Write the script**

`tools/publish-release.ps1`:
```powershell
<#
.SYNOPSIS
  Publish a Coalesce release on GitLab with the .xlam attached, so the website's Download
  button (downloadLink = 'direct') always fetches the newest file.

.DESCRIPTION
  1. Uploads the add-in to the project's generic package registry.
  2. Creates the release (and its tag) with an asset link whose direct asset path is /<file name>,
     which is what .../-/releases/permalink/latest/downloads/<file name> resolves to.
  Needs a GitLab personal access token with the "api" scope, in $env:GITLAB_TOKEN or typed when asked.

.EXAMPLE
  .\publish-release.ps1 -GitLabUrl https://gitlab.example.com -Project ops/coalesce -Version 2.4.0 -File .\Coalesce.xlam
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)] [string] $GitLabUrl,
    [Parameter(Mandatory = $true)] [string] $Project,
    [Parameter(Mandatory = $true)] [string] $Version,
    [Parameter(Mandatory = $true)] [string] $File,
    [string] $Ref = 'main',
    [string] $Notes = '',
    [switch] $DryRun
)

$ErrorActionPreference = 'Stop'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

if (-not (Test-Path -LiteralPath $File -PathType Leaf)) { throw "File not found: $File" }
$fileName = [IO.Path]::GetFileName($File)
$base = $GitLabUrl.TrimEnd('/')
$api = "$base/api/v4/projects/$([uri]::EscapeDataString($Project))"
$packageUrl = "$api/packages/generic/coalesce/$Version/$fileName"
$description = if ($Notes) { $Notes } else { "Coalesce $Version" }
$release = [ordered]@{
    name        = "Coalesce $Version"
    tag_name    = "v$Version"
    ref         = $Ref
    description = $description
    assets      = @{ links = @(@{ name = $fileName; url = $packageUrl; link_type = 'package'; direct_asset_path = "/$fileName" }) }
}
$body = $release | ConvertTo-Json -Depth 6

if ($DryRun) {
    Write-Output "PUT  $packageUrl"
    Write-Output "POST $api/releases"
    Write-Output $body
    return
}

$token = $env:GITLAB_TOKEN
if (-not $token) {
    $secure = Read-Host 'GitLab personal access token (api scope)' -AsSecureString
    $token = [Runtime.InteropServices.Marshal]::PtrToStringBSTR([Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure))
}
$headers = @{ 'PRIVATE-TOKEN' = $token }

Write-Output "Uploading $fileName ..."
Invoke-RestMethod -Method Put -Uri $packageUrl -Headers $headers -InFile $File | Out-Null
Write-Output "Creating release v$Version from $Ref ..."
Invoke-RestMethod -Method Post -Uri "$api/releases" -Headers $headers -ContentType 'application/json' -Body $body | Out-Null
Write-Output "Done. Newest download: $base/$Project/-/releases/permalink/latest/downloads/$fileName"
```

- [ ] **Step 4: Run the tests to see them pass**

Run: `.venv/Scripts/python -m pytest tests/test_publish_release.py -q`
Expected: `2 passed`.

- [ ] **Step 5: Commit**

```bash
git add tools/publish-release.ps1 tests/test_publish_release.py
git commit -q -F - <<'EOF'
feat: release script that attaches the .xlam with a permanent latest link

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
EOF
```

---

### Task 13: README, Pages job and the zip

**Files:**
- Create: `README.md`, `.gitlab-ci.yml`, `tools/package.py`, `tests/test_package.py`

**Interfaces:**
- Consumes everything above.
- Produces `tools/package.py`: `files_to_ship()` and `build(dest=dist/coalesce-site.zip) -> Path`. Every archive path starts with `coalesce-site/`.

- [ ] **Step 1: Write the failing tests**

`tests/test_package.py`:
```python
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

MUST_SHIP = [
    "public/index.html", "public/help/index.html", "public/site-config.js", "public/css/site.css",
    "public/js/hero.js", "public/js/crowd.js", "public/js/motion.js", "public/js/config.js", "public/js/eligibility.js",
    "public/assets/coalesce.glb", "public/assets/layout.json", "public/assets/home-still.webp",
    "public/assets/help-still.webp", "public/vendor/three/build/three.module.min.js", "public/fonts/OFL.txt",
    "blender/build_coalesce.py", "blender/coalesce_layout.py", "blender/coalesce.blend",
    "tools/publish-release.ps1", "tools/serve.py", "tools/verify.py", "requirements-dev.txt",
    "README.md", ".gitlab-ci.yml",
]


def test_zip_ships_the_site_and_its_sources_only(tmp_path):
    import package

    path = package.build(tmp_path / "coalesce-site.zip")
    names = set(zipfile.ZipFile(path).namelist())
    for rel in MUST_SHIP:
        assert f"coalesce-site/{rel}" in names, rel
    unwanted = ("coalesce-site/docs/", "coalesce-site/tests/", "coalesce-site/.venv/", "coalesce-site/dist/")
    assert not [n for n in names if n.startswith(unwanted) or "__pycache__" in n]
    assert path.stat().st_size < 3_000_000


def test_pages_job_publishes_public():
    ci = (ROOT / ".gitlab-ci.yml").read_text(encoding="utf-8")
    assert "pages:" in ci and "- public" in ci


def test_readme_covers_install_settings_and_releases():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for heading in ("## Install it in your GitLab project", "## The settings file",
                    "## Publishing a release", "## Preview on your PC"):
        assert heading in readme, heading
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `.venv/Scripts/python -m pytest tests/test_package.py -q`
Expected: 3 failed (`package`, `.gitlab-ci.yml` and `README.md` don't exist).

- [ ] **Step 3: Write the Pages job, the packager and the README**

`.gitlab-ci.yml`:
```yaml
# Publishes the public/ folder with GitLab Pages, exactly as it is (no build step).
# Only needed if your project doesn't already have a "pages" job.
pages:
  stage: deploy
  script:
    - echo "Publishing public/ as-is"
  artifacts:
    paths:
      - public
  rules:
    - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH
```

`tools/package.py`:
```python
"""Build dist/coalesce-site.zip: everything needed at work, and nothing else.

  .venv/Scripts/python tools/package.py
"""
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHIP = ["public", "blender", "tools", ".gitlab-ci.yml", "README.md", "requirements-dev.txt"]
SKIP_PARTS = {"__pycache__"}
SKIP_SUFFIXES = {".pyc", ".blend1"}


def files_to_ship():
    for item in SHIP:
        path = ROOT / item
        candidates = [path] if path.is_file() else sorted(p for p in path.rglob("*") if p.is_file())
        for file in candidates:
            if SKIP_PARTS.isdisjoint(file.relative_to(ROOT).parts) and file.suffix not in SKIP_SUFFIXES:
                yield file


def build(dest=ROOT / "dist" / "coalesce-site.zip"):
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dest, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file in files_to_ship():
            archive.write(file, (Path("coalesce-site") / file.relative_to(ROOT)).as_posix())
    return dest


if __name__ == "__main__":
    path = build()
    print(f"wrote {path.relative_to(ROOT)} ({path.stat().st_size / 1e6:.2f} MB)")
```

`README.md`:
````markdown
# Coalesce website

The project home for Coalesce, the Excel add-in. It has two pages:
- **Home:** download, install, docs, releases, access.
- **Help:** service desk, tutorial, SOP.

Both open with an interactive 3D figure made of many small people.

The site is plain HTML, CSS and JavaScript. GitLab Pages publishes the `public/` folder exactly as it is: there is no build step and no server code.

## Install it in your GitLab project

1. Unzip `coalesce-site.zip`. Copy everything inside the `coalesce-site/` folder into your project's repository, replacing the existing `public/` folder. If your project already has a `.gitlab-ci.yml` with a `pages` job that publishes `public/`, keep yours and don't copy ours.
2. Fill in `public/site-config.js` (see the next section).
3. Commit and push to your default branch. The **pages** job publishes the site in a minute or two. **Deploy → Pages** shows its address.

## The settings file

Every link, your team name and the version shown on the page live in `public/site-config.js`. Paste full links that start with `https://`. If a setting is left empty, the page shows "Link coming soon" instead of a broken link.

| Setting | What it's for |
|---|---|
| `teamName` | Shown in the footer and on the Help page |
| `gitlabProjectUrl` | Your project's address, for example `https://gitlab.example.com/ops/coalesce`. The Releases, Download and GitLab project links are built from it |
| `xlamFileName` | The add-in's file name (normally `Coalesce.xlam`) |
| `downloadLink` | `'release-page'` (the default): Download opens the newest release. `'direct'`: Download fetches the newest `.xlam` itself (see the next section) |
| `version`, `releaseDate` | Shown under the Download button; update them with each release |
| `links.docs` | The usage docs / SOP |
| `links.tutorial` | The interactive tutorial |
| `links.serviceDesk` | Your Jira service desk portal (also used for "Report an issue") |
| `links.access` | How to request access |

## Publishing a release

GitLab can give a release file a permanent "always the newest" address. It only does that when the file is attached through its API, and `tools/publish-release.ps1` handles that for you from Windows PowerShell:

```powershell
$env:GITLAB_TOKEN = '<a personal access token with the api scope>'
powershell -ExecutionPolicy Bypass -File .\tools\publish-release.ps1 -GitLabUrl https://gitlab.example.com -Project ops/coalesce -Version 2.4.0 -File .\Coalesce.xlam
```

The script:
- uploads the file to the project's package registry;
- creates release `v2.4.0` from `main` (change it with `-Ref`, add release notes with `-Notes "…"`);
- with `-DryRun`, shows what it would send without sending anything.

After your first release made this way, set `downloadLink: 'direct'` in `site-config.js`. From then on, the Download button fetches the newest file. With each release, also update `version` and `releaseDate` there.

It needs GitLab 15 or newer and a personal access token with the `api` scope. To create one, go to your avatar → **Edit profile** → **Access tokens**.

## Preview on your PC

With Python installed, run this from the unzipped folder:

```powershell
python tools/serve.py
```

Then open <http://127.0.0.1:8000/>. Double-clicking `index.html` won't show the 3D figure, because browsers block 3D files opened straight from disk.

## When the page shows a picture instead of the 3D figure

The page shows a still image instead of the live figure in these cases:
- on phones and tablets;
- when Windows' **Show animations** setting is off;
- on PCs without 3D graphics (some virtual desktops);
- on PCs too slow to animate it smoothly.

Everything else on the page works the same. On other PCs, a **Pause motion** button stops the animation.

## Changing the look

- **Shapes and still images:** the small person, the magnifying glass and the still images come from `blender/build_coalesce.py` (Blender 5.2 LTS).
- **Positions:** where the people stand comes from `blender/coalesce_layout.py`.
- **Colors and wording:** `public/css/site.css` and the two HTML files.

After editing either Blender file, rebuild:

```powershell
& "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" -b --factory-startup --python-exit-code 1 --python blender/build_coalesce.py -- --stills
```

That rewrites `public/assets/` and `blender/coalesce.blend` (open the `.blend` for hand edits).

## Checking a change

`tools/verify.py` takes screenshots of every state into `verify-output/` and checks the size and speed budgets. It needs the dev tools first:

```powershell
python -m pip install -r requirements-dev.txt
python -m playwright install chromium
python tools/verify.py
```

## Licenses

The site includes Three.js (MIT, `public/vendor/three/LICENSE`) and the Instrument Serif and Instrument Sans fonts (SIL Open Font License, `public/fonts/OFL.txt`), each with its license.
````

- [ ] **Step 4: Run the tests to see them pass**

Run: `.venv/Scripts/python -m pytest tests/test_package.py -q`
Expected: `3 passed`.

- [ ] **Step 5: Run the whole suite and build the zip**

Run:
```bash
.venv/Scripts/python -m pytest -q
.venv/Scripts/python tools/package.py
```
Expected:
- The suite passes.
- The packager prints `wrote dist/coalesce-site.zip (… MB)`, under 3 MB.

- [ ] **Step 6: Commit**

```bash
git add README.md .gitlab-ci.yml tools/package.py tests/test_package.py
git commit -q -F - <<'EOF'
docs: README, Pages job and the zip packager

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
EOF
```

---

## Spec coverage

| Spec section | Task(s) |
|---|---|
| §3 Hosting, look, motion, pipeline, download source, third-party code | 2, 4, 5, 6, 8–10, 12 |
| §4 Files | 1–13 |
| §5.1–5.3 Pages and copy | 6 |
| §5.4 Settings file and URL rules | 5 |
| §6.1 Blender authoring and self-check | 3, 4 |
| §6.2–6.3 Engine and Playful behavior (incl. Help idle and lens) | 8, 9, 10 |
| §6.4 Still-image rules and watchdog | 7, 10 |
| §6.5 Controls and accessibility | 6, 10 |
| §6.6 Budgets | 4, 11 |
| §7 Hosting, releases, delivery, local preview | 1, 12, 13 |
| §8 Testing and verification | 1–13 (tests), 11 (screenshots and metrics) |
| §9 Risks | 5 (missing links), 7/10 (weak GPUs), 12 (release script), 13 (README) |
