# WEAVE prototype

The home page and Help page for WEAVE, the Workforce Engagement, Actions & Visibility Environment: the planned web dashboard that grows out of the Coalesce Excel add-in. It is a work in progress, and every number on it is sample data.

The page is plain HTML, CSS and JavaScript in `public/`, with no build step. Its panel lists come from one file, `public/panels.js`. On desktop the hero is the live 3D quilt, hanging from its rod and swaying gently, with Pause and Unstitch buttons beside it: Unstitch (or a click on the quilt) lays its blocks out as a dashboard of tiles, and Sew it back (or a click on the background) sews it together again. Phones, reduced motion and any browser where the 3D scene can't run get a still picture of the quilt instead.

The Help page, `public/help/`, offers three ways to get help: report a problem, take the tutorial or read the docs. Its cards' links come from one file, `public/site-config.js` (see Help links). On desktop its hero is a live corner of the quilt coming apart: the loose threads sway, the pointer stirs them, and Pause stops the motion. Phones, reduced motion and any browser where the 3D scene can't run get a still picture instead (a placeholder for now). The mend, and a still captured from the scene, come with #19.

## Preview

From the repo root:

```
python tools/serve.py weave
```

Then open <http://127.0.0.1:8000/public/>; the Help page is at <http://127.0.0.1:8000/public/help/>. This preview serves WEAVE on its own, so the "Coalesce" link there goes nowhere; the whole-site preview in the root `README.md` has both prototypes.

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

To check the page's budgets (transfer size, time to the first live frame, frame times over five seconds of idle plus one unstitch and sew-back cycle, the sew-in with `?whatsnew`, and the still) and its hero states, run `verify.py` from the repo root with the venv active. It opens a visible browser, so the frame times use the real GPU; keep its windows in front until the run ends. `--headless` is only a smoke run, never evidence for the frame times. The report lands in `weave/verify-output/report.json`.

```
python weave/tools/verify.py
```

Then run the tests from inside `weave/`. This is the one command not run from the repo root:

```
cd weave
python -m pytest
```

The suite runs at a fixed instant before any release, so nothing is new. To run it in the release's news window, where #16's sew-in plays on a plain load, set `WEAVE_TEST_CLOCK` to `2026-10-10T09:00:00` for the run, then unset it. In PowerShell:

```
$env:WEAVE_TEST_CLOCK = "2026-10-10T09:00:00"
python -m pytest
Remove-Item Env:WEAVE_TEST_CLOCK
```

In cmd, where `set` with nothing after the `=` deletes the variable:

```
set WEAVE_TEST_CLOCK=2026-10-10T09:00:00
python -m pytest
set WEAVE_TEST_CLOCK=
```

In Git Bash, macOS or Linux, the prefix sets it for that one command only:

```
WEAVE_TEST_CLOCK=2026-10-10T09:00:00 python -m pytest
```

On a plain load the quilt plays a short intro before it settles, so a test that needs the settled quilt first calls `wait_for_quilt(page)` from `tests/helpers.py`, whose 15 s default covers going live, the intro and E2's sew-in with time to spare.

The tests drive headless Chromium with Playwright. The desktop hero tests need it to report WebGL and a mouse (hover). That is verified on Windows with the GPU flags in `tests/conftest.py`. Elsewhere, if the desktop hero tests fail, suspect those flags before the page code.

## The fixed test clock

The tests never depend on the calendar. `FIXED_INSTANT`, noon on 1 January 2000, is defined once, in `weave/tools/fixed_clock.py`, with `FIXED_DATE` worked out from it; no other file writes it. It is before every release, so no release's news window contains it. Every browser context the shared fixture makes (`make_page` in `tests/conftest.py`) has its clock pinned to it before its first page, so the page's `new Date()` reads that instant and `Date.now()` stands still.

