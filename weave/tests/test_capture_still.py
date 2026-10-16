"""weave/tools/capture_still.py: the target registry, the CLI, the quality ladder, the clock, and the capture itself."""
import hashlib
import importlib.util
import re
import subprocess
import sys
import time
from pathlib import Path

import pytest

import conftest
import helpers

WEAVE = Path(__file__).resolve().parents[1]
REPO = WEAVE.parent
SCRIPT = WEAVE / "tools" / "capture_still.py"
STILL = WEAVE / "public" / "assets" / "weave-still.jpg"


@pytest.fixture
def capture():
    """capture_still.py loaded from its path, with sys.path restored afterwards (verify.py appends the root tools/)."""
    saved = list(sys.path)
    try:
        spec = importlib.util.spec_from_file_location("weave_capture_still", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        yield module
    finally:
        sys.path[:] = saved


def run_script(*args, cwd, timeout=120):
    return subprocess.run([sys.executable, str(SCRIPT), *args], cwd=cwd, capture_output=True, text=True,
                          timeout=timeout)


def test_targets_are_home_only_until_19(capture):
    """An equality pin: #19's help registration must update it."""
    assert capture.TARGETS == {"home": ("/index.html", "weave-still.jpg")}
    assert capture.RECIPE == "pose=rest&frame=still"
    assert capture.DEFAULT_OUT == WEAVE / "public" / "assets"


def test_capture_shares_verifys_settings(capture):
    assert capture.verify.GPU_ARGS == conftest.GPU_ARGS
    assert capture.LIMIT == 250_000
    assert capture.verify.QUILT_SETTLED == helpers.QUILT_SETTLED
    assert capture.verify.SETTLE_AFTER_LIVE_MS == 2500


def test_target_url_appends_queries_after_the_recipe(capture):
    url = capture.target_url("http://h:1", "/index.html", ["watchdogLimitMs=0", "nowatchdog="])
    assert url == "http://h:1/index.html?pose=rest&frame=still&watchdogLimitMs=0&nowatchdog="
    assert capture.target_url("http://h:1", "/index.html", []) == "http://h:1/index.html?pose=rest&frame=still"


@pytest.mark.parametrize("value", ["x", "=1", "a=1&b=2", "a=b#c", "1a=2"])
def test_query_grammar_rejects_bad_pairs(capture, capsys, tmp_path, value):
    with pytest.raises(SystemExit) as exc:
        capture.main(["--query", value, "--out", str(tmp_path)])
    assert exc.value.code == 2
    assert "--query" in capsys.readouterr().err


def test_query_grammar_accepts_good_pairs(capture):
    """The control for the rejections: the parser alone takes a pair and a bare flag."""
    args = capture.build_parser().parse_args(["--query", "watchdogLimitMs=0", "--query", "nowatchdog="])
    assert args.query == ["watchdogLimitMs=0", "nowatchdog="]


def test_fit_steps_down_until_it_fits(capture):
    sizes = {90: 300_000, 85: 240_000, 80: 200_000}
    calls = []

    def shoot(q):
        calls.append(q)
        return b"x" * sizes[q]

    quality, data = capture.fit(shoot)
    assert (quality, len(data)) == (85, 240_000) and calls == [90, 85]
    with pytest.raises(capture.CaptureError) as exc:
        capture.fit(lambda q: b"x" * 260_000)
    assert "at quality 60" in str(exc.value) and "250,000" in str(exc.value)
    assert capture.fit(lambda q: b"x" * 250_000)[0] == 90


class FakeClock:
    def __init__(self):
        self.pinned = []

    def set_fixed_time(self, instant):
        self.pinned.append(instant)


class FakeBrowser:
    def __init__(self):
        self.kwargs = None
        self.clock = FakeClock()

    def new_context(self, **kwargs):
        self.kwargs = kwargs
        context = type("FakeContext", (), {})()
        context.clock = self.clock
        return context


def test_open_context_pins_the_recipe_and_the_clock(capture, monkeypatch):
    monkeypatch.setenv("WEAVE_TEST_CLOCK", "2030-01-01T00:00:00")
    sentinel = object()
    original = capture.verify.fixed_instant
    monkeypatch.setattr(capture.verify, "fixed_instant", lambda: sentinel)
    browser = FakeBrowser()
    capture.open_context(browser)
    assert browser.kwargs == {"viewport": capture.VIEWPORT, "device_scale_factor": 1}
    assert capture.VIEWPORT == {"width": 1600, "height": 1000}
    assert browser.clock.pinned == [sentinel]

    monkeypatch.setattr(capture.verify, "fixed_instant", lambda: None)
    browser = FakeBrowser()
    capture.open_context(browser)
    assert browser.clock.pinned == []

    # Unpatched: the same expectation as test_verify's test_fixed_clock_ignores_the_environment.
    monkeypatch.setattr(capture.verify, "fixed_instant", original)
    browser = FakeBrowser()
    capture.open_context(browser)
    fixed_clock = WEAVE / "tools" / "fixed_clock.py"
    if fixed_clock.is_file():
        spec = importlib.util.spec_from_file_location("fixed_clock_probe", fixed_clock)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        assert browser.clock.pinned == [module.FIXED_INSTANT]
    else:
        assert browser.clock.pinned == []


def test_capture_holds_no_date_literal():
    """A source grep on purpose: the AC (the clock rule lives in verify.fixed_instant alone) is a property of the text."""
    text = SCRIPT.read_text(encoding="utf-8")
    assert not re.search(r"(19|20)\d\d-[01]\d-[0-3]\d", text)
    assert "WEAVE_TEST_CLOCK" not in text


def test_which_help_names_the_missing_target(tmp_path):
    out = tmp_path / "o"
    start = time.monotonic()
    result = run_script("--which", "help", "--out", str(out), cwd=tmp_path)
    elapsed = time.monotonic() - start
    assert result.returncode == 2, (result.returncode, result.stderr)
    assert "no 'help' target is registered yet" in result.stderr and "registered: home" in result.stderr, result.stderr
    assert not out.exists()
    assert elapsed < 10, elapsed


# --- The capture (Task 2): headless Chromium on the suite's server; tests always pass --out or call capture(). ---


def tree_guard():
    """What a capture must never change: git's view of weave/public, and the committed still's bytes."""
    status = subprocess.run(["git", "status", "--porcelain", "--", "public"], cwd=WEAVE, capture_output=True,
                            text=True, check=True).stdout
    return status, hashlib.sha256(STILL.read_bytes()).hexdigest()


def test_capture_waits_for_live_fade_and_watchdog(capture, browser, base_url):
    data, quality, info = capture.capture(browser, f"{base_url}/public", "home", [])
    assert info["state"] == "live" and info["still_opacity"] == "0", info
    assert info["after_live_ms"] >= 2500 and info["frames_advanced"] > 0, info
    assert helpers.jpeg_size(data) == (1600, 1000)
    assert len(data) <= 250_000 and quality in capture.QUALITIES, (len(data), quality)


def test_capture_writes_only_under_out(tmp_path):
    before = tree_guard()
    out = tmp_path / "o"
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    result = run_script("--out", str(out), cwd=elsewhere)
    assert result.returncode == 0, (result.returncode, result.stderr)
    assert re.fullmatch(r"capture_still\.py: wrote .*weave-still\.jpg \(1600 x 1000, JPEG quality \d+, [\d,]+ B\)",
                        result.stdout.strip()), result.stdout
    assert sorted(p.name for p in out.iterdir()) == ["weave-still.jpg"]
    data = (out / "weave-still.jpg").read_bytes()
    assert helpers.jpeg_size(data) == (1600, 1000) and len(data) <= 250_000, len(data)
    assert tree_guard() == before


def test_forced_fallback_writes_nothing(tmp_path):
    """The positive control is test_capture_writes_only_under_out: the same harness, rc 0, one file."""
    before = tree_guard()
    out = tmp_path / "o"
    result = run_script("--query", "watchdogLimitMs=0", "--out", str(out), cwd=tmp_path)
    assert result.returncode == 1, (result.returncode, result.stderr)
    assert "home: the scene fell back to the still (too-slow); nothing written" in result.stderr, result.stderr
    assert not out.exists() or list(out.iterdir()) == []
    assert tree_guard() == before
