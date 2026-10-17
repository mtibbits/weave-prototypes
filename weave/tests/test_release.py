"""#12's release rules (release.js), their boot wiring (stage.__weaveRelease), and the fixed test clock."""
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest

import conftest
import fixed_clock
import helpers
from conftest import FIXED_DATE, FIXED_INSTANT
from helpers import DEFAULTS_JS, LAST_SEEN_KEY, SIM_KEY

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
    # The tools: verify.py loads the module, and capture_still.py takes the rule from verify.py alone.
    verify_text = (WEAVE / "tools" / "verify.py").read_text(encoding="utf-8")
    capture_text = (WEAVE / "tools" / "capture_still.py").read_text(encoding="utf-8")
    assert '"fixed_clock.py"' in verify_text and "FIXED_DATE" in verify_text
    assert "verify.NOW_QUERY" in capture_text and "fixed_clock" not in capture_text


# --- The default clock and its opt-outs. ---

GOOD_INSTANTS = ["2026-10-10T09:00:00", "2026-10-10T09:00", "2026-10-08T21:00:00-04:00", "2026-10-10T09:00:00Z",
                 "2026-10-10T09:00:00.250", FIXED_INSTANT]
BAD_INSTANTS = ["soon", "2026-10-09", "2026-10-09T09", "2026-02-30T09:00:00", "20261010T090000", "2026-10-10 09:00:00",
                "", 1234]


@pytest.mark.parametrize("value", GOOD_INSTANTS)
def test_check_instant_accepts_a_full_date_time(value):
    assert conftest.check_instant(value, "make_page(clock=...)") == value


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
    advanced = page.evaluate(helpers.CLOCK_ADVANCE)
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


# --- The pure rules (release.js), over the shipped panels.js through #5's cleanPanels. ---

# DEFAULTS is the shipped list through cleanPanels and RAW is window.WEAVE_PANELS; SAMPLE carries its settings.
PRELUDE = DEFAULTS_JS + r"""
    const R = await import('/public/js/release.js');
    const RAW = window.WEAVE_PANELS;
    const SAMPLE = { panels: DEFAULTS, release: RAW.release, windowDays: RAW.newsWindowDays };
    const withPanels = (over) => DEFAULTS.map((p) => (p.id in over ? { ...p, ...over[p.id] } : p));
    const sinceAll = (since) => DEFAULTS.map((p) => (p.status === 'live' ? { ...p, since } : p));
    const fakeStorage = (initial = {}) => {
      const data = { ...initial };
      const log = [];
      return { data, log, getItem: (k) => (k in data ? data[k] : null),
               setItem: (k, v) => { log.push([k, v]); data[k] = String(v); } };
    };
    const make = (over = {}) => {
      const warned = [];
      const storage = fakeStorage();
      const hook = R.createRelease({ now: null, whatsnew: false, rest: false, raw: RAW, panels: DEFAULTS,
                                     date: new Date(2026, 9, 10, 9), getStorage: () => storage,
                                     warn: (m) => warned.push(m), ...over });
      return { hook, warned, log: storage.log, data: storage.data };
    };
"""


@pytest.fixture(scope="module")
def js(browser, base_url):
    """conftest's js, one blank page for the whole module: the rules keep no state, and a context per case is waste."""
    contexts = []
    page = conftest.page_factory(browser, contexts)()
    page.goto(f"{base_url}/tests/blank.html")
    yield lambda body: page.evaluate(f"async () => {{ {body} }}")
    for ctx in contexts:
        ctx.close()


def run(js, body):
    return js(PRELUDE + body)


TRAVEL_DESKS = ["travel", "desks"]
LIVE_IDS = ["manpower", "hiring", "training", "awards", "travel", "actions", "desks"]
HOOK_KEYS = ["today", "force", "key", "lastSeen", "newIds", "taggedIds", "recordSeen"]


