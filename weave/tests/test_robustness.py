"""Each panels.js robustness rule, on the real page, with panels.js swapped by page.route."""
import pytest

from helpers import MALFORMED, STATIC_LABEL, VALID, W_DUP, W_MANY, W_SAMPLE, hidden_by_attribute, open_page

LOAD_MESSAGE = "The panel list couldn't be loaded."


def body(entries):
    """A panels.js body from JS entry literals."""
    return f"window.WEAVE_PANELS = {{ panels: [{', '.join(entries)}] }};"


def names(page, group):
    return page.locator(f'[data-list="{group}"] li.panel .panel-name').all_text_contents()


def weave_errors(errors):
    return [e for e in errors if e.startswith("console.error: WEAVE:")]


@pytest.mark.parametrize("panels_body", [
    "window.WEAVE_PANELS = {",
    "",
    "window.WEAVE_PANELS = { panels: 'x' };",
], ids=["syntax-error", "empty", "not-an-array"])
def test_broken_file_shows_the_load_message(make_page, base_url, panels_body):
    page, errors = open_page(make_page, base_url, panels_body)
    assert len(weave_errors(errors)) == 1, errors
    status = page.locator("[data-panels-status]")
    assert status.is_visible() and status.text_content() == LOAD_MESSAGE
    assert page.locator("li.panel").count() == 0
    assert "None yet." not in page.locator("#panels").inner_text()
    for group in ("live", "planned"):
        assert hidden_by_attribute(page.locator(f'[data-group="{group}"]'))
    assert hidden_by_attribute(page.locator("[data-suggest]"))
    assert page.locator("[data-hero]").get_attribute("aria-label") == STATIC_LABEL


@pytest.mark.parametrize("bad,message", [(b, m) for _, b, m in MALFORMED], ids=[i for i, _, _ in MALFORMED])
def test_malformed_entry_is_skipped_with_a_warning(make_page, base_url, bad, message):
    warnings = []
    page, _ = open_page(make_page, base_url, body([bad, VALID]), warnings)
    assert names(page, "live") + names(page, "planned") == ["Okay"]
    assert warnings == [message.format(n=1)]


def test_duplicate_id_keeps_the_first(make_page, base_url):
    warnings = []
    page, _ = open_page(make_page, base_url, body([
        "{ id: 'x', name: 'First', status: 'planned', sample: null }",
        "{ id: ' x ', name: 'Second', status: 'planned', sample: null }",
    ]), warnings)
    assert names(page, "planned") == ["First"]
    assert warnings == [W_DUP.format(n=2, id='x')]


def figure(page):
    return page.locator('[data-list="live"] li.panel .panel-figure').all_text_contents()


def test_live_null_sample_reads_no_sample_yet_without_a_warning(make_page, base_url):
    warnings = []
    page, _ = open_page(make_page, base_url, body(["{ id: 'a', name: 'A', status: 'live', sample: null }"]), warnings)
    assert figure(page) == ["No sample yet"]
    assert warnings == []


@pytest.mark.parametrize("field", ["", ", sample: 'abc'"], ids=["absent", "string"])
def test_live_missing_or_bad_sample_reads_no_sample_yet_with_a_warning(make_page, base_url, field):
    warnings = []
    page, _ = open_page(make_page, base_url, body([f"{{ id: 'a', name: 'A', status: 'live'{field} }}"]), warnings)
    assert figure(page) == ["No sample yet"]
    assert warnings == [W_SAMPLE.format(id='a')]


def test_empty_unit_reads_value_and_sample(make_page, base_url):
    page, _ = open_page(make_page, base_url, body(["{ id: 'a', name: 'A', status: 'live', sample: { value: 5, unit: '' } }"]))
    assert figure(page) == ["5 (sample)"]


def test_thirteen_entries_are_all_listed_with_a_warning(make_page, base_url):
    warnings = []
    entries = [f"{{ id: 'p{i}', name: 'P{i}', status: 'planned', sample: null }}" for i in range(13)]
    page, _ = open_page(make_page, base_url, body(entries), warnings)
    assert page.locator("li.panel").count() == 13
    assert warnings == [W_MANY.format(count=13)]


def test_empty_panel_list_reads_none_yet(make_page, base_url):
    page, errors = open_page(make_page, base_url, body([]))
    assert page.locator("#panels h3").all_text_contents() == ["Sewn in", "Pinned for later"]
    for group in ("live", "planned"):
        assert page.locator(f'[data-list="{group}"] li').all_text_contents() == ["None yet."]
    assert hidden_by_attribute(page.locator("[data-suggest]"))
    assert errors == []


def test_first_suggest_entry_wins(make_page, base_url):
    page, _ = open_page(make_page, base_url, body([
        "{ id: 's1', name: 'One', status: 'suggest', sample: null, blurb: 'First idea.' }",
        "{ id: 's2', name: 'Two', status: 'suggest', sample: null, blurb: 'Second idea.' }",
    ]))
    assert page.locator("[data-suggest]").text_content() == "First idea."


def test_suggest_without_a_blurb_shows_its_name(make_page, base_url):
    page, _ = open_page(make_page, base_url, body(["{ id: 's', name: 'Tell us', status: 'suggest', sample: null }"]))
    assert page.locator("[data-suggest]").text_content() == "Tell us"


# Planted controls: hidden_by_attribute must turn red when the mechanism is broken either way.

def test_hidden_check_fails_when_the_attribute_is_stripped(make_page, base_url):
    page, _ = open_page(make_page, base_url, body([]))
    suggest = page.locator("[data-suggest]")
    suggest.evaluate("el => { el.hidden = false; }")
    assert not hidden_by_attribute(suggest)


def test_hidden_check_fails_when_css_overrides_the_attribute(make_page, base_url):
    page, _ = open_page(make_page, base_url, body([]))
    page.add_style_tag(content=".suggest[hidden] { display: block !important; }")
    assert not hidden_by_attribute(page.locator("[data-suggest]"))
