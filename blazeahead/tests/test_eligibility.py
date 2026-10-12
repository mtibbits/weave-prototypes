import json

import pytest

OK_ENV = {"webgl": True, "reducedMotion": False, "canHover": True, "saveData": False}


def decide(js, env):
    return js(f"const m = await import('/public/js/eligibility.js'); return m.decideMode({json.dumps(env)});")


def watchdog(js, frames, **options):
    return js(f"""
        const m = await import('/public/js/eligibility.js');
        const dog = new m.FrameWatchdog({json.dumps(options)});
        return {json.dumps(frames)}.map((f) => dog.add(f));
    """)


@pytest.mark.parametrize("override, reason", [
    ({}, "ok"),
    ({"webgl": False}, "no-webgl"),
    ({"reducedMotion": True}, "reduced-motion"),
    ({"canHover": False}, "no-hover"),
    ({"saveData": True}, "save-data"),
    ({"webgl": False, "reducedMotion": True}, "no-webgl"),
])
def test_decide_mode(js, override, reason):
    result = decide(js, {**OK_ENV, **override})
    assert result == {"live": reason == "ok", "reason": reason}


def test_watchdog_passes_smooth_animation(js):
    verdicts = watchdog(js, [16.7] * 130)
    assert verdicts[0] == "pending" and verdicts.index("ok") == 119


def test_watchdog_fails_slow_animation(js):
    verdicts = watchdog(js, [60] * 40)
    assert verdicts.index("too-slow") == 33 and verdicts[-1] == "too-slow"


def test_watchdog_ignores_one_long_hitch(js):
    assert watchdog(js, [900] + [16] * 80)[-1] == "ok"


def test_watchdog_verdict_is_final(js):
    assert watchdog(js, [60] * 40 + [5] * 200)[-1] == "too-slow"


def test_read_environment_in_desktop_chromium(js):
    env = js("const m = await import('/public/js/eligibility.js'); return m.readEnvironment(window);")
    assert env == OK_ENV
