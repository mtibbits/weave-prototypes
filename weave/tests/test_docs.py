"""The READMEs carry the commands a reader needs, each in the section where it belongs."""
import re
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