@pytest.mark.parametrize("a, b, expected", [
    ("1.10", "1.9", 1), ("1.1.0", "1.1", 0), ("1.0", "1.1", -1), ("2", "1.99", 1), ("01.1", "1.1", 0),
    ("1.1", "1.1.1", -1), ("1." + "9" * 25, "1." + "9" * 24 + "8", 1),
], ids=["1.10-1.9", "1.1.0-1.1", "1.0-1.1", "2-1.99", "01.1-1.1", "1.1-1.1.1", "25-digits"])
def test_compare_versions(js, a, b, expected):
    got = run(js, f"return [R.compareVersions({json.dumps(a)}, {json.dumps(b)}),"
                  f" R.compareVersions({json.dumps(b)}, {json.dumps(a)})];")
    assert got == [expected, -expected]


@pytest.mark.parametrize("value, expected", [
    ("1.10", True), (1.1, False), ("1.", False), ("", False), ("v1", False), (" 1.1", False), ("1..1", False),
    (None, False),
], ids=["1.10", "number", "trailing-dot", "empty", "v1", "space", "double-dot", "null"])
def test_is_version(js, value, expected):
    assert run(js, f"return R.isVersion({json.dumps(value)});") is expected


@pytest.mark.parametrize("value, expected", [
    ("2024-02-29", True), ("2026-02-29", False), ("2026-02-30", False), ("2026-10-9", False), ("2026-13-01", False),
    ("0099-01-01", False),
], ids=["leap", "not-leap", "feb-30", "unpadded", "month-13", "year-99"])
def test_is_date(js, value, expected):
    assert run(js, f"return R.isDate({json.dumps(value)});") is expected


def test_day_number_ignores_daylight_saving(js):
    pairs = [("2026-03-07", "2026-03-08"), ("2026-03-08", "2026-03-09"), ("2026-10-31", "2026-11-01"),
             ("2026-11-01", "2026-11-02")]
    got = run(js, f"return {json.dumps(pairs)}.map(([a, b]) => R.dayNumber(b) - R.dayNumber(a));")
    assert got == [1, 1, 1, 1]
    assert run(js, "return [undefined, null, 7].map((s) => Number.isNaN(R.dayNumber(s)));") == [True] * 3


def test_local_date_pads_the_local_calendar_day(js):
    got = run(js, "return [R.localDate(new Date(2026, 9, 8, 21)), R.localDate(new Date(2026, 0, 2, 0, 30))];")
    assert got == ["2026-10-08", "2026-01-02"]


def test_window_edges_with_the_sample_data(js):
    """AC1: 10-08 out, 10-09 in, 10-15 in, 10-16 out, for the new and the tagged sets alike."""
    days = ["2026-10-08", "2026-10-09", "2026-10-15", "2026-10-16"]
    got = run(js, f"""return {json.dumps(days)}.map((today) => [
        R.newPanelIds({{ ...SAMPLE, lastSeen: null, today, force: false }}),
        R.taggedPanelIds({{ ...SAMPLE, today }})]);""")
    assert got == [[[], []], [TRAVEL_DESKS, TRAVEL_DESKS], [TRAVEL_DESKS, TRAVEL_DESKS], [[], []]]


def test_window_days_bounds(js):
    got = run(js, """const at = (windowDays, today) => R.newPanelIds({ ...SAMPLE, windowDays, lastSeen: null, today });
        return [at(1, '2026-10-09'), at(1, '2026-10-10'), at(60, '2026-12-07'), at(60, '2026-12-08')];""")
    assert got == [TRAVEL_DESKS, [], TRAVEL_DESKS, []]


MALFORMED = {
    "date-unpadded": ("release", "{ ...RAW.release, date: '2026-10-9' }", "W_NEWS_DATE"),
    "date-impossible": ("release", "{ ...RAW.release, date: '2026-02-30' }", "W_NEWS_DATE"),
    "window-string": ("windowDays", "'7'", "W_NEWS_WINDOW"),
    "window-zero": ("windowDays", "0", "W_NEWS_WINDOW"),
    "window-61": ("windowDays", "61", "W_NEWS_WINDOW"),
    "window-fraction": ("windowDays", "7.5", "W_NEWS_WINDOW"),
    "version-number": ("release", "{ ...RAW.release, version: 1.1 }", "W_NEWS_VERSION"),
    "version-v": ("release", "{ ...RAW.release, version: 'v1.1' }", "W_NEWS_VERSION"),
}


