"""#12's release rules (release.js), their boot wiring (stage.__weaveRelease), and the fixed test clock."""
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest

import conftest
import fixed_clock
from conftest import FIXED_DATE, FIXED_INSTANT

WEAVE = Path(__file__).resolve().parents[1]


# --- The clock: one instant, one home (D11). ---


def test_fixed_instant_is_noon_on_2000_01_01():
    assert datetime.fromisoformat(FIXED_INSTANT) == datetime(2000, 1, 1, 12, 0, 0)
    assert FIXED_DATE == datetime.fromisoformat(FIXED_INSTANT).date().isoformat()


def weave_files():
    """Every file git would ship under weave/ (tracked, plus untracked files that are not ignored), as paths."""
    out = subprocess.run(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"], cwd=WEAVE,
                         capture_output=True, check=True).stdout
    return sorted({name for name in out.decode("utf-8").split("\0") if name and (WEAVE / name).is_file()})


def test_fixed_instant_has_one_home():
    """The literal is written only in tools/fixed_clock.py; the planted positive is that module itself."""
    needle = FIXED_INSTANT.encode("ascii")
    hits = [name for name in weave_files() if needle in (WEAVE / name).read_bytes()]
    assert hits == ["tools/fixed_clock.py"], hits
    assert conftest.FIXED_INSTANT is fixed_clock.FIXED_INSTANT
    assert "from fixed_clock import FIXED_DATE, FIXED_INSTANT" in (WEAVE / "tests" / "conftest.py").read_text(
        encoding="utf-8")


# --- The default clock and its opt-outs. ---

GOOD_INSTANTS = ["2026-10-10T09:00:00", "2026-10-10T09:00", "2026-10-08T21:00:00-04:00", "2026-10-10T09:00:00Z",
                 "2026-10-10T09:00:00.250"]
BAD_INSTANTS = ["soon", "2026-10-09", "2026-10-09T09", "2026-02-30T09:00:00", "20261010T090000", "2026-10-10 09:00:00",
                "", 1234]


@pytest.mark.parametrize("value", GOOD_INSTANTS)
def test_check_instant_accepts_a_full_date_time(value):
    assert conftest.check_instant(value, "make_page(clock=...)") == value


def test_check_instant_accepts_the_fixed_instant():
    assert conftest.check_instant(FIXED_INSTANT, "make_page(clock=...)") == FIXED_INSTANT


@pytest.mark.parametrize("value", BAD_INSTANTS)
def test_check_instant_rejects_anything_else(value):
    with pytest.raises(ValueError, match=r"^make_page\(clock=\.\.\.\) must be a full local date-time"):
        conftest.check_instant(value, "make_page(clock=...)")


def test_resolve_default_clock_takes_the_environment_as_an_argument():
    assert conftest.resolve_default_clock({}) == FIXED_INSTANT
    assert conftest.resolve_default_clock({conftest.CLOCK_ENV: "2026-10-10T09:00:00"}) == "2026-10-10T09:00:00"
    for value in ("soon", "2026-10-09", ""):
        with pytest.raises(ValueError, match=r"^WEAVE_TEST_CLOCK must"):
            conftest.resolve_default_clock({conftest.CLOCK_ENV: value})


# rAF timestamps over `n` frames, and performance.now() across a 300 ms timer, on the page.
FRAMES_AND_TIMER = """async (n) => {
  const stamps = [];
  await new Promise((resolve) => {
    const tick = (t) => { stamps.push(t); if (stamps.length < n) requestAnimationFrame(tick); else resolve(); };
    requestAnimationFrame(tick);
  });
  const before = performance.now();
  await new Promise((resolve) => setTimeout(resolve, 300));
  return { stamps, waited: performance.now() - before };
}"""


def test_default_clock_is_the_resolved_instant(make_page, base_url):
    page = make_page()
    page.goto(f"{base_url}/tests/blank.html")
    expected = page.evaluate("(s) => new Date(s).getTime()", conftest.DEFAULT_CLOCK)
    assert page.evaluate("() => Date.now()") == expected
    run = page.evaluate(FRAMES_AND_TIMER, 10)
    stamps = run["stamps"]
    assert len(stamps) >= 10 and all(b > a for a, b in zip(stamps, stamps[1:])), stamps
    assert run["waited"] >= 250, run
    assert page.evaluate("() => Date.now()") == expected


def test_make_page_takes_another_instant(make_page, base_url):
    page = make_page(clock="2026-10-20T09:00:00")
    page.goto(f"{base_url}/tests/blank.html")
    assert page.evaluate("() => new Date().getTime() === new Date('2026-10-20T09:00:00').getTime()") is True


def test_real_clock_opt_out_runs(make_page, base_url):
    page = make_page(clock=None)
    page.goto(f"{base_url}/tests/blank.html")
    advanced = page.evaluate("async () => { const a = Date.now(); await new Promise((r) => setTimeout(r, 200));"
                             " return Date.now() - a; }")
    assert advanced >= 150, advanced


def test_make_page_rejects_a_bare_date(make_page):
    with pytest.raises(ValueError, match=r"make_page\(clock=\.\.\.\)"):
        make_page(clock="2026-10-09")


def clean_env(**extra):
    env = {key: value for key, value in os.environ.items() if key != conftest.CLOCK_ENV}
    env.update(extra)
    return env


@pytest.mark.parametrize("value", ["soon", "2026-10-09"])
def test_clock_env_fails_the_run(value):
    result = subprocess.run([sys.executable, "-m", "pytest", "tests/test_docs.py::test_root_readme_points_to_weave",
                             "-q", "-p", "no:cacheprovider"], cwd=WEAVE, capture_output=True, text=True,
                            env=clean_env(**{conftest.CLOCK_ENV: value}), timeout=120)
    assert result.returncode == 4, (result.returncode, result.stdout, result.stderr)
    assert conftest.CLOCK_ENV in result.stderr and repr(value) in result.stderr, result.stderr


def test_clock_env_replaces_the_default_for_a_run():
    """The positive control for test_clock_env_fails_the_run: the same harness, a good value, rc 0."""
    result = subprocess.run([sys.executable, "-m", "pytest",
                             "tests/test_release.py::test_default_clock_is_the_resolved_instant", "-q", "-p",
                             "no:cacheprovider"], cwd=WEAVE, capture_output=True, text=True,
                            env=clean_env(**{conftest.CLOCK_ENV: "2026-10-10T09:00:00"}), timeout=180)
    assert result.returncode == 0, (result.returncode, result.stdout, result.stderr)
    assert "1 passed" in result.stdout, result.stdout
