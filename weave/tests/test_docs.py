"""The READMEs carry the commands a reader needs, each in the section where it belongs."""
import re
import subprocess
import sys
from pathlib import Path

WEAVE = Path(__file__).resolve().parents[1]
REPO = WEAVE.parent


def section(path, heading):
    """The text under a `## heading` up to the next `## ` heading ('' when the section is missing)."""
    if not path.is_file():
        return ""
    match = re.search(rf"^## {re.escape(heading)}\s*$(.*?)(?=^## |\Z)", path.read_text(encoding="utf-8"), re.M | re.S)
    return match.group(1) if match else ""


def test_weave_readme_has_preview_and_tests():
    readme = WEAVE / "README.md"
    preview = section(readme, "Preview")
    assert "python tools/serve.py weave" in preview and "/public/" in preview
    tests = section(readme, "Tests")
    for command in ("python -m venv .venv", "python -m pip install -r weave/requirements-dev.txt",
                    "python -m playwright install chromium", "cd weave", "python -m pytest"):
        assert command in tests, command
    # The desktop hero tests need headless Chromium to report WebGL and hover.
    assert "WebGL" in tests and "hover" in tests


def test_root_readme_points_to_weave():
    readme = REPO / "README.md"
    assert "weave/README.md" in section(readme, "Tests")
    layout = re.search(r"```(.*?)```", section(readme, "Layout"), re.S).group(1)
    assert "weave/tests/" in layout and "weave/README.md" in layout


def test_every_tests_command_line_is_a_bare_command():
    """Each fenced line in Tests is one pasteable command per shell: no prose, and an activate line for each shell."""
    tests = section(WEAVE / "README.md", "Tests")
    lines = [line.strip() for fence in re.findall(r"```(.*?)```", tests, re.S) for line in fence.splitlines() if line.strip()]
    assert lines and not [line for line in lines if "(" in line or ";" in line], lines
    for activate in (r".venv\Scripts\activate", "source .venv/Scripts/activate", "source .venv/bin/activate"):
        assert activate in lines, activate
    # PowerShell refuses Activate.ps1 under the stock Restricted policy, and without the venv the install goes global.
    assert "Set-ExecutionPolicy -Scope Process Bypass" in lines, lines


def test_faces_page_says_how_to_open_it():
    html = (WEAVE / "dev" / "faces.html").read_text(encoding="utf-8")
    body = re.sub(r"<script.*?</script>", "", re.search(r"<body>(.*)</body>", html, re.S).group(1), flags=re.S)
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body))
    for phrase in ("repo root", "python tools/serve.py weave", "/dev/faces.html"):
        assert phrase in text, phrase


def test_weave_readme_preview_names_the_faces_page():
    preview = section(WEAVE / "README.md", "Preview")
    assert "/dev/faces.html" in preview and "--port" in preview


def test_root_readme_layout_lists_weave_dev():
    layout = re.search(r"```(.*?)```", section(REPO / "README.md", "Layout"), re.S).group(1)
    assert "weave/dev/" in layout


def test_weave_readme_tests_says_how_to_run_verify():
    tests = section(WEAVE / "README.md", "Tests")
    lines = [line.strip() for fence in re.findall(r"```(.*?)```", tests, re.S) for line in fence.splitlines()]
    assert "python weave/tools/verify.py" in lines
    for phrase in ("repo root", "visible", "browser", "--headless", "weave/verify-output/report.json",
                   "one unstitch and sew-back cycle"):
        assert phrase in tests, phrase
    # It comes before the pytest steps, which run from inside weave/.
    assert tests.index("python weave/tools/verify.py") < tests.index("cd weave")


def test_root_readme_layout_lists_weave_tools():
    layout = re.search(r"```(.*?)```", section(REPO / "README.md", "Layout"), re.S).group(1)
    assert "weave/tools/" in layout and "verify.py" in layout and "capture_still.py" in layout
    assert "fixed_clock.py" in layout


