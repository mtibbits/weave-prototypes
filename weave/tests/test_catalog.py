"""cleanPanels: the pure cleaner between panels.js and the page. Every message is pinned in full here."""
import json
import math
import re

import pytest

E1 = ("WEAVE: the panel list (window.WEAVE_PANELS from panels.js) is missing or is not an object. "
      "Check panels.js for a syntax error.")
E2 = "WEAVE: WEAVE_PANELS.panels in panels.js is not an array."
W_OBJECT = "WEAVE: panels.js entry {n} was skipped: it is not an object."
W_ID = "WEAVE: panels.js entry {n} was skipped: its id must be a non-empty string."
W_NAME = "WEAVE: panels.js entry {n} was skipped: its name must be a non-empty string."
W_STATUS = "WEAVE: panels.js entry {n} was skipped: its status must be 'live', 'planned' or 'suggest'."
W_DUP = "WEAVE: panels.js entry {n} was skipped: the id '{id}' is already used (the first one is kept)."
W_SAMPLE = "WEAVE: the live panel '{id}' has no valid sample, so it reads \"No sample yet\"."
W_MANY = "WEAVE: panels.js has {count} valid panels; the quilt draws the first 12."

VALID = "{ id: 'ok', name: 'Okay', status: 'planned', sample: null }"

# (id, JS literal of the bad entry, message template). Shared with test_robustness.py.
MALFORMED = [
    ("object-null", "null", W_OBJECT),
    ("object-number", "7", W_OBJECT),
    ("object-string", "'x'", W_OBJECT),
    ("object-array", "[]", W_OBJECT),
    ("id-missing", "{ name: 'No id', status: 'live' }", W_ID),
    ("id-blank", "{ id: '  ', name: 'Blank id', status: 'live' }", W_ID),
    ("id-number", "{ id: 7, name: 'Seven', status: 'live' }", W_ID),
    ("name-missing", "{ id: 'a', status: 'live' }", W_NAME),
    ("name-blank", "{ id: 'a', name: '  ', status: 'live' }", W_NAME),
    ("name-number", "{ id: 'a', name: 7, status: 'live' }", W_NAME),
    ("status-unknown", "{ id: 'a', name: 'A', status: 'archived' }", W_STATUS),
    ("status-case", "{ id: 'a', name: 'A', status: 'Live' }", W_STATUS),
    ("status-missing", "{ id: 'a', name: 'A' }", W_STATUS),
]


def clean(js, raw):
    """Run cleanPanels over a JS literal; returns the result with error read as None when absent."""
    return js(f"""
        const m = await import('/public/js/catalog.js');
        const r = m.cleanPanels({raw});
        return {{ panels: r.panels, warnings: r.warnings, error: r.error ?? null, hasError: 'error' in r }};
    """)


@pytest.mark.parametrize("raw", ["null", "7", "'text'", "[]", "undefined"])
def test_never_throws_on_a_non_object(js, raw):
    r = clean(js, raw)
    assert r["panels"] == [] and r["warnings"] == [] and r["error"] == E1


@pytest.mark.parametrize("raw", ["{}", "{ panels: null }", "{ panels: {} }", "{ panels: 'x' }"])
def test_panels_not_an_array_is_a_broken_file(js, raw):
    r = clean(js, raw)
    assert r["panels"] == [] and r["warnings"] == [] and r["error"] == E2


@pytest.mark.parametrize("bad, template", [(b, t) for _, b, t in MALFORMED], ids=[i for i, _, _ in MALFORMED])
def test_malformed_entry_is_skipped(js, bad, template):
    r = clean(js, f"{{ panels: [{bad}, {VALID}] }}")
    assert [p["id"] for p in r["panels"]] == ["ok"]
    assert r["warnings"] == [template.format(n=1)]
    assert not r["hasError"]


def test_trims_id_and_name(js):
    r = clean(js, "{ panels: [{ id: '  a  ', name: '  Alpha  ', status: 'planned', sample: null }] }")
    assert (r["panels"][0]["id"], r["panels"][0]["name"]) == ("a", "Alpha")


def test_duplicate_id_keeps_the_first(js):
    r = clean(js, """{ panels: [
        { id: 'x', name: 'First', status: 'planned', sample: null },
        { id: ' x ', name: 'Second', status: 'planned', sample: null },
    ] }""")
    assert [p["name"] for p in r["panels"]] == ["First"]
    assert r["warnings"] == [W_DUP.format(n=2, id="x")]


def test_malformed_entry_does_not_claim_its_id(js):
    r = clean(js, """{ panels: [
        { id: 'x', name: 'Broken', status: 'archived' },
        { id: 'x', name: 'Kept', status: 'planned', sample: null },
    ] }""")
    assert [p["name"] for p in r["panels"]] == ["Kept"]
    assert r["warnings"] == [W_STATUS.format(n=1)]


def test_keeps_since_and_every_other_field(js):
    r = clean(js, """{ panels: [{ id: 'a', name: 'A', status: 'live', since: '1.0', icon: 'people',
        fabric: 'muslin', blurb: 'Words.', extra: { k: 1 }, sample: { value: 1, unit: 'u' } }] }""")
    p = r["panels"][0]
    assert (p["since"], p["icon"], p["fabric"], p["blurb"], p["extra"]) == ("1.0", "people", "muslin", "Words.", {"k": 1})
    assert p["sample"] == {"value": 1, "unit": "u"}


def test_every_suggest_entry_is_kept_in_order_without_a_warning(js):
    # The page shows the first kept suggest entry (test_robustness.py); the cleaner keeps them all.
    r = clean(js, """{ panels: [
        { id: 's1', name: 'One', status: 'suggest', sample: null, blurb: 'First idea.' },
        { id: 's2', name: 'Two', status: 'suggest', sample: null, blurb: 'Second idea.' },
    ] }""")
    assert [p["id"] for p in r["panels"]] == ["s1", "s2"]
    assert r["warnings"] == []