@pytest.mark.parametrize("case", MALFORMED, ids=list(MALFORMED))
def test_malformed_release_settings_mean_nothing_new(js, case):
    """AC2 and AC11: nothing new even with force, no tags, recordSeen writes nothing, and that field's warning."""
    field, value, warning = MALFORMED[case]
    raw_field = "release" if field == "release" else "newsWindowDays"
    got = run(js, f"""const bad = {{ ...SAMPLE, {field}: {value} }};
        const visit = make({{ raw: {{ ...RAW, {raw_field}: {value} }}, now: '2026-10-20' }});
        return {{ plain: R.newPanelIds({{ ...bad, lastSeen: null, today: '2026-10-10', force: false }}),
                  forced: R.newPanelIds({{ ...bad, lastSeen: null, today: '2026-10-10', force: true }}),
                  tagged: R.taggedPanelIds({{ ...bad, today: '2026-10-10' }}),
                  hookNew: visit.hook.newIds, recorded: visit.hook.recordSeen(), log: visit.log,
                  warned: visit.warned }};""")
    assert got == {"plain": [], "forced": [], "tagged": [], "hookNew": [], "recorded": False, "log": [],
                   "warned": [getattr(helpers, warning)]}


def test_well_formed_settings_record_the_release(js):
    """The control for test_malformed_release_settings_mean_nothing_new: the sample records once, on the .sim key."""
    got = run(js, """const visit = make({ now: '2026-10-20' });
        return { recorded: visit.hook.recordSeen(), log: visit.log, warned: visit.warned };""")
    assert got == {"recorded": True, "log": [[SIM_KEY, "1.1"]], "warned": []}


FIRST = "{ panels: sinceAll('1.0'), release: { version: '1.0', date: '2026-10-09' }, windowDays: 7 }"


def test_first_release_gives_nothing_new(js):
    """AC5: a first release with no lastSeen gives nothing new and no tags."""
    got = run(js, f"""const first = {FIRST};
        return [R.newPanelIds({{ ...first, lastSeen: null, today: '2026-10-10' }}),
                R.taggedPanelIds({{ ...first, today: '2026-10-10' }})];""")
    assert got == [[], []]


def test_whatsnew_on_the_first_release_gives_every_launch_panel(js):
    got = run(js, f"""const first = {FIRST};
        return R.newPanelIds({{ ...first, lastSeen: null, today: '2026-10-10', force: true }});""")
    assert got == LIVE_IDS


def test_sample_release_gives_a_fresh_profile_travel_and_desks(js):
    got = run(js, "return [R.newPanelIds({ ...SAMPLE, lastSeen: null, today: '2026-10-10' }),"
                  " R.taggedPanelIds({ ...SAMPLE, today: '2026-10-10' })];")
    assert got == [TRAVEL_DESKS, TRAVEL_DESKS]


V12 = "{ version: '1.2', date: '2026-10-09', label: 'sample release' }"


def test_gap_with_promotions_in_1_2(js):
    """AC6: the sequence set, the tag set and the heading together."""
    got = run(js, f"""const panels = withPanels({{ promotions: {{ status: 'live', since: '1.2' }} }});
        const settings = {{ panels, release: {V12}, windowDays: 7 }};
        const newIds = R.newPanelIds({{ ...settings, lastSeen: '1.0', today: '2026-10-10' }});
        return {{ newIds, tagged: R.taggedPanelIds({{ ...settings, today: '2026-10-10' }}),
                  heading: R.cardHeading({{ panels, newIds, release: settings.release }}),
                  from11: R.newPanelIds({{ ...settings, lastSeen: '1.1', today: '2026-10-10' }}) }};""")
    assert got.pop("from11") == ["promotions"]
    assert got == {"newIds": ["promotions", "travel", "desks"], "tagged": ["promotions"],
                   "heading": {"kind": "since-last-visit", "text": "New since your last visit",
                               "groups": [{"version": "1.1", "names": ["Travel", "Desk Allocation"]},
                                          {"version": "1.2", "names": ["Promotions"]}]}}