def test_spec_lists_the_mode_hooks():
    """#8's and #10's hooks ship on the public page, so the design spec's hook list names them (Issue-7's lesson)."""
    spec = (WEAVE / "docs" / "superpowers" / "specs" / "2026-10-09-weave-v0-design.md").read_text(encoding="utf-8")
    hooks = re.search(r"^### URL and page hooks\s*$(.*?)(?=^##)", spec, re.M | re.S).group(1)
    for phrase in ("data-mode", "weave:mode", "restitching", "fades()", "revealStitches", "setFace"):
        assert phrase in hooks, phrase
    # The claim, not one phrasing: the director's states sentence names all six (#16's sewing live), none reserved.
    states = re.search(r"director's state: ([^.]*)\.", " ".join(hooks.split()))
    assert states, "the hook list no longer names the director's states"
    for mode in ("intro", "sewing", "quilt", "unstitching", "tiles", "restitching"):
        assert f"`{mode}`" in states.group(1), (mode, states.group(1))
    assert "reserved" not in states.group(1), states.group(1)


def test_weave_readme_tests_describes_wait_for_quilt():
    """A plain load plays the intro, so the README tells a test writer to wait for the settled quilt, and how long."""
    prose = " ".join(re.sub(r"```.*?```", " ", section(WEAVE / "README.md", "Tests"), flags=re.S).split())
    sentences = re.split(r"(?<=[.!?])\s+", prose)
    assert any("wait_for_quilt" in s and "15 s" in s for s in sentences), sentences


def frame_comment(text, constant):
    """The run of // comment lines just above `export const <constant>` in a JS source ('' when there is none)."""
    lines = text.splitlines()
    at = next(i for i, line in enumerate(lines) if line.startswith(f"export const {constant} "))
    block = []
    for line in reversed(lines[:at]):
        if not line.startswith("//"):
            break
        block.insert(0, line)
    return "\n".join(block)


def frame_claims(text):
    """Whether the pin and dash frame comments state their claims (#20, #22 and #16 build on these frames)."""
    pin = frame_comment(text, "PIN_LENGTH")
    dash = frame_comment(text, "STITCH_DASH_LENGTH")
    return all(p in pin for p in ("tip", "+Y", "PIN_LENGTH")) and all(p in dash for p in ("+X", "seam", "no lift"))


def test_scene_js_documents_the_pin_and_dash_frames():
    text = (WEAVE / "public" / "js" / "scene.js").read_text(encoding="utf-8")
    assert frame_claims(text) is True
    # Planted control: the same source with the pin frame's comment trimmed fails the check.
    trimmed = text.replace(frame_comment(text, "PIN_LENGTH"), "// Pins.")
    assert frame_claims(trimmed) is False


# --- #11: the owner's sections (editing panels.js, stills, budgets), each command checked against its script. ---

EDITING = "Editing `panels.js`"
EDITOR_NOTE = "<!-- read by tests/test_docs.py::test_readme_commands_match_the_scripts: keep flags in sync with --help -->"


def sentences(text):
    prose = " ".join(re.sub(r"```.*?```", " ", text, flags=re.S).split())
    return re.split(r"(?<=[.!?])\s+", prose)


def fenced(text):
    return [line.strip() for fence in re.findall(r"```(.*?)```", text, re.S) for line in fence.splitlines() if line.strip()]


def test_weave_readme_has_the_owner_sections():
    readme = WEAVE / "README.md"
    text = readme.read_text(encoding="utf-8")
    headings = re.findall(r"^## (.+?)\s*$", text, re.M)
    at = {heading: i for i, heading in enumerate(headings)}
    assert at["Tests"] < at[EDITING] < at["Stills"] < at["Budgets"] < at["Licenses"], headings

    editing = section(readme, EDITING)
    for phrase in ("'live'", "'planned'", "'suggest'", "sample", "null", "since", "No sample yet", "skipped",
                   "The panel list couldn't be loaded.", "first 12", "filler"):
        assert phrase in editing, phrase
    assert any("still" in s and "recapture" in s for s in sentences(editing)), sentences(editing)

    stills = section(readme, "Stills")
    assert "python weave/tools/capture_still.py" in fenced(stills)
    for phrase in ("--which", "stale", "repo root", EDITOR_NOTE):
        assert phrase in stills, phrase

    budgets = section(readme, "Budgets")
    assert "python weave/tools/verify.py --base https://mtibbits.github.io/weave-prototypes/weave/" in fenced(budgets)
    for phrase in ("1.5 MB", "250 KB", "33 ms", "weave/verify-output/report.json", "headroom_bytes", "shots",
                   "runs/", EDITOR_NOTE):
        assert phrase in budgets, phrase
    assert "137 KB" not in budgets

    # Write each claim to the width of the code: run()'s budget windows open together, a run at the same commit replaces
    # its own folder, and a --base report's stamp names the local checkout, not what Pages serves.
    assert "one at a time" not in text and "never overwrites an earlier" not in budgets
    assert "checkout" in budgets and "pull" in budgets


