"""panels.js drives the quilt end to end: an edit to the file changes the quilt and the lists together."""
from pathlib import Path

import pytest

from helpers import open_live, weave

SHIPPED = (Path(__file__).resolve().parents[1] / "public" / "panels.js").read_text(encoding="utf-8")
EDITS = """
const panels = window.WEAVE_PANELS.panels;
panels.find((p) => p.id === 'manpower').name = 'Personnel';
panels.unshift(...panels.splice(panels.findIndex((p) => p.id === 'travel'), 1));
Object.assign(panels.find((p) => p.id === 'promotions'), { status: 'live', since: '1.1', sample: { value: 5, unit: 'boards' } });
"""


def slot_of(slots, panel_id):
    return next(s for s in slots if s["id"] == panel_id)


def test_editing_panels_js_changes_the_quilt_and_the_lists(make_page, base_url):
    """The epic's fixture test (control: the default order starts with manpower, in test_hero.py)."""
    page, errors = open_live(make_page, base_url, panels_body=SHIPPED + EDITS)
    assert weave(page, ".order")[0] == "travel"
    slots = weave(page, ".slots")
    assert slot_of(slots, "manpower")["name"] == "Personnel"
    promotions = slot_of(slots, "promotions")
    assert promotions["status"] == "live" and promotions["face"] == "sewn"
    live = page.locator('[data-list="live"] .panel-name').all_text_contents()
    planned = page.locator('[data-list="planned"] .panel-name').all_text_contents()
    assert live[0] == "Travel" and "Personnel" in live and "Promotions" in live
    assert "Promotions" not in planned
    assert errors == []


SLOT_BODIES = {
    "ten": SHIPPED + "\nwindow.WEAVE_PANELS.panels.length = 10;\n",
    "thirteen": SHIPPED + "\nwindow.WEAVE_PANELS.panels.push({ id: 'extra', name: 'Extra', status: 'planned', sample: null });\n",
    "broken": "window.WEAVE_PANELS = {",
}
DEFAULT_IDS = ["manpower", "hiring", "training", "awards", "promotions", "travel", "feedback", "actions",
               "oversight", "access", "desks", "suggest"]


@pytest.mark.parametrize("case", ["ten", "thirteen", "broken"])
def test_slot_filling(make_page, base_url, case):
    page, _ = open_live(make_page, base_url, panels_body=SLOT_BODIES[case])
    order = weave(page, ".order")
    slots = weave(page, ".slots")
    if case == "ten":
        assert order == DEFAULT_IDS[:10] + [None, None]
        assert all(s["face"] == "filler" and s["id"] is None for s in slots[10:])
    elif case == "thirteen":
        assert order == DEFAULT_IDS
    else:
        assert order == [None] * 12 and all(s["face"] == "filler" for s in slots)
    snap_faces = page.eval_on_selector("[data-hero]", "el => el.__weave.snapshot().blocks.map((b) => b.face)")
    assert snap_faces == [s["face"] for s in slots]  # the drawn quilt agrees with the hooks