def test_gap_when_1_2_ships_no_panels(js):
    got = run(js, f"""const settings = {{ panels: DEFAULTS, release: {V12}, windowDays: 7 }};
        const newIds = R.newPanelIds({{ ...settings, lastSeen: '1.0', today: '2026-10-10' }});
        return {{ newIds, tagged: R.taggedPanelIds({{ ...settings, today: '2026-10-10' }}),
                  heading: R.cardHeading({{ panels: DEFAULTS, newIds, release: settings.release }}) }};""")
    assert got == {"newIds": TRAVEL_DESKS, "tagged": [],
                   "heading": {"kind": "since-last-visit", "text": "New since your last visit",
                               "groups": [{"version": "1.1", "names": ["Travel", "Desk Allocation"]}]}}
    assert got["heading"]["text"] != "New this release · v1.2"


def test_planned_panel_is_never_new_or_tagged(js):
    """AC7: Promotions planned with since '1.1' is in neither set."""
    got = run(js, """const settings = { ...SAMPLE, panels: withPanels({ promotions: { since: '1.1' } }) };
        return [[false, null], [true, null], [false, '1.0'], [true, '1.0']].map(([force, lastSeen]) =>
          [R.newPanelIds({ ...settings, lastSeen, force, today: '2026-10-10' }),
           R.taggedPanelIds({ ...settings, today: '2026-10-10' })]);""")
    assert got == [[TRAVEL_DESKS, TRAVEL_DESKS]] * 4


def test_live_panel_without_a_usable_since_is_never_new_and_makes_a_later_release(js):
    """AC8: a first-release set plus one live panel with since missing, then 'soon'; only 'soon' warns."""
    got = run(js, f"""const first = {FIRST};
        return [undefined, 'soon'].map((since) => {{
          const odd = {{ id: 'odd', name: 'Odd', status: 'live', sample: null }};
          if (since !== undefined) odd.since = since;
          const settings = {{ ...first, panels: [...first.panels, odd] }};
          return [R.newPanelIds({{ ...settings, lastSeen: null, today: '2026-10-10' }}),
                  R.releaseWarnings(settings)];
        }});""")
    assert got == [[LIVE_IDS, []], [LIVE_IDS, [helpers.W_NEWS_SINCE.format(id="odd")]]]


def test_launch_set_written_as_numbers_warns_and_still_gives_travel_and_desks(js):
    got = run(js, """const panels = DEFAULTS.map((p) => (p.since === '1.0' ? { ...p, since: 1.0 } : p));
        const settings = { ...SAMPLE, panels };
        return [R.releaseWarnings(settings), R.newPanelIds({ ...settings, lastSeen: null, today: '2026-10-10' })];""")
    assert got == [[helpers.W_NEWS_SINCE.format(id=i) for i in ("manpower", "hiring", "training", "awards", "actions")],
                   TRAVEL_DESKS]


def test_since_written_as_a_number_warns_and_is_never_new(js):
    """AC9: since: 1.1 as a number warns naming the panel, which is never new."""
    got = run(js, """const settings = { ...SAMPLE, panels: withPanels({ travel: { since: 1.1 } }) };
        return [R.releaseWarnings(settings), R.newPanelIds({ ...settings, lastSeen: null, today: '2026-10-10' }),
                R.taggedPanelIds({ ...settings, today: '2026-10-10' })];""")
    assert got == [[helpers.W_NEWS_SINCE.format(id="travel")], ["desks"], ["desks"]]


def test_1_1_0_is_the_1_1_release(js):
    """AC10: since '1.1.0' under release '1.1' is new and tagged, with the "New this release" heading."""
    got = run(js, """const panels = withPanels({ desks: { since: '1.1.0' } });
        const settings = { ...SAMPLE, panels };
        const newIds = R.newPanelIds({ ...settings, lastSeen: null, today: '2026-10-10' });
        return { newIds, tagged: R.taggedPanelIds({ ...settings, today: '2026-10-10' }),
                 heading: R.cardHeading({ panels, newIds, release: RAW.release }) };""")
    assert got["newIds"] == TRAVEL_DESKS and got["tagged"] == TRAVEL_DESKS
    assert got["heading"]["kind"] == "release"
    assert got["heading"]["text"] == "New this release · v1.1 (sample release)"