def test_readme_commands_match_the_scripts():
    """Executed docs: every fenced `python weave/tools/...` line in Stills and Budgets names a real script, and each
    of its --flags appears in that script's --help."""
    readme = WEAVE / "README.md"
    lines = [line for heading in ("Stills", "Budgets") for line in fenced(section(readme, heading))
             if line.startswith("python weave/tools/")]
    assert len(lines) >= 2, lines
    for line in lines:
        script = REPO / line.split()[1]
        assert script.is_file(), line
        result = subprocess.run([sys.executable, str(script), "--help"], cwd=REPO, capture_output=True, text=True,
                                timeout=60)
        assert result.returncode == 0, (line, result.stderr)
        for flag in re.findall(r"(?<!\S)--[a-z][a-z-]*", line):
            assert flag in result.stdout, (line, flag)


def test_spec_names_the_capture_and_the_state_run():
    spec = (WEAVE / "docs" / "superpowers" / "specs" / "2026-10-09-weave-v0-design.md").read_text(encoding="utf-8")
    fallbacks = re.search(r"^## 9\..*?(?=^### URL)", spec, re.M | re.S).group(0)
    assert "capture_still.py" in fallbacks and "watchdog" in fallbacks
    testing = re.search(r"^## 10\..*?(?=^## 11\.)", spec, re.M | re.S).group(0)
    assert "--base" in testing
    tree = re.search(r"^## 3\..*?```(.*?)```", spec, re.M | re.S).group(1)
    assert "capture_still.py" in tree and "fixed_clock.py" in tree


# --- #12: the fixed test clock and the release hooks. ---

CLOCK = "The fixed test clock"


def test_weave_readme_has_the_fixed_clock_section():
    readme = WEAVE / "README.md"
    headings = re.findall(r"^## (.+?)\s*$", readme.read_text(encoding="utf-8"), re.M)
    assert CLOCK in headings and headings.index("Tests") < headings.index(CLOCK) < headings.index(EDITING), headings
    clock = section(readme, CLOCK)
    for phrase in ("FIXED_INSTANT", "weave/tools/fixed_clock.py", "?now=YYYY-MM-DD", "?whatsnew",
                   "weave.lastSeenRelease.sim", "?pose=rest", "performance.now()"):
        assert phrase in clock, phrase
    said = sentences(clock)
    # The claims, each in one sentence: the variable and its format; the one-clock rule; the opt-out; the tool rule.
    assert any("WEAVE_TEST_CLOCK" in s and "bare date" in s for s in said), said
    assert any("requestAnimationFrame" in s and "Date" in s for s in said), said
    assert any(("clock=None" in s or "make_page(clock=" in s) and "None" in s for s in said), said
    assert any("tool" in s and "now=" in s and "WEAVE_TEST_CLOCK" in s for s in said), said


def test_spec_lists_the_release_hooks():
    spec = (WEAVE / "docs" / "superpowers" / "specs" / "2026-10-09-weave-v0-design.md").read_text(encoding="utf-8")
    hooks = re.search(r"^### URL and page hooks\s*$(.*?)(?=^##)", spec, re.M | re.S).group(1)
    for phrase in ("?now=", "?whatsnew", "__weaveRelease", "recordSeen", "weave.lastSeenRelease.sim"):
        assert phrase in hooks, phrase


# --- #15: shipping a panel, and the card's hooks. ---

SHIPPING = "Shipping a panel"
SPEC = WEAVE / "docs" / "superpowers" / "specs" / "2026-10-09-weave-v0-design.md"


def test_weave_readme_has_the_shipping_section():
    readme = WEAVE / "README.md"
    headings = re.findall(r"^## (.+?)\s*$", readme.read_text(encoding="utf-8"), re.M)
    assert SHIPPING in headings
    assert headings.index(EDITING) < headings.index(SHIPPING) < headings.index("Stills"), headings
    shipping = section(readme, SHIPPING)
    for phrase in ("status: 'live'", "since", "'1.2'", "sample", "blurb", "YYYY-MM-DD", "?now=", "?whatsnew",
                   "weave.lastSeenRelease", "capture_still.py", "FIXED_INSTANT", "build_assets.py --poster"):
        assert phrase in shipping, phrase
    said = sentences(shipping)
    assert any("version" in s and "date" in s and "window" in s for s in said), said
    assert any("stale" in s and ("recapture" in s or "capture_still.py" in s) for s in said), said