A test that needs another moment passes `make_page(clock="2026-10-10T09:00:00")`, and one that needs the real clock passes `make_page(clock=None)`. Release tests always pin their own instant or use `?now=`. To run the whole suite at another moment (#16 runs it inside the sample release's window), set `WEAVE_TEST_CLOCK` to a full local date-time such as `2026-10-10T09:00:00`, or one with an offset, never a bare date: Playwright reads a bare date as UTC midnight, the evening before in EDT. A bad value, a bare date included, fails the run with a message naming the variable instead of falling back, and `make_page(clock=...)` refuses one the same way.

One clock times the page: animation advances on the `requestAnimationFrame` timestamp's dt, and timeouts and watchdogs use timers or `performance.now()`, so nothing on the page is timed by `Date`, which the pin stops. The pin replaces `requestAnimationFrame`, timers and `performance` with Playwright's fake timers. They keep running, but frames come on an emulated tick of about 16 ms with whole-millisecond timestamps, not the display's, `performance.now()` has its own origin, and the performance timeline is empty: no marks, no resource entries. So a fixture test never measures real frame pacing (that is `verify.py`'s job), and a test that reads the timeline (such as the first-live-frame mark) passes `clock=None` and adds `now=` to keep the release rules off the calendar.

The page has two test-only parameters for the release rules. `?now=YYYY-MM-DD` sets the day the rules see (an invalid value is ignored with a console warning, and today stays the local date), and `?whatsnew` shows the current release's panels as new whatever was seen before. A visit with either of them, or with `?pose=rest` (the capture and test pose), stores what it saw under `weave.lastSeenRelease.sim` instead of `weave.lastSeenRelease`, so a demo link never changes what a real visit sees.

A tool that loads `/weave/` outside the fixture (`verify.py`, `capture_still.py`, and any later one) never pins the browser clock, because the pin empties the performance timeline the tool measures with and fakes the frame loop it times; it opens every page with `now=` set to `FIXED_INSTANT`'s date, worked out from `fixed_clock.py`, and ignores `WEAVE_TEST_CLOCK`, so a value left set in a shell can never move a still or a budget run into a release window.

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

## Shipping a panel

Shipping a panel is an edit to `panels.js`, a preview and a fresh still. A visitor whose browser has not yet seen the release gets a "what's new" card listing it, and the panel's "New" tag stays in the list for the release's news window.