@pytest.mark.parametrize("travel, desks, first", [("1.1.0", "1.1", "1.1.0"), ("1.1", "1.1.0", "1.1")],
                         ids=["1.1.0-first", "1.1-first"])
def test_equal_versions_share_a_group_spelled_first_in_list_order(js, travel, desks, first):
    got = run(js, f"""const panels = withPanels({{ promotions: {{ status: 'live', since: '1.2' }},
                                               travel: {{ since: '{travel}' }}, desks: {{ since: '{desks}' }} }});
        const release = {V12};
        const newIds = R.newPanelIds({{ panels, release, windowDays: 7, lastSeen: '1.0', today: '2026-10-10' }});
        return R.cardHeading({{ panels, newIds, release }}).groups;""")
    assert got == [{"version": first, "names": ["Travel", "Desk Allocation"]},
                   {"version": "1.2", "names": ["Promotions"]}]


def test_card_heading_rules(js):
    got = run(js, f"""const forced = R.newPanelIds({{ panels: DEFAULTS, release: {V12}, windowDays: 7,
                                                      lastSeen: null, today: '2026-10-10', force: true }});
        const text = (label) => R.cardHeading({{ panels: DEFAULTS, newIds: ['travel', 'desks'],
                                                 release: {{ version: '1.1', date: '2026-10-09', label }} }}).text;
        return {{ empty: R.cardHeading({{ ...SAMPLE, newIds: [] }}), forced,
                  forcedHeading: R.cardHeading({{ panels: DEFAULTS, newIds: forced, release: {V12} }}),
                  badVersion: R.cardHeading({{ panels: DEFAULTS, newIds: ['travel'], release: {{ version: 1.1 }} }}),
                  labels: [text(''), text(undefined), text(7)] }};""")
    assert got == {"empty": None, "forced": [], "forcedHeading": None, "badVersion": None,
                   "labels": ["New this release · v1.1"] * 3}


def test_last_seen_rules(js):
    """Rule 5, and a malformed lastSeen falling back to rule 4."""
    got = run(js, """return ['1.1', 'soon', '1.0'].map((lastSeen) =>
        R.newPanelIds({ ...SAMPLE, lastSeen, today: '2026-10-10' }));""")
    assert got == [[], TRAVEL_DESKS, TRAVEL_DESKS]


def test_rules_never_throw_on_garbage(js):
    got = run(js, """const day = { today: '2026-10-10', lastSeen: null };
        const cases = [{ ...SAMPLE, ...day, panels: null }, { ...SAMPLE, ...day, panels: 7 },
                       { ...SAMPLE, ...day, release: null }, { ...SAMPLE, today: undefined },
                       { ...SAMPLE, ...day, panels: [null] }, null, undefined, 7];
        return cases.map((c) => [R.newPanelIds(c), R.taggedPanelIds(c), R.cardHeading(c), R.releaseWarnings(c)]);""")
    calm = [[], [], None, []]
    # release: null is present and no object, so releaseWarnings names both fields (and still never throws).
    assert got == [calm, calm, [[], [], None, [helpers.W_NEWS_VERSION, helpers.W_NEWS_DATE]]] + [calm] * 5


def test_storage_helpers_never_throw(js):
    """AC13's pure leg: a throwing getter or storage gives null/false; only a version is read or written."""
    got = run(js, """const boom = () => { throw new Error('blocked'); };
        const throwing = { getItem: boom, setItem: boom };
        const good = fakeStorage({ k: '1.1', bad: 'soon' });
        return { getter: [R.readLastSeen(boom, 'k'), R.writeLastSeen(boom, 'k', '1.2')],
                 storage: [R.readLastSeen(() => throwing, 'k'), R.writeLastSeen(() => throwing, 'k', '1.2')],
                 soon: R.readLastSeen(() => good, 'bad'), control: R.readLastSeen(() => good, 'k'),
                 absent: R.readLastSeen(() => good, 'none'),
                 write: R.writeLastSeen(() => good, 'w', '1.2'), stored: good.data.w,
                 writeBad: R.writeLastSeen(() => good, 'x', 'soon'), log: good.log };""")
    assert got == {"getter": [None, False], "storage": [None, False], "soon": None, "control": "1.1", "absent": None,
                   "write": True, "stored": "1.2", "writeBad": False, "log": [["w", "1.2"]]}


