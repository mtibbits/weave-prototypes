"""weave/tools/verify.py: the budgets, the pure check() over a report, and where the script finds its files."""
import ast
import importlib.util
import sys
from pathlib import Path

import pytest

from conftest import GPU_ARGS

WEAVE = Path(__file__).resolve().parents[1]
REPO = WEAVE.parent
SCRIPT = WEAVE / "tools" / "verify.py"
SHARED = ("home_transfer_bytes", "still_bytes", "frame_median_ms", "frame_p95_ms")


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


def good_report(verify):
    """A report that passes every row, built from the bars themselves."""
    return {
        "measures": {"baseline_frame_median_ms": 16.6, "home_transfer_bytes": 950_000, "first_live_frame_ms": 900.0,
                     "frame_median_ms": 16.7, "frame_p95_ms": 18.0, "still_bytes": 200_000, "still_size": [1600, 1000]},
        "states": {"desktop": ["live", "ok"], "desktop_after_idle": {"state": "live", "reason": "ok", "frames_rose": True},
                   "reduced_motion": ["still", "reduced-motion"], "phone": ["still", "no-hover"],
                   "phone_no_horizontal_scroll": True},
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


def test_check_flags_each_failing_row(verify):
    assert verify.check(good_report(verify)) == []
    for key, limit in verify.BUDGETS.items():
        report = good_report(verify)
        bar = verify.frame_budget(report["measures"]["baseline_frame_median_ms"]) if key == "frame_median_ms" else limit
        report["measures"][key] = bar * 1.5 + 1
        failures = verify.check(report)
        assert len(failures) == 1 and key in failures[0], (key, failures)
    for key in [*verify.BUDGETS, "baseline_frame_median_ms", "still_size"]:
        report = good_report(verify)
        del report["measures"][key]
        assert any(key in failure for failure in verify.check(report)), key
    report = good_report(verify)
    report["measures"]["still_size"] = [1599, 1000]
    assert any("still_size" in failure for failure in verify.check(report))
    report = good_report(verify)
    report["states"]["desktop"] = ["still", "too-slow"]
    assert any("desktop" in failure for failure in verify.check(report))
    report = good_report(verify)
    report["states"]["phone_no_horizontal_scroll"] = False
    assert any("phone" in failure for failure in verify.check(report))
    for idle in ({"state": "still", "reason": "too-slow", "frames_rose": False},
                 {"state": "live", "reason": "ok", "frames_rose": False}, None):
        report = good_report(verify)
        report["states"]["desktop_after_idle"] = idle
        failures = verify.check(report)
        # w302: the hook outlives the teardown, so the frame rows count only on a quilt still live and running.
        assert any("frame_median_ms" in f for f in failures) and any("frame_p95_ms" in f for f in failures), idle


def test_gpu_args_match_the_suites(verify):
    assert verify.GPU_ARGS == GPU_ARGS


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
