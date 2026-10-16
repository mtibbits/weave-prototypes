"""weave/tools/verify.py: the budgets, the state checks and their shots, the pure check() over a report, --base, and
where the script finds and writes its files."""
import ast
import importlib.util
import json
import struct
import subprocess
import sys
from pathlib import Path

import pytest

import conftest
import helpers
from conftest import GPU_ARGS

WEAVE = Path(__file__).resolve().parents[1]
REPO = WEAVE.parent
SCRIPT = WEAVE / "tools" / "verify.py"
SHARED = ("home_transfer_bytes", "still_bytes", "frame_median_ms", "frame_p95_ms")
# The contract's shot names (the PR and epic #1 cite them): a literal here, never read from verify.py.
STATE_SHOTS = {"quilt": "01-quilt.png", "hover": "02-hover.png", "tiles": "03-tiles.png", "reorder": "04-reorder.png",
               "sewn_back": "05-sewn-back.png", "paused": "06-paused.png", "still_no_webgl": "07-still-no-webgl.png",
               "still_reduced_motion": "08-still-reduced-motion.png", "still_watchdog": "09-still-watchdog.png",
               "phone": "10-phone.png", "full_page": "11-full-page.png"}
CHECKS = (*STATE_SHOTS, "labels")


@pytest.fixture
def verify():
    """verify.py loaded from its path, with sys.path restored afterwards (the script appends the root tools/)."""
    saved = list(sys.path)
    try:
        spec = importlib.util.spec_from_file_location("weave_verify", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        yield module
    finally:
        sys.path[:] = saved


def good_report():
    """A report that passes every row, built from the bars themselves."""
    return {
        "measures": {"baseline_frame_median_ms": 16.6, "home_transfer_bytes": 950_000, "first_live_frame_ms": 900.0,
                     "frame_median_ms": 16.7, "frame_p95_ms": 18.0, "still_bytes": 200_000, "still_size": [1600, 1000],
                     "cycle_frame_median_ms": 16.8, "cycle_frame_p95_ms": 20.0, "cycle_frame_max_ms": 40.0,
                     "headroom_bytes": 550_000},
        "states": {"desktop": ["live", "ok"], "desktop_after_idle": {"state": "live", "reason": "ok", "frames_rose": True},
                   "desktop_cycle": ["unstitching", "tiles", "restitching", "quilt"],
                   "reduced_motion": ["still", "reduced-motion"], "phone": ["still", "no-hover"],
                   "phone_no_horizontal_scroll": True},
        "checks": {name: {"ok": True, "detail": ""} for name in CHECKS},
        "shots": {name: f"shots/{file}" for name, file in STATE_SHOTS.items()},
    }


def coalesce_budgets():
    tree = ast.parse((REPO / "coalesce" / "tools" / "verify.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == "BUDGETS" for t in node.targets):
            return ast.literal_eval(node.value)
    raise AssertionError("no BUDGETS literal in coalesce/tools/verify.py")


def test_budgets_start_from_coalesces(verify):
    theirs = coalesce_budgets()
    assert {key: verify.BUDGETS[key] for key in SHARED} == {key: theirs[key] for key in SHARED}
    assert set(verify.BUDGETS) == {"home_transfer_bytes", "first_live_frame_ms", "frame_median_ms", "frame_p95_ms",
                                   "still_bytes"}
    assert verify.BUDGETS["first_live_frame_ms"] == 4000
    assert verify.STILL_SIZE == (1600, 1000)


def test_frame_budget_is_the_display_floor_or_baseline_plus_one(verify):
    assert verify.frame_budget(10) == 16.7
    assert verify.frame_budget(17.5) == 18.5


def test_budgets_for_takes_the_frame_median_from_the_baseline(verify):
    assert verify.budgets_for({}) == verify.BUDGETS
    budgets = verify.budgets_for({"baseline_frame_median_ms": 17.5})
    assert budgets == {**verify.BUDGETS, "frame_median_ms": 18.5}


def test_check_flags_each_failing_row(verify):
    assert verify.check(good_report()) == []
    for key, limit in verify.BUDGETS.items():
        report = good_report()
        bar = verify.frame_budget(report["measures"]["baseline_frame_median_ms"]) if key == "frame_median_ms" else limit
        report["measures"][key] = bar * 1.5 + 1
        failures = verify.check(report)
        assert len(failures) == 1 and key in failures[0], (key, failures)
    for key in [*verify.BUDGETS, "baseline_frame_median_ms", "still_size", *verify.CYCLE_MEASURES]:
        report = good_report()
        del report["measures"][key]
        assert any(key in failure for failure in verify.check(report)), key
    report = good_report()
    report["measures"]["still_size"] = [1599, 1000]
    assert any("still_size" in failure for failure in verify.check(report))
    report = good_report()
    report["states"]["desktop"] = ["still", "too-slow"]
    assert any("desktop" in failure for failure in verify.check(report))
    report = good_report()
    report["states"]["phone_no_horizontal_scroll"] = False
    assert any("phone" in failure for failure in verify.check(report))
    for idle in ({"state": "still", "reason": "too-slow", "frames_rose": False},
                 {"state": "live", "reason": "ok", "frames_rose": False}, None):
        report = good_report()
        report["states"]["desktop_after_idle"] = idle
        failures = verify.check(report)
        # w302: the hook outlives the teardown, so the frame rows count only on a quilt still live and running.
        assert any("frame_median_ms" in f for f in failures) and any("frame_p95_ms" in f for f in failures), idle
    for cycle in (["unstitching"], None):
        report = good_report()
        report["states"]["desktop_cycle"] = cycle
        failures = verify.check(report)
        # #8: the pooled window counts only if it really held one unstitch and sew-back cycle.
        assert any(f.startswith("frame_median_ms") for f in failures), cycle
        assert any(f.startswith("frame_p95_ms") for f in failures), cycle


def test_window_stats_pools_idle_and_cycle(verify):
    assert verify.window_stats([0, 10, 10, 10], [30, 30]) == ((10, 30), (30, 30, 30))
    # One long frame in the cycle (the first flip's compile) is under its p95 but is its max.
    assert verify.window_stats([0, 10], [10] * 30 + [90])[1] == (10, 10, 90)


def test_baseline_uses_the_plain_frame_loop(verify):
    """The empty page has no toggle, so its baseline must keep #7's plain loop, not the cycle window."""
    lines = [line for line in SCRIPT.read_text(encoding="utf-8").splitlines()
             if 'measures["baseline_frame_median_ms"]' in line and "=" in line.split('measures["baseline', 1)[1][:30]]
    assert len(lines) == 1 and "evaluate(FRAME_TIMES)" in lines[0], lines
    assert "data-toggle" not in verify.FRAME_TIMES
    assert "data-toggle" in verify.WINDOW_TIMES


def test_gpu_args_match_the_suites(verify):
    assert verify.GPU_ARGS == GPU_ARGS


def test_verify_waits_like_wait_for_quilt(verify):
    """#10: verify.py's windows open only once the intro has settled, on the tests' own predicate."""
    assert verify.QUILT_SETTLED == helpers.QUILT_SETTLED
    calls = []

    class FakePage:
        def wait_for_function(self, *args, **kwargs):
            calls.append((args, kwargs))

    verify.wait_settled(FakePage())
    assert len(calls) == 1 and calls[0][0][0] == helpers.QUILT_SETTLED, calls


def test_paths_resolve_from_the_scripts_location(verify):
    assert verify.PUBLIC == WEAVE / "public"
    assert verify.OUT == WEAVE / "verify-output"
    assert Path(verify.serve.__file__).resolve() == REPO / "tools" / "serve.py"
    text = SCRIPT.read_text(encoding="utf-8")
    # Appended, never inserted first, so the root tools/ can never shadow a module the caller already resolves.
    assert "sys.path.append(" in text and "sys.path.insert" not in text


def test_fixed_clock_ignores_the_environment(verify, monkeypatch):
    monkeypatch.setenv("WEAVE_TEST_CLOCK", "2026-01-01T00:00:00")
    fixed_clock = WEAVE / "tools" / "fixed_clock.py"
    if fixed_clock.is_file():
        spec = importlib.util.spec_from_file_location("fixed_clock_probe", fixed_clock)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        assert verify.fixed_instant() == module.FIXED_INSTANT
    else:
        assert verify.fixed_instant() is None


# --- #11: the state checks and their shots, --base, the run directory and the git stamp. ---


def test_state_shots_cover_every_listed_state(verify):
    assert verify.STATE_SHOTS == STATE_SHOTS
    assert verify.CHECKS == CHECKS


def test_check_flags_each_failing_state(verify):
    assert verify.check(good_report()) == []
    for name in CHECKS:
        report = good_report()
        report["checks"][name] = {"ok": False, "detail": "boom"}
        assert verify.check(report) == [f"{name}: boom"], name
        report = good_report()
        del report["checks"][name]
        assert verify.check(report) == [f"{name}: not run"], name
    for name in STATE_SHOTS:
        report = good_report()
        del report["shots"][name]
        assert verify.check(report) == [f"{name}: no screenshot"], name


def test_check_flags_a_missing_headroom(verify):
    report = good_report()
    del report["measures"]["headroom_bytes"]
    assert verify.check(report) == ["headroom_bytes: not run"]


def test_base_mode_checks_the_states_only(verify):
    good = good_report()
    base = {"base": "https://x/weave/", "checks": good["checks"], "shots": good["shots"]}
    assert verify.check(base) == []
    failing = json.loads(json.dumps(base))
    failing["checks"]["hover"] = {"ok": False, "detail": "no tooltip"}
    assert verify.check(failing) == ["hover: no tooltip"]
    # The control: the same report without base is a local run, so every budget row is missing.
    local = {key: value for key, value in base.items() if key != "base"}
    assert any(f.startswith("home_transfer_bytes") for f in verify.check(local)), verify.check(local)


def test_page_url_joins_a_sub_path(verify):
    assert verify.page_url("http://h:1") == "http://h:1/"
    assert verify.page_url("https://u/weave", "?q=0") == "https://u/weave/?q=0"
    assert verify.page_url("https://u/weave/", "?q=0") == "https://u/weave/?q=0"


@pytest.mark.parametrize("value", ["ftp://x", "weave/"])
def test_base_flag_takes_only_http_urls(verify, monkeypatch, capsys, value):
    def launched(*args, **kwargs):
        raise AssertionError("a browser started")

    monkeypatch.setattr(verify, "sync_playwright", launched)
    with pytest.raises(SystemExit) as exc:
        verify.main(["--base", value])
    assert exc.value.code == 2
    assert "--base" in capsys.readouterr().err


def test_base_flag_parses_an_https_url(verify):
    """The control for the rejections."""
    assert verify.build_parser().parse_args(["--base", "https://x/weave/"]).base == "https://x/weave/"


def test_run_dir_is_tagged_by_mode_and_sha(verify):
    out = verify.OUT
    clean = {"sha": "a" * 40, "dirty": False}
    assert verify.run_dir(out, None, clean) == out / "runs" / "local-aaaaaaa"
    assert verify.run_dir(out, "https://x/weave/", clean) == out / "runs" / "base-aaaaaaa"
    assert verify.run_dir(out, None, {"sha": "a" * 40, "dirty": True}) == out / "runs" / "local-aaaaaaa-dirty"
    assert verify.run_dir(out, None, {"sha": None, "dirty": None}) == out / "runs" / "local-nogit"


def test_git_stamp_reads_head(verify, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    head = subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"], capture_output=True, text=True,
                          check=True).stdout.strip()
    stamp = verify.git_stamp()
    assert stamp["sha"] == head and isinstance(stamp["dirty"], bool), stamp


def test_verify_js_never_hard_codes_public():
    """No string in verify.py names '/public/', so every page and module it opens resolves from the base it is given
    (a source walk, so a ported helper can't hide one)."""
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    strings = [node.value for node in ast.walk(tree) if isinstance(node, ast.Constant) and isinstance(node.value, str)]
    assert len(strings) > 20
    assert [s for s in strings if "/public/" in s] == []


def test_verify_shares_the_suites_seams_and_webgl_off(verify):
    assert verify.SEAMS_JS == helpers.SEAMS_JS
    assert verify.NO_WEBGL_ARGS == conftest.NO_WEBGL_ARGS
    assert "document.baseURI" in verify.SEAMS


class FakeServer:
    def shutdown(self):
        pass

    def server_close(self):
        pass


class FakeBrowser:
    def close(self):
        pass


class FakePlaywright:
    def __enter__(self):
        launcher = type("Launcher", (), {"launch": lambda self, **kwargs: FakeBrowser()})()
        return type("Pw", (), {"chromium": launcher})()

    def __exit__(self, *exc):
        return False


def test_report_is_written_when_a_run_throws(verify, monkeypatch, tmp_path):
    def throws(*args, **kwargs):
        raise RuntimeError("states blew up\nsecond line")

    monkeypatch.setattr(verify, "OUT", tmp_path)
    monkeypatch.setattr(verify, "sync_playwright", FakePlaywright)
    monkeypatch.setattr(verify.serve, "start", lambda directory: (FakeServer(), "http://127.0.0.1:1"))
    monkeypatch.setattr(verify, "run", lambda report, base, headless: None)
    monkeypatch.setattr(verify, "run_states", throws)
    assert verify.main(["--headless"]) == 1
    runs = list((tmp_path / "runs").iterdir())
    assert len(runs) == 1 and runs[0].name.startswith("local-"), runs
    for path in (runs[0] / "report.json", tmp_path / "report.json"):
        report = json.loads(path.read_text(encoding="utf-8"))
        assert "git" in report and "verify.py stopped: states blew up" in report["failures"], report["failures"]


def png_size(path):
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n", path
    return struct.unpack(">II", data[16:24])


@pytest.fixture(scope="module")
def repo_url():
    """The repo root served at /, so the page sits at /weave/public/: a prefix other than the suite's /public/."""
    server, url = conftest.serve.start(REPO)
    yield url
    server.shutdown()
    server.server_close()


def test_state_checks_pass_on_a_subpath_base(verify, browser, browser_no_webgl, repo_url, tmp_path):
    checks, shots = verify.run_states(f"{repo_url}/weave/public/", tmp_path, browser, browser_no_webgl,
                                      query="?nowatchdog")
    failing = {name: entry["detail"] for name, entry in checks.items() if not entry["ok"]}
    assert sorted(checks) == sorted(CHECKS) and failing == {}, failing
    assert shots == {name: f"shots/{file}" for name, file in STATE_SHOTS.items()}
    for file in STATE_SHOTS.values():
        assert (tmp_path / file).read_bytes()[:8] == b"\x89PNG\r\n\x1a\n", file
    assert png_size(tmp_path / "11-full-page.png")[1] > 900
    assert png_size(tmp_path / "10-phone.png")[0] == 780


def test_still_shown_rejects_a_live_stage(verify, make_page, base_url):
    """The planted control for still_shown: a live stage fails it, naming is-live."""
    page, _ = helpers.open_live(make_page, base_url)
    result = verify.still_shown(page)
    assert result["ok"] is False and "is-live" in result["detail"], result
