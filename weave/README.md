# WEAVE home page

The home page for WEAVE, the Workforce Engagement, Actions & Visibility Environment: the planned web dashboard that grows out of the Coalesce Excel add-in. It is a work in progress, and every number on it is sample data.

The page is plain HTML, CSS and JavaScript in `public/`, with no build step. Its panel lists come from one file, `public/panels.js`. The hero shows a still picture of the quilt for now; the 3D quilt is being built.

## Preview

From the repo root:

```
python tools/serve.py weave
```

Then open <http://127.0.0.1:8000/public/>. This preview serves WEAVE on its own, so the "Coalesce" link there goes nowhere; the whole-site preview in the root `README.md` has both prototypes.

## Tests

From the repo root, make a virtual environment and activate it first, so the install doesn't change your global `pytest`:

```
python -m venv .venv
```

Activate it with the line for your shell. In PowerShell or cmd:

```
.venv\Scripts\activate
```

In Git Bash:

```
source .venv/Scripts/activate
```

On macOS or Linux:

```
source .venv/bin/activate
```

Then install the test tools:

```
python -m pip install -r weave/requirements-dev.txt
python -m playwright install chromium
```

Then run the tests from inside `weave/`. This is the one command not run from the repo root:

```
cd weave
python -m pytest
```

The tests drive headless Chromium with Playwright. The desktop hero tests need it to report WebGL and a mouse (hover). That is verified on Windows with the GPU flags in `tests/conftest.py`; on other machines, check `test_hero.py`'s desktop test before trusting a green run.

## Licenses

Three.js is MIT licensed (`public/vendor/three/LICENSE`). The Instrument fonts are under the SIL Open Font License (`public/fonts/OFL.txt`).
