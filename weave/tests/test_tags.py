"""#14: the "New" tags, from #12's taggedIds: a badge beside each tagged panel's name in the lists, and the tiles the
scene asks the painter to label (stage.__weave.slots[i].tagged). Every expected value is a literal here."""
import re
from pathlib import Path

import pytest

import helpers
from helpers import RELEASE_READY

WEAVE = Path(__file__).resolve().parents[1]

NEW = "New"
TAGGED_NAMES = ["Travel", "Desk Allocation"]
TAGGED_IDS = ["travel", "desks"]
LIVE_NAMES = ["Manpower", "Hiring", "Training", "Awards", "Travel", "Action Tracking", "Desk Allocation"]
IN_WINDOW_Q = "?now=2026-10-10"
BEFORE_Q = "?now=2026-10-08"
AFTER_Q = "?now=2026-10-20"

SHIPPED = (WEAVE / "public" / "panels.js").read_text(encoding="utf-8")


def _replace(text, old, new, count):
    assert text.count(old) == count, (old, text.count(old))
    return text.replace(old, new)


# The first release: release 1.0, and every live panel since 1.0, so nothing is new.
FIRST_RELEASE = _replace(_replace(SHIPPED, "version: '1.1'", "version: '1.0'", 1), "since: '1.1'", "since: '1.0'", 2)
# A 13th valid entry, live and new in the release: it is listed but has no tile.
PAYROLL = ("    { id: 'payroll', name: 'Payroll', icon: 'people', fabric: 'muslin', status: 'live', since: '1.1',"
           " sample: null, blurb: 'Pay.' },\n")
THIRTEENTH = re.sub(r"(\r?\n)(  \],)", lambda m: m.group(1) + PAYROLL.replace("\n", m.group(1)) + m.group(2),
                    SHIPPED, count=1)
assert "'payroll'" in THIRTEENTH

# Per li that holds a badge: [name text, badge text, badge follows the name, name contains badge, badge is the li's
# child, the li's list].
BADGES = r"""() => [...document.querySelectorAll('li.panel')].filter((li) => li.querySelector('.panel-new')).map((li) => {
    const name = li.querySelector('.panel-name');
    const badge = li.querySelector('.panel-new');
    return [name.textContent, badge.textContent, badge.previousElementSibling === name, name.contains(badge),
            badge.parentElement === li, li.closest('[data-list]').dataset.list];
})"""
LIVE_ROWS = "() => document.querySelectorAll('[data-list=\"live\"] li.panel').length"
TAGGED_ANYWHERE = "() => [document.querySelectorAll('.panel-new').length, document.querySelectorAll('li.is-new').length]"


def badges(page):
    return page.evaluate(BADGES)


def expected_rows(names):
    return [[name, NEW, True, False, True, "live"] for name in names]


def assert_no_badges(page):
    assert page.evaluate(LIVE_ROWS) == 7
    assert page.evaluate(TAGGED_ANYWHERE) == [0, 0]


# --- The list badge. ---


def test_badges_inside_the_window(make_page, base_url):
    page, errors, _ = helpers.open_release(make_page, base_url, IN_WINDOW_Q)
    assert helpers.release_state(page)["taggedIds"] == TAGGED_IDS
    assert badges(page) == expected_rows(TAGGED_NAMES)
    # E1's list read: the name element holds the name alone.
    assert page.eval_on_selector_all('[data-list="live"] .panel-name', "els => els.map((e) => e.textContent)") \
        == LIVE_NAMES
    geometry = page.evaluate(r"""() => [...document.querySelectorAll('li.is-new')].map((li) => {
        const n = li.querySelector('.panel-name').getBoundingClientRect();
        const b = li.querySelector('.panel-new').getBoundingClientRect();
        return { sameLine: b.top < n.bottom && b.bottom > n.top, after: b.left >= n.right, n: [n.left, n.top, n.right, n.bottom],
                 b: [b.left, b.top, b.right, b.bottom] };
    })""")
    assert len(geometry) == 2 and all(g["sameLine"] and g["after"] for g in geometry), geometry
    assert errors == []


def test_badge_is_read_with_its_list_item(make_page, base_url):
    page, _, _ = helpers.open_release(make_page, base_url, IN_WINDOW_Q)
    travel = page.locator('[data-list="live"] li.panel').nth(4)
    snapshot = travel.aria_snapshot()
    assert "listitem" in snapshot and re.search(r"\bTravel\s+New\b", snapshot), snapshot
    hidden = travel.locator(".panel-new").evaluate(r"""(badge) => {
        const out = [];
        for (let e = badge; e && e.tagName !== 'LI'; e = e.parentElement) {
          if (e.getAttribute('aria-hidden') === 'true' || ['presentation', 'none'].includes(e.getAttribute('role'))) out.push(e.className);
        }
        return out;
    }""")
    assert hidden == []


@pytest.mark.parametrize("query", [BEFORE_Q, AFTER_Q])
def test_no_badges_outside_the_window(make_page, base_url, query):
    page, errors, _ = helpers.open_release(make_page, base_url, query)
    assert helpers.release_state(page)["taggedIds"] == []
    assert_no_badges(page)
    assert errors == []