def test_spec_lists_the_card_hooks():
    spec = SPEC.read_text(encoding="utf-8")
    hooks = re.search(r"^### URL and page hooks\s*$(.*?)(?=^##)", spec, re.M | re.S).group(1)
    for phrase in ("data-release-state", "data-new-panels", "`none`", "`pending`", "`sewing`", "`card`", "`done`"):
        assert phrase in hooks, phrase
    assert any("weave:mode" in s and "quilt" in s and "card" in s for s in sentences(hooks)), sentences(hooks)
    release_hook = next(line for line in hooks.split("\n- ") if "stage.__weaveRelease" in line)
    assert "calls it when the card is seen" in " ".join(release_hook.split())
    logic = re.search(r"^## 7\..*?(?=^## 8\.)", spec, re.M | re.S).group(0)
    assert any("lastSeenRelease" in s and "card" in s and ("release.date" in s or "the window opens" in s)
               for s in sentences(logic)), sentences(logic)
    page = re.search(r"^## 8\..*?(?=^## 9\.)", spec, re.M | re.S).group(0)
    hero = re.search(r"\*\*Hero:\*\*(.*?)(?=^- \*\*)", page, re.M | re.S).group(1)
    assert "card" in hero, hero
    access = re.search(r"^## 9\..*?(?=^### URL)", spec, re.M | re.S).group(0)
    assert "aria-live" in access
    assert any("h1" in s and "tabindex" in s for s in sentences(access)), sentences(access)


# --- #16: the sew-in. ---

RESERVES_SEWING = re.compile(r"sewing.{0,40}reserved|reserves .{0,20}sewing|#16 adds .sewing")


def test_no_home_still_reserves_sewing():
    """#16 makes `sewing` live: no module, the spec or the README still calls it reserved or yet to come."""
    subjects = sorted((WEAVE / "public" / "js").glob("*.js")) + [SPEC, WEAVE / "README.md"]
    assert len(subjects) >= 16, subjects
    found = [f"{p.name}:{n}" for p in subjects
             for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1) if RESERVES_SEWING.search(line)]
    assert found == []


def test_no_home_still_reserves_sewing_catches_the_old_lines():
    """The planted control: the lines #16 replaced match the guard."""
    old = ["// #16 adds 'sewing' between pending and card.", "to `card`, and ... #16 adds `sewing` between `pending`",
           "`sewing` (#16) reserved. A plain load starts in `intro`"]
    assert [line for line in old if not RESERVES_SEWING.search(line)] == []


IN_WINDOW_FENCES = [
    ['$env:WEAVE_TEST_CLOCK = "2026-10-10T09:00:00"', "python -m pytest", "Remove-Item Env:WEAVE_TEST_CLOCK"],
    ["set WEAVE_TEST_CLOCK=2026-10-10T09:00:00", "python -m pytest", "set WEAVE_TEST_CLOCK="],
    ["WEAVE_TEST_CLOCK=2026-10-10T09:00:00 python -m pytest"],
]


def test_weave_readme_tests_covers_the_in_window_run():
    tests = section(WEAVE / "README.md", "Tests")
    assert "WEAVE_TEST_CLOCK" in tests and "2026-10-10T09:00:00" in tests
    # Split on the fence marks: odd parts are fences, each preceded by its prose, which names its shell.
    parts = tests.split("```")
    lines = [[line.strip() for line in part.splitlines() if line.strip()] for part in parts]
    clocked = [k for k in range(1, len(parts), 2) if any("WEAVE_TEST_CLOCK" in line for line in lines[k])]
    assert [lines[k] for k in clocked] == IN_WINDOW_FENCES, [lines[k] for k in clocked]
    for k, shell in zip(clocked, ("PowerShell", "cmd", "Git Bash")):
        assert shell in parts[k - 1], (shell, parts[k - 1])
    verify = next(s for s in sentences(tests) if "budgets" in s and "verify.py" in s)
    assert "?whatsnew" in verify and "sew-in" in verify, verify


def test_weave_readme_budgets_covers_the_sew_in_run():
    budgets = section(WEAVE / "README.md", "Budgets")
    assert "five bars" in budgets and "four bars" not in budgets
    for phrase in ("?whatsnew", "sew_frame_median_ms", "sew_frame_p95_ms", "sew_frame_max_ms"):
        assert phrase in budgets, phrase
    said = sentences(budgets)
    assert any("6" in s and "12" in s and "unmeasured" in s for s in said), said