def test_create_release_picks_the_key_and_force(js):
    got = run(js, """const pick = (over) => { const v = make(over);
          return { key: v.hook.key, force: v.hook.force, today: v.hook.today, warned: v.warned }; };
        return { real: pick({}), now: pick({ now: '2026-10-20' }), bad: pick({ now: 'bad' }),
                 whatsnew: pick({ whatsnew: true }), rest: pick({ rest: true }),
                 local: R.localDate(new Date(2026, 9, 10, 9)) };""")
    assert got["local"] == "2026-10-10"
    assert got["real"] == {"key": LAST_SEEN_KEY, "force": False, "today": "2026-10-10", "warned": []}
    assert got["now"] == {"key": SIM_KEY, "force": False, "today": "2026-10-20", "warned": []}
    assert got["bad"] == {"key": SIM_KEY, "force": False, "today": "2026-10-10", "warned": [helpers.W_NEWS_NOW]}
    assert got["whatsnew"] == {"key": SIM_KEY, "force": True, "today": "2026-10-10", "warned": []}
    assert got["rest"] == {"key": SIM_KEY, "force": False, "today": "2026-10-10", "warned": []}


def test_create_release_computes_the_sets_and_leaves_last_seen(js):
    got = run(js, """const v = make({});
        const recorded = v.hook.recordSeen();
        return { keys: Object.keys(v.hook).sort(), newIds: v.hook.newIds, taggedIds: v.hook.taggedIds,
                 lastSeen: v.hook.lastSeen, recorded, log: v.log };""")
    assert got == {"keys": sorted(HOOK_KEYS), "newIds": TRAVEL_DESKS, "taggedIds": TRAVEL_DESKS, "lastSeen": None,
                   "recorded": True, "log": [[LAST_SEEN_KEY, "1.1"]]}


def test_release_warnings_with_the_shipped_panels_are_empty(js):
    assert run(js, "return R.releaseWarnings(SAMPLE);") == []


def test_a_release_that_is_no_object_warns_for_both_fields(js):
    """Present but not an object (null, a version string, a number, an array) warns; absent stays silent."""
    got = run(js, """return [null, '1.1', 7, ['1.1'], undefined].map((release) =>
        R.releaseWarnings({ ...SAMPLE, release }));""")
    assert got == [[helpers.W_NEWS_VERSION, helpers.W_NEWS_DATE]] * 4 + [[]]


def test_release_warnings_and_create_release_never_throw(js):
    got = run(js, """const boom = () => { throw new Error('blocked'); };
        const out = [];
        for (const raw of [{ release: null }, { release: 7, newsWindowDays: null }, null, 7]) {
          for (const getStorage of [() => fakeStorage(), boom]) {
            for (const panels of [DEFAULTS, null, [null]]) {
              const hook = R.createRelease({ now: null, whatsnew: false, rest: false, raw, panels,
                                             date: new Date(2026, 9, 10, 9), getStorage, warn: () => {} });
              out.push({ warned: Array.isArray(R.releaseWarnings({ panels, release: raw?.release })),
                         keys: Object.keys(hook).sort(), newIds: hook.newIds, taggedIds: hook.taggedIds,
                         recorded: hook.recordSeen() });
            }
          }
        }
        return out;""")
    assert got == [{"warned": True, "keys": sorted(HOOK_KEYS), "newIds": [], "taggedIds": [], "recorded": False}] * 24


# --- The boot wiring: stage.__weaveRelease on the real page (each test pins its own instant or uses ?now=). ---

IN_WINDOW = "2026-10-10T09:00:00"
AFTER_WINDOW = "2026-10-20T09:00:00"
STORED = "(key) => localStorage.getItem(key)"


@pytest.mark.parametrize("search, expected", [
    ("", [None, False]), ("?now=2026-10-20&whatsnew", ["2026-10-20", True]), ("?now=", ["", False]),
    ("?whatsnew=0", [None, True]),
], ids=["none", "both", "empty-now", "whatsnew-0"])
def test_read_hooks_reads_the_release_parameters(js, search, expected):
    got = js(f"const h = (await import('/public/js/dom.js')).readHooks({json.dumps(search)});"
             " return [h.now, h.whatsnew, Object.keys(h).sort()];")
    assert got[:2] == expected
    assert got[2] == sorted(["watchdog", "limitMs", "rest", "still", "now", "whatsnew"])