def test_whatsnew_outside_the_window_adds_no_badges(make_page, base_url):
    page, _, _ = helpers.open_release(make_page, base_url, AFTER_Q + "&whatsnew")
    state = helpers.release_state(page)
    assert state["newIds"] == TAGGED_IDS and state["taggedIds"] == []
    assert_no_badges(page)


def test_no_badges_on_the_first_release(make_page, base_url):
    page, _, _ = helpers.open_release(make_page, base_url, IN_WINDOW_Q, panels_body=FIRST_RELEASE)
    assert helpers.release_state(page)["taggedIds"] == []
    assert_no_badges(page)


def test_a_reload_keeps_the_badges(make_page, base_url):
    page, _, _ = helpers.open_release(make_page, base_url, IN_WINDOW_Q)
    assert badges(page) == expected_rows(TAGGED_NAMES)
    assert helpers.record_seen(page) is True
    page.reload()
    page.wait_for_function(RELEASE_READY)
    state = helpers.release_state(page)
    assert state["lastSeen"] == "1.1" and state["newIds"] == []
    assert badges(page) == expected_rows(TAGGED_NAMES)


def test_a_thirteenth_live_panel_gets_a_badge(make_page, base_url):
    page, _, _ = helpers.open_release(make_page, base_url, IN_WINDOW_Q, panels_body=THIRTEENTH)
    assert badges(page) == expected_rows([*TAGGED_NAMES, "Payroll"])


@pytest.mark.parametrize("path", ["reduced-motion", "no-webgl"])
def test_still_paths_show_the_badges(make_page, base_url, browser_no_webgl, path):
    if path == "reduced-motion":
        page, _, _ = helpers.open_release(make_page, base_url, IN_WINDOW_Q)
    else:
        page, _, _ = helpers.open_release(make_page, base_url, IN_WINDOW_Q, target_browser=browser_no_webgl,
                                          reduced_motion="no-preference")
    assert helpers.hero_result(page) == ["still", path]
    assert badges(page) == expected_rows(TAGGED_NAMES)


@pytest.mark.parametrize("tagged, count", [("['travel']", 1), ("'travel'", 0), ("new Set(['travel'])", 0)],
                         ids=["array", "string", "set"])
def test_render_panels_ignores_a_non_array_tag_set(js, tagged, count):
    found = js(r"""
        const { cleanPanels } = await import('/public/js/catalog.js');
        const { renderPanels } = await import('/public/js/dom.js');
        const section = document.createElement('section');
        section.innerHTML = '<p data-panels-status hidden></p><div data-group><ul data-list="live"></ul></div>'
          + '<div data-group><ul data-list="planned"></ul></div><p data-suggest hidden></p>';
        document.body.append(section);
        const result = cleanPanels({ panels: [
          { id: 'travel', name: 'Travel', status: 'live', sample: null },
          { id: 'feedback', name: 'Feedback', status: 'planned', sample: null },
        ] });
        renderPanels(section, result, %s);
        return [section.querySelectorAll('li.panel').length, section.querySelectorAll('.panel-new').length];
    """ % tagged)
    assert found == [2, count]


def visible_badges(page):
    return page.evaluate("() => [...document.querySelectorAll('.panel-new')].filter((b) => b.getClientRects().length"
                         " && getComputedStyle(b).visibility !== 'hidden').length")


@pytest.mark.parametrize("width", [390, 1440])
def test_badges_meet_contrast(make_page, base_url, width):
    page, _, _ = helpers.open_release(make_page, base_url, IN_WINDOW_Q, viewport={"width": width, "height": 844})
    assert visible_badges(page) == 2
    # The control: a pale badge must be caught, so the badges are in the checked set.
    page.evaluate("() => { document.querySelector('.panel-new').style.color = '#BBBBBB'; }")
    assert any(f["text"] == NEW for f in helpers.contrast_failures(page))
    page.evaluate("() => { document.querySelector('.panel-new').style.color = ''; }")
    assert helpers.contrast_failures(page) == []


def test_no_horizontal_scroll_with_badges(make_page, base_url):
    page, _, _ = helpers.open_release(make_page, base_url, IN_WINDOW_Q, viewport={"width": 390, "height": 844})
    assert visible_badges(page) == 2
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")


def test_tagged_row_height_matches(make_page, base_url):
    page, _, _ = helpers.open_release(make_page, base_url, IN_WINDOW_Q)
    heights = page.evaluate(r"""() => {
        const rows = [...document.querySelectorAll('[data-list="live"] li.panel')];
        const height = (name) => rows.find((li) => li.querySelector('.panel-name').textContent === name).getBoundingClientRect().height;
        return { travel: height('Travel'), training: height('Training'), tagged: rows[4].classList.contains('is-new') };
    }""")
    assert heights["tagged"] is True
    assert abs(heights["travel"] - heights["training"]) <= 1, heights

