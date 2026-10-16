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

To check the page's budgets (transfer size, time to the first live frame, frame times over five seconds of idle plus one unstitch and sew-back cycle, and the still) and its hero states, run `verify.py` from the repo root with the venv active. It opens a visible browser, so the frame times use the real GPU; keep its windows in front until the run ends. `--headless` is only a smoke run, never evidence for the frame times. The report lands in `weave/verify-output/report.json`.

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

## Editing `panels.js`

`public/panels.js` is the one file to edit to change the panels the page lists and the quilt draws. Each entry in its `panels` list has:

- `id` and `name`: non-empty strings, and no two entries share an `id`;
- `status`: `'live'` (sewn into the quilt, with a figure in the list), `'planned'` (pinned for later) or `'suggest'` (the "Suggest a panel" block);
- `sample`: `{ value, unit }` or `null`, where `value` is a number or a non-blank string and `unit` is a string (it can be `''`). A live panel shows it in the list with "(sample)" after it, and a live panel whose `sample` is `null` reads "No sample yet". A live panel's missing or malformed `sample` is read as `null`, and the console warns that it reads "No sample yet"; planned panels never warn;
- `since`: the release the panel arrived in, as a string such as `'1.1'`, never a number;
- `blurb`, `icon` and `fabric`: the line under the panel's name in the list, and the block's drawn icon and cloth.

The file ships 12 placeholder panels, a stand-in launch set rather than a decision.

An entry the page can't use is skipped, and the console warns, naming the entry's number: one that is not an object, has an empty `id` or `name`, has a `status` other than the three above, or repeats an earlier `id` (the first one is kept). If the file itself is broken (a syntax error, or no `panels` list), the list shows "The panel list couldn't be loaded." and the console error names `panels.js`. The quilt has 12 blocks: with more than 12 valid entries it draws the first 12 and warns, and with fewer, filler blocks pad it out.

Editing `panels.js` alone changes everything on the page except the still, which keeps showing the old quilt until someone recaptures it (see Stills).

## Stills

Phones, reduced motion and any browser where the 3D scene can't run show `public/assets/weave-still.jpg`, a 1600 x 1000 JPEG of the quilt at rest. It is captured from the live render, not drawn. To recapture it, run this from the repo root with the venv active, then commit the new file:

<!-- read by tests/test_docs.py::test_readme_commands_match_the_scripts: keep flags in sync with --help -->
```
python weave/tools/capture_still.py
```

It opens the page at `?pose=rest&frame=still` in headless Chromium and waits until the quilt is live and settled, the still has faded out and the frame watchdog has had time to rule. Then it saves the JPEG at the first quality, from 90 down to 60, whose file fits 250 KB. If the scene falls back to the still, or no quality fits, it writes nothing and exits 1. `--which home|help|all` picks the target: today only `home` (this page) is registered, and `help` arrives with the Help page, so until then `--which help` exits 2 and names it. The default, `all`, captures every registered target. `--out DIR` and `--query K=V` are for tests: they write somewhere else and add to the page's query.

The still is a snapshot, so it goes stale whenever `panels.js` or the scene changes, and stays stale until someone recaptures it. Every command in this section and the next runs from the repo root.

## Budgets

The page has four bars, checked on the owner's dev laptop:

- transfer: at most 1.5 MB for the home page, headers included;
- time to the first live frame: at most 4 s;
- frame times over 5 s of idle plus one unstitch and sew-back cycle: a median of at most 16.7 ms (or the empty page's median plus 1 ms, on a display slower than 60 Hz) and a p95 of at most 33 ms;
- the still: at most 250 KB, at 1600 x 1000.

The full run is the `verify.py` command under Tests, in a visible browser on the owner's dev laptop; keep its windows in front until the run ends. After the budgets it checks every hero state (the quilt, the full page and its labels, hover, tiles, a reorder, the sew-back, Pause, the three still fallbacks and the phone) and screenshots each into `weave/verify-output/shots/`. The report is `weave/verify-output/report.json`, stamped with the commit of the checkout it ran from. Each run also keeps its own report and shots under `weave/verify-output/runs/`, in a folder named for the kind of run (local or `--base`, with `-headless` for a smoke run) and that commit, so a run at another commit leaves them alone and a headless smoke run never replaces the headed evidence; a second run of the same kind at the same commit replaces its folder. `report.json` records `headless`.

For how much room is left under the transfer bar, `weave/verify-output/report.json`'s measured `headroom_bytes` (1.5 MB less the measured transfer) is the figure to trust. "Headers included" means Chromium's Resource Timing `transferSize`, which counts headers as 300 B per response, not their real size.

To check the deployed copy, run the states alone against it:

<!-- read by tests/test_docs.py::test_readme_commands_match_the_scripts: keep flags in sync with --help -->
```
python weave/tools/verify.py --base https://mtibbits.github.io/weave-prototypes/weave/
```

That run checks and screenshots the states only. Its stamp names your checkout, not what Pages serves, so pull `main` and let the Pages deploy finish first. The budgets stay local, because Pages compresses the files and the first live frame would include the download.

## Licenses

Three.js is MIT licensed (`public/vendor/three/LICENSE`). The Instrument fonts are under the SIL Open Font License (`public/fonts/OFL.txt`).