@pytest.mark.parametrize("value", ["2026-10-9", "2026-02-30", "zz-not-a-date"])
def test_invalid_now_is_ignored_with_a_warning(make_page, base_url, value):
    """AC3: ignored with a warning; today is the local date, the key is the .sim key, the value is never written."""
    page, errors, warnings = helpers.open_release(make_page, base_url, f"?now={value}", clock=IN_WINDOW)
    state = helpers.release_state(page)
    assert warnings == [helpers.W_NEWS_NOW] and errors == []
    assert state["today"] == "2026-10-10" and state["key"] == SIM_KEY
    assert value not in page.content()


@pytest.mark.parametrize("instant, today, new_ids", [
    ("2026-10-08T21:00:00-04:00", "2026-10-08", []),
    ("2026-10-09T00:30:00-04:00", "2026-10-09", TRAVEL_DESKS),
    ("2026-10-15T21:00:00-04:00", "2026-10-15", TRAVEL_DESKS),
], ids=["eve-21h", "release-day-0h30", "last-day-21h"])
def test_today_is_the_local_date_at_boot(make_page, base_url, instant, today, new_ids):
    """AC4: a UTC-date bug fails the first case, where UTC is already 10-09."""
    page, errors, _ = helpers.open_release(make_page, base_url, clock=instant, timezone_id="America/New_York")
    state = helpers.release_state(page)
    assert (state["today"], state["newIds"]) == (today, new_ids) and errors == []


@pytest.mark.parametrize("query, new_ids", [("?now=2026-10-08", []), ("?now=2026-10-08&whatsnew", TRAVEL_DESKS)],
                         ids=["plain", "whatsnew"])
def test_before_the_window_nothing_is_written(make_page, base_url, query, new_ids):
    """AC12; the positive control is test_simulated_visits_write_only_the_sim_key."""
    page, errors, _ = helpers.open_release(make_page, base_url, query)
    assert helpers.release_state(page)["newIds"] == new_ids
    assert helpers.record_seen(page) is False
    assert page.evaluate("() => localStorage.length") == 0 and errors == []


@pytest.mark.parametrize("query, clock", [("?now=2026-10-20", None), ("?whatsnew", AFTER_WINDOW),
                                          ("?pose=rest", IN_WINDOW)], ids=["now", "whatsnew", "pose-rest"])
def test_simulated_visits_write_only_the_sim_key(make_page, base_url, query, clock):
    """AC14: a simulated visit writes the .sim key and leaves the real one absent."""
    options = {} if clock is None else {"clock": clock}
    page, errors, _ = helpers.open_release(make_page, base_url, query, **options)
    assert helpers.record_seen(page) is True
    assert page.evaluate(STORED, SIM_KEY) == "1.1" and page.evaluate(STORED, LAST_SEEN_KEY) is None
    assert errors == []


def test_real_visit_writes_the_real_key(make_page, base_url):
    """The control for test_simulated_visits_write_only_the_sim_key."""
    page, errors, _ = helpers.open_release(make_page, base_url, clock=IN_WINDOW)
    assert helpers.release_state(page)["key"] == LAST_SEEN_KEY
    assert helpers.record_seen(page) is True
    assert page.evaluate(STORED, LAST_SEEN_KEY) == "1.1" and page.evaluate(STORED, SIM_KEY) is None
    assert errors == []


# Makes the page's own window.localStorage read throw, as site data blocked by policy does (U3).
BLOCK_STORAGE = """Object.defineProperty(window, 'localStorage', { configurable: true,
  get() { throw new DOMException('blocked', 'SecurityError'); } });"""


