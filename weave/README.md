# WEAVE home page

The home page for WEAVE, the Workforce Engagement, Actions & Visibility Environment: the planned web dashboard that grows out of the Coalesce Excel add-in. It is a work in progress, and every number on it is sample data.

The page is plain HTML, CSS and JavaScript in `public/`, with no build step. Its panel lists come from one file, `public/panels.js`. On desktop the hero is the live 3D quilt, hanging from its rod and swaying gently, with Pause and Unstitch buttons beside it: Unstitch (or a click on the quilt) lays its blocks out as a dashboard of tiles, and Sew it back (or a click on the background) sews it together again. Phones, reduced motion and any browser where the 3D scene can't run get a still picture of the quilt instead.

## Preview

From the repo root:

```
python tools/serve.py weave
```

Then open <http://127.0.0.1:8000/public/>. This preview serves WEAVE on its own, so the "Coalesce" link there goes nowhere; the whole-site preview in the root `README.md` has both prototypes.

The faces review page is at <http://127.0.0.1:8000/dev/faces.html> from the same command; it paints every block, tile and texture, and is never published. If port 8000 is taken, add `--port 8017` and use that port.

## Tests

From the repo root, make a virtual environment and activate it first, so the install doesn't change your global `pytest`:

```
python -m venv .venv
```

Activate it with the line for your shell. In PowerShell or cmd:

```
.venv\Scripts\activate
```

If PowerShell answers that running scripts is disabled (the stock Windows policy), allow scripts for this window only, then run the activate line again:

```
Set-ExecutionPolicy -Scope Process Bypass
```

If a group policy blocks that too, use cmd, where the same activate line works. Check that your prompt now starts with `(.venv)` before installing anything.

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

To check the page's budgets (transfer size, time to the first live frame, frame times over five seconds of idle plus one unstitch and sew-back cycle, and the still) and its hero states, run `verify.py` from the repo root with the venv active. It opens a visible browser, so the frame times use the real GPU; keep that window in front until it closes. `--headless` is only a smoke run, never evidence for the frame times. The report lands in `weave/verify-output/report.json`.

```
python weave/tools/verify.py
```

Then run the tests from inside `weave/`. This is the one command not run from the repo root:

```
cd weave
python -m pytest
```

On a plain load the quilt plays a short intro before it settles, so a test that needs the settled quilt first calls `wait_for_quilt(page)` from `tests/helpers.py`, whose 15 s default covers going live, the intro and E2's sew-in with time to spare.

The tests drive headless Chromium with Playwright. The desktop hero tests need it to report WebGL and a mouse (hover). That is verified on Windows with the GPU flags in `tests/conftest.py`. Elsewhere, if the desktop hero tests fail, suspect those flags before the page code.

## Licenses

Three.js is MIT licensed (`public/vendor/three/LICENSE`). The Instrument fonts are under the SIL Open Font License (`public/fonts/OFL.txt`).