ABSENT = object()


@pytest.mark.parametrize("status, sample, expected, warns", [
    ("live", "null", None, 0),
    ("live", ABSENT, None, 1),
    ("live", "'abc'", None, 1),
    ("live", "{ value: NaN, unit: 'x' }", None, 1),
    ("live", "{ value: '  ', unit: 'x' }", None, 1),
    ("live", "{ value: 3 }", None, 1),
    ("live", "{ value: 3, unit: 7 }", None, 1),
    ("planned", "'abc'", None, 0),
    ("live", "{ value: '87%', unit: 'current' }", {"value": "87%", "unit": "current"}, 0),
    ("live", "{ value: 248, unit: 'assigned' }", {"value": 248, "unit": "assigned"}, 0),
], ids=["live-null", "live-absent", "live-string", "live-nan", "live-blank-value", "live-no-unit",
        "live-number-unit", "planned-string", "live-percent", "live-number"])
def test_sample_rules(js, status, sample, expected, warns):
    field = "" if sample is ABSENT else f", sample: {sample}"
    r = clean(js, f"{{ panels: [{{ id: 'p', name: 'P', status: '{status}'{field} }}] }}")
    assert r["panels"][0]["sample"] == expected
    assert r["warnings"] == [W_SAMPLE.format(id="p")] * warns


def _valid_sample(sample):
    """Independent re-statement of the sample rule over the returned JSON."""
    if sample is None:
        return True
    if not isinstance(sample, dict) or set(sample) != {"value", "unit"}:
        return False
    value, unit = sample["value"], sample["unit"]
    number = isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
    text = isinstance(value, str) and value.strip() != ""
    return (number or text) and isinstance(unit, str)


ODD_SAMPLES = [
    "Infinity", "[]", "{}", "{ value: {}, unit: 'x' }", "{ value: 3, unit: 'x', extra: 1 }",
    "{ value: -Infinity, unit: 'x' }", "{ value: Infinity, unit: 'x' }", "{ value: true, unit: 'x' }",
    "{ value: null, unit: 'x' }", "{ value: 0, unit: '' }", "{ value: '', unit: 'x' }", "{ value: [], unit: 'x' }",
    "{ unit: 'x' }", "{ value: 'a', unit: null }", "7", "'7 units'", "true",
]


def test_every_returned_sample_is_valid_or_null(js):
    entries = ", ".join(f"{{ id: 'p{i}', name: 'P', status: 'live', sample: {s} }}" for i, s in enumerate(ODD_SAMPLES))
    r = clean(js, f"{{ panels: [{entries}] }}")
    assert len(r["panels"]) == len(ODD_SAMPLES)
    for literal, panel in zip(ODD_SAMPLES, r["panels"]):
        assert _valid_sample(panel["sample"]), (literal, panel["sample"])
    # The two valid ones survive as exactly { value, unit }.
    assert [p["sample"] for p in r["panels"] if p["sample"] is not None] == [
        {"value": 3, "unit": "x"}, {"value": 0, "unit": ""}]


def test_more_than_twelve_valid_entries_warns_and_keeps_all(js):
    entries = ", ".join(f"{{ id: 'p{i}', name: 'P{i}', status: 'planned', sample: null }}" for i in range(13))
    r = clean(js, f"{{ panels: [{entries}] }}")
    assert len(r["panels"]) == 13
    assert r["warnings"] == [W_MANY.format(count=13)]


def test_twelve_valid_entries_do_not_warn(js):
    entries = ", ".join(f"{{ id: 'p{i}', name: 'P{i}', status: 'planned', sample: null }}" for i in range(12))
    assert clean(js, f"{{ panels: [{entries}] }}")["warnings"] == []


def test_does_not_mutate_its_input(js):
    same = js("""
        const m = await import('/public/js/catalog.js');
        const raw = { panels: [{ id: ' a ', name: ' A ', status: 'live', sample: 'bad' },
                               { id: 'a', name: 'B', status: 'planned' }, 7] };
        const before = JSON.stringify(raw);
        m.cleanPanels(raw);
        return before === JSON.stringify(raw);
    """)
    assert same is True


SHIPPED_IDS = ["manpower", "hiring", "training", "awards", "promotions", "travel",
               "feedback", "actions", "oversight", "access", "desks", "suggest"]


def test_the_shipped_panels_file_is_clean(js):
    out = js("""
        await new Promise((ok, bad) => {
            const s = document.createElement('script');
            s.src = '/public/panels.js';
            s.onload = ok;
            s.onerror = () => bad(new Error('panels.js did not load'));
            document.head.appendChild(s);
        });
        const m = await import('/public/js/catalog.js');
        const raw = window.WEAVE_PANELS;
        const r = m.cleanPanels(raw);
        return { panels: r.panels, warnings: r.warnings, hasError: 'error' in r,
                 release: raw.release, days: raw.newsWindowDays };
    """)
    assert not out["hasError"]
    assert out["warnings"] == []
    assert [p["id"] for p in out["panels"]] == SHIPPED_IDS
    live = [p for p in out["panels"] if p["status"] == "live"]
    assert len(live) == 7 and all(isinstance(p["since"], str) for p in live)
    release = out["release"]
    assert isinstance(release["version"], str) and isinstance(release["label"], str)
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", release["date"])
    days = out["days"]
    assert isinstance(days, int) and not isinstance(days, bool) and days > 0
    json.dumps(out)  # the whole file round-trips as plain data