def test_blocked_local_storage_boots_and_applies_rule_4(make_page, base_url):
    """AC13's page leg: no errors, no lastSeen, rule 4's set, and recordSeen writes nothing."""
    page, errors, _ = helpers.open_release(make_page, base_url, clock=IN_WINDOW,
                                           before_goto=lambda p: p.add_init_script(BLOCK_STORAGE))
    # The planted precondition: the page's storage read really throws.
    assert page.evaluate("() => { try { localStorage; return 'readable'; } catch { return 'threw'; } }") == "threw"
    state = helpers.release_state(page)
    assert errors == [] and state["lastSeen"] is None and state["newIds"] == TRAVEL_DESKS
    assert helpers.record_seen(page) is False


SKIPS_AND_DUPLICATES = """window.WEAVE_PANELS = { release: { version: '1.1', date: '2026-10-09' }, newsWindowDays: 7,
  panels: [
    { id: 'travel', name: 'Travel', status: 'live', since: '1.1', sample: null },
    { id: 'ghost', name: ' ', status: 'live', since: '1.1', sample: null },
    { id: 'travel', name: 'Travel again', status: 'live', since: '1.1', sample: null },
    { id: 'old', name: 'Old', status: 'live', since: '1.0', sample: null },
  ] };"""


def test_skipped_and_duplicate_entries_are_never_candidates(make_page, base_url):
    page, errors, warnings = helpers.open_release(make_page, base_url, panels_body=SKIPS_AND_DUPLICATES,
                                                  clock=IN_WINDOW)
    assert helpers.release_state(page)["newIds"] == ["travel"]
    assert warnings == [] and errors == []


BROKEN = {
    "throws": ("throw new Error('planted panels.js failure');", []),
    "release-null": ("""window.WEAVE_PANELS = { release: null, newsWindowDays: 7, panels: [
      { id: 'travel', name: 'Travel', status: 'live', since: '1.1', sample: null } ] };""",
                     [helpers.W_NEWS_VERSION, helpers.W_NEWS_DATE]),
}


@pytest.mark.parametrize("case", BROKEN, ids=list(BROKEN))
def test_broken_panels_js_means_nothing_new(make_page, base_url, case):
    """A missing or broken panels.js means nothing is new; release.js adds no error and the hero still settles."""
    body, expected_warnings = BROKEN[case]
    page, errors, warnings = helpers.open_release(make_page, base_url, panels_body=body, clock=IN_WINDOW)
    state = helpers.release_state(page)
    assert (state["newIds"], state["taggedIds"]) == ([], [])
    assert warnings == expected_warnings
    # The one error a throwing panels.js may cause is its own throw (and E1's load message, which it reports).
    pageerrors = [e for e in errors if e.startswith("pageerror:")]
    assert [e for e in pageerrors if "planted panels.js failure" not in e] == [], errors
    assert helpers.hero_result(page)[0] == "still"


def test_shipped_panels_boot_cleanly_on_both_paths(make_page, base_url):
    """AC17: no errors or release warnings on either path, release.js loads, the still path never requests Three."""
    requested = []
    page, errors, warnings = helpers.open_release(
        make_page, base_url, clock=FIXED_INSTANT, before_goto=lambda p: p.on("request", lambda r: requested.append(r.url)))
    page.wait_for_load_state("networkidle")
    keys = helpers.release_keys(page)
    assert errors == [] and warnings == []
    assert any(url.endswith("/public/js/release.js") for url in requested), requested
    assert not [url for url in requested if "three.module" in url], requested
    assert keys == sorted(HOOK_KEYS) and helpers.release_state(page)["newIds"] == []

    live_warnings = []
    page, errors = helpers.open_live(
        make_page, base_url, clock=FIXED_INSTANT,
        before_goto=lambda p: helpers.collect_warnings(p, helpers.RELEASE_WARNING_PREFIX, live_warnings))
    assert errors == [] and live_warnings == [] and helpers.release_keys(page) == sorted(HOOK_KEYS)


def test_release_js_imports_nothing():
    """AC17, a source property on purpose: with comments stripped, release.js has no import of any kind."""
    text = (WEAVE / "public" / "js" / "release.js").read_text(encoding="utf-8")
    code = re.sub(r"//[^\n]*", "", re.sub(r"/\*.*?\*/", "", text, flags=re.S))
    assert "export function newPanelIds" in code
    assert not re.search(r"^\s*import\b", code, re.M) and "import(" not in code