1. Make the panel live: give its entry `status: 'live'`, a `since` naming the release it arrives in, quoted as a string such as `'1.2'` (never the number `1.2`), a `sample` (`{ value, unit }`, or `null` for "No sample yet") and a `blurb`.
2. Bump the release: set `release.version` to that same version and `release.date` to the day it ships, written `YYYY-MM-DD`. The news window opens on that date and lasts `newsWindowDays`, so a bumped version left with the old date keeps the old window: only the days that remain of it, then nothing.
3. Preview it with `?now=YYYY-MM-DD` (a day inside the window) or `?whatsnew` (the current release's panels as new, whatever the day). Neither touches the real `weave.lastSeenRelease`, so your own next real visit still gets the card. A `?now=` preview writes `weave.lastSeenRelease.sim` instead, so a second one shows no card: use `?whatsnew`, or delete that key, to see it again. `?whatsnew` before `release.date` writes nothing.
4. Recapture the still with `capture_still.py` (see Stills), since the still stays stale, showing the panel pinned, until someone recaptures it. The capture opens the page with `now=` set to `FIXED_INSTANT`'s date and never pins the browser clock (as "The fixed test clock" says); that date is outside every news window, so the panel shows sewn in and nothing is written. E4's #23 later replaces this step with `build_assets.py --poster`.

## Stills

Phones, reduced motion and any browser where the 3D scene can't run show `public/assets/weave-still.jpg`, a 1600 x 1000 JPEG of the quilt at rest. It is captured from the live render, not drawn. To recapture it, run this from the repo root with the venv active, then commit the new file:

<!-- read by tests/test_docs.py::test_readme_commands_match_the_scripts: keep flags in sync with --help -->
```
python weave/tools/capture_still.py
```

It opens the page at `?pose=rest&frame=still&now=…` in headless Chromium (the `now=` is `FIXED_INSTANT`'s date, as The fixed test clock says) and waits until the quilt is live and settled, the still has faded out and the frame watchdog has had time to rule. Then it saves the JPEG at the first quality, from 90 down to 60, whose file fits 250 KB. If the scene falls back to the still, or no quality fits, it writes nothing and exits 1. `--which home|help|all` picks the target: today only `home` (this page) is registered, and `help` arrives with #19, which captures the Help page's still, so until then `--which help` exits 2 and names it. The default, `all`, captures every registered target. `--out DIR` and `--query K=V` are for tests: they write somewhere else and add to the page's query.

The still is a snapshot, so it goes stale whenever `panels.js` or the scene changes, and stays stale until someone recaptures it. Every command in this section and the next runs from the repo root.

## Budgets

The page has five bars, checked on the owner's dev laptop:

- transfer: at most 1.5 MB for the home page, headers included;
- time to the first live frame: at most 4 s;
- frame times over 5 s of idle plus one unstitch and sew-back cycle: a median of at most 16.7 ms (or the empty page's median plus 1 ms, on a display slower than 60 Hz) and a p95 of at most 33 ms;
- frame times over the sew-in, on a load with `?whatsnew` and `now=` at the fixed date, so nothing is written: the same median and p95 (`sew_frame_median_ms`, `sew_frame_p95_ms`);
- the still: at most 250 KB, at 1600 x 1000.

The sew-in's longest frame, `sew_frame_max_ms`, is recorded but not budgeted. `verify.py` measures the sample's two new blocks; a sew-in of 6 to 12 new blocks, where the schedule compresses to 5 s, is unmeasured (#38).

The full run is the `verify.py` command under Tests, in a visible browser on the owner's dev laptop; keep its windows in front until the run ends. After the budgets it checks every hero state (the quilt, the full page and its labels, hover, tiles, a reorder, the sew-back, Pause, the three still fallbacks and the phone) and screenshots each into `weave/verify-output/shots/`. The report is `weave/verify-output/report.json`, stamped with the commit of the checkout it ran from. Each run also keeps its own report and shots under `weave/verify-output/runs/`, in a folder named for the kind of run (local or `--base`, with `-headless` for a smoke run) and that commit, so a run at another commit leaves them alone and a headless smoke run never replaces the headed evidence; a second run of the same kind at the same commit replaces its folder. `report.json` records `headless`.

For how much room is left under the transfer bar, `weave/verify-output/report.json`'s measured `headroom_bytes` (1.5 MB less the measured transfer) is the figure to trust. "Headers included" means Chromium's Resource Timing `transferSize`, which counts headers as 300 B per response, not their real size.

To check the deployed copy, run the states alone against it:

<!-- read by tests/test_docs.py::test_readme_commands_match_the_scripts: keep flags in sync with --help -->
```
python weave/tools/verify.py --base https://mtibbits.github.io/weave-prototypes/weave/
```

That run checks and screenshots the states only. Its stamp names your checkout, not what Pages serves, so pull `main` and let the Pages deploy finish first. The budgets stay local, because Pages compresses the files and the first live frame would include the download.

## Help links

The Help page's three cards and the footer's team name come from `public/site-config.js` alone; nothing else needs editing. It sets `window.WEAVE_SITE`:

- `teamName`: the name in the footer's "maintained by ..." line. Empty shows "the WEAVE team".
- `links.serviceDesk`: the "Report a problem" card, the service desk portal.
- `links.tutorial`: the "Take the tutorial" card, the guided tutorial.
- `links.docs`: the "Read the docs" card, the usage docs.

A link must start with `https://`, `http://`, `mailto:`, `/`, `./` or `../` (after trimming spaces, in any letter case). Anything else, or an empty value, is dropped, and its card shows "Link coming soon" and is not a link. A `site-config.js` that is missing or doesn't parse leaves every card on "Link coming soon" and the footer on "the WEAVE team".

This repo and its GitHub Pages site are public, so commit public URLs only and never an internal hostname or intranet link; until a public link exists, leave the value empty. The tests never read the committed values: the Help page's tests serve their own settings in place of the file, and the two that touch the committed file check only its comments and its shape.

## Licenses

Three.js is MIT licensed (`public/vendor/three/LICENSE`). The Instrument fonts are under the SIL Open Font License (`public/fonts/OFL.txt`).
