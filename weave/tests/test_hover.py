"""#10's hover: the tooltip (dom.js and weave.css, on a blank page) and, on the live page, naming and lifting a block."""
import pytest

from helpers import (HOVER_WINDOW_MS, LINK_CSS, PLANNED_WORDS, SEWN_WORDS, SUGGEST_WORDS, assert_tile_geometry,
                     contrast_failures, frames, log_modes, open_live, project, wait_for_data_mode, wait_for_quilt, weave)
from test_quilt_panels import SLOT_BODIES
from test_unstitch import REST, layout, tile_geometry, unstitch

# A 528 x 330 .hero-stage (weave.css's aspect ratio) with weave.css linked, and dom.js as D.
TIP_JS = LINK_CSS + r"""
    const D = await import('/public/js/dom.js');
    const stage = document.createElement('div');
    stage.className = 'hero-stage';
    stage.style.width = '528px';
    document.body.append(stage);
"""


def tip(js, body):
    return js(TIP_JS + body)


def test_tooltip_is_text_only_and_hidden_from_assistive_tech(js):
    r = tip(js, r"""
        const t = D.createTooltip(stage);
        const made = { children: stage.querySelectorAll('[data-tooltip]').length, parent: t.parentElement === stage,
                       aria: t.getAttribute('aria-hidden'), hidden: t.hidden };
        const name = '<img src=x onerror="window.__xss=1">';
        D.showTooltip(t, { name, face: 'sewn' }, 10, 20);
        await new Promise((resolve) => setTimeout(resolve, 50));
        const shown = { name: t.querySelector('.hero-tip-name').textContent === name, elements: t.querySelectorAll('*').length,
                        xss: window.__xss === undefined, hidden: t.hidden };
        D.hideTooltip(t);
        return { made, shown, after: t.hidden };
    """)
    assert r["made"] == {"children": 1, "parent": True, "aria": "true", "hidden": True}
    assert r["shown"] == {"name": True, "elements": 2, "xss": True, "hidden": False}
    assert r["after"] is True


def test_tooltip_flips_inside_the_stage(js):
    r = tip(js, r"""
        const t = D.createTooltip(stage);
        const box = (el) => { const b = el.getBoundingClientRect(); return [b.left, b.top, b.right, b.bottom]; };
        D.showTooltip(t, { name: 'Promotions and a long name', face: 'planned' }, 500, 300);
        const corner = { tip: box(t), stage: box(stage) };
        D.showTooltip(t, { name: 'Manpower', face: 'sewn' }, 10, 20);
        return { corner, near: [t.offsetLeft, t.offsetTop], size: [stage.clientWidth, stage.clientHeight],
                 display: [...t.children].map((c) => getComputedStyle(c).display),
                 style: (({ position, pointerEvents, opacity }) => ({ position, pointerEvents, opacity }))(getComputedStyle(t)) };
    """)
    assert r["size"] == [528, 330]
    (l, t, rt, b), (sl, st, sr, sb) = r["corner"]["tip"], r["corner"]["stage"]
    assert l >= sl and t >= st and rt <= sr and b <= sb, r["corner"]
    assert r["near"] == [22, 32]
    assert r["display"] == ["block", "block"]
    assert r["style"] == {"position": "absolute", "pointerEvents": "none", "opacity": "1"}


def test_tooltip_status_words(js):
    r = tip(js, r"""
        const t = D.createTooltip(stage);
        return ['sewn', 'planned', 'suggest'].map((face) => {
          D.showTooltip(t, { name: 'X', face }, 10, 10);
          return t.querySelector('.hero-tip-status').textContent;
        });
    """)
    assert r == [SEWN_WORDS, PLANNED_WORDS, SUGGEST_WORDS]


# --- The live page. ---

# Block `slot`'s top edge length |v40 - v0| from a fresh snapshot: the hover's 3 % scale, read off the drawn mesh.
EDGE = ("(slot) => { const p = document.querySelector('[data-hero]').__weave.snapshot().blocks[slot].positions;"
        " return Math.hypot(p[120] - p[0], p[121] - p[1], p[122] - p[2]); }")
HOVER_STATE = "() => document.querySelector('[data-hero]').__weave.hover"
TIP = "[data-tooltip]"
# (slot, name, status) per hovered face.
FACES = {"manpower": (0, "Manpower", SEWN_WORDS), "promotions": (4, "Promotions", PLANNED_WORDS),
         "suggest": (11, "Suggest a panel", SUGGEST_WORDS)}
SNAP_JSON = "el => JSON.stringify(el.__weave.snapshot())"


def edge(page, slot):
    return page.evaluate(f"({EDGE})({slot})")


def centre_xy(page, slot):
    """Block `slot`'s centre vertex, projected to client px."""
    return page.eval_on_selector("[data-hero]", "(el, slot) => el.__weave.project(el.__weave.snapshot().blocks[slot]"
                                 ".positions.slice(3 * 840, 3 * 841))", slot)


def slot_xy(page, slot):
    """Quilt slot `slot`'s centre on the z = 0 plane, projected to client px (wherever its block is now)."""
    return page.eval_on_selector("[data-hero]", "async (el, slot) => { const L = await import('/public/js/layout.js');"
                                 " return el.__weave.project([...L.slotCentre(slot), 0]); }", slot)


def hover_state(page):
    return page.evaluate(HOVER_STATE)


def tip_hidden(page):
    return page.eval_on_selector(TIP, "el => el.hidden")


def wait_ratio(page, slot, base, low, high, timeout=HOVER_WINDOW_MS):
    page.wait_for_function(f"([slot, base, low, high]) => {{ const r = ({EDGE})(slot) / base; return r >= low && r <= high; }}",
                           arg=[slot, base, low, high], timeout=timeout, polling=50)


# The hover amount eases at HOVER.rate (12/s) and snaps within 1e-3, so reaching exactly 0 or 1 takes about 0.58 s:
# longer than HOVER_WINDOW_MS, which times the negatives and their controls, not this settle.
HOVER_SETTLE_MS = 2000


def wait_hover(page, predicate, timeout=HOVER_SETTLE_MS):
    page.wait_for_function(f"() => {{ const h = document.querySelector('[data-hero]').__weave.hover; return {predicate}; }}",
                           timeout=timeout, polling=50)


def wait_tip_shown(page, timeout=HOVER_WINDOW_MS):
    page.wait_for_function(f"() => document.querySelector('{TIP}')?.hidden === false", timeout=timeout, polling=50)


def live_quilt(make_page, base_url, **kwargs):
    page, errors = open_live(make_page, base_url, **kwargs)
    wait_for_quilt(page)
    return page, errors


@pytest.mark.parametrize("face", list(FACES))
def test_hover_names_and_lifts_a_block(make_page, base_url, face):
    slot, name, status = FACES[face]
    page, errors = live_quilt(make_page, base_url)
    base = edge(page, slot)
    page.mouse.move(*centre_xy(page, slot))
    wait_ratio(page, slot, base, 1.025, 1.035)
    tip = page.locator(TIP)
    assert tip.count() == 1 and tip_hidden(page) is False
    assert tip.get_attribute("aria-hidden") == "true"
    assert [tip.locator(".hero-tip-name").text_content(), tip.locator(".hero-tip-status").text_content()] == [name, status]
    assert hover_state(page)["id"] == face
    assert contrast_failures(page) == []
    # U4: moving onto Pause leaves the canvas; the hover ends exactly.
    page.locator("[data-pause]").hover()
    wait_hover(page, "h.id === null && h.amount === 0")
    assert tip_hidden(page) is True
    assert abs(edge(page, slot) / base - 1) <= 1e-6
    assert errors == []


@pytest.mark.parametrize("slot", [0, 11], ids=["slot0", "slot11"])
def test_tooltip_stays_inside_the_stage(make_page, base_url, slot):
    page, errors = live_quilt(make_page, base_url)
    page.mouse.move(*centre_xy(page, slot))
    wait_tip_shown(page)
    tip = page.locator(TIP).bounding_box()
    stage = page.locator("[data-hero]").bounding_box()
    assert tip["x"] >= stage["x"] and tip["y"] >= stage["y"], (tip, stage)
    assert tip["x"] + tip["width"] <= stage["x"] + stage["width"], (tip, stage)
    assert tip["y"] + tip["height"] <= stage["y"] + stage["height"], (tip, stage)
    assert errors == []


# Block 0's top edge length from the snapshot the unstitching entry's handler sees.
EDGE_AT_UNSTITCH = r"""
    window.__onMode = (event, el) => {
      if (event.detail.mode !== 'unstitching') return;
      const p = el.__weave.snapshot().blocks[0].positions;
      window.__edge = Math.hypot(p[120] - p[0], p[121] - p[1], p[122] - p[2]);
    };
"""


def press_toggle_by_key(page):
    """Press the toggle from the keyboard, so the pointer stays where it rests."""
    page.locator("[data-toggle]").focus()
    page.keyboard.press("Enter")


def test_handler_sees_no_hover(make_page, base_url):
    """D39's scene first: a weave:mode handler's snapshot shows #8's pose, not the hover lift, though the pointer is
    still on the block."""
    def before(page):
        log_modes(page)
        page.add_init_script(EDGE_AT_UNSTITCH)
    page, errors = live_quilt(make_page, base_url, before_goto=before)
    base = edge(page, 0)
    page.mouse.move(*centre_xy(page, 0))
    wait_hover(page, "h.id === 'manpower' && h.amount === 1")
    press_toggle_by_key(page)
    page.wait_for_function("() => window.__edge !== undefined", timeout=2000)
    assert abs(page.evaluate("window.__edge") / base - 1) <= 1e-6
    assert errors == []


def test_resting_pointer_is_named_on_entering_quilt(make_page, base_url):
    page, errors = live_quilt(make_page, base_url)
    page.mouse.move(*centre_xy(page, 0))
    wait_hover(page, "h.id === 'manpower'")  # precondition
    press_toggle_by_key(page)
    wait_for_data_mode(page, "tiles")
    assert hover_state(page)["id"] is None and tip_hidden(page) is True
    press_toggle_by_key(page)
    wait_for_quilt(page)
    wait_hover(page, "h.id === 'manpower'", timeout=HOVER_WINDOW_MS)
    assert errors == []


def test_hover_skips_fillers(make_page, base_url):
    page, errors = live_quilt(make_page, base_url, panels_body=SLOT_BODIES["ten"])
    base = edge(page, 10)
    page.mouse.move(*centre_xy(page, 10))
    page.wait_for_timeout(HOVER_WINDOW_MS)
    assert tip_hidden(page) is True and hover_state(page)["id"] is None
    assert abs(edge(page, 10) / base - 1) <= 1e-6
    # Control: the block beside it is named within the same window.
    page.mouse.move(*centre_xy(page, 9))
    wait_tip_shown(page)
    assert errors == []


def test_hover_is_off_in_tiles_at_rest_and_in_the_intro(make_page, base_url):
    page, errors = live_quilt(make_page, base_url)
    unstitch(page)
    page.mouse.move(*project(page, [*layout(page)["tiles"][0], 0]))
    held = page.eval_on_selector("[data-hero]", SNAP_JSON)
    page.wait_for_timeout(HOVER_WINDOW_MS)
    assert tip_hidden(page) is True and hover_state(page)["id"] is None
    assert page.eval_on_selector("[data-hero]", SNAP_JSON) == held
    assert errors == []

    rest, rest_errors = open_live(make_page, base_url, query=REST)
    held = rest.eval_on_selector("[data-hero]", SNAP_JSON)
    rest.mouse.move(*centre_xy(rest, 0))
    rest.wait_for_timeout(HOVER_WINDOW_MS)
    assert tip_hidden(rest) is True
    assert rest.eval_on_selector("[data-hero]", SNAP_JSON) == held
    assert rest_errors == []

    intro, intro_errors = open_live(make_page, base_url)
    assert weave(intro, ".mode") == "intro"  # precondition
    intro.mouse.move(*slot_xy(intro, 0))
    intro.wait_for_timeout(HOVER_WINDOW_MS)
    hidden, mode = intro.eval_on_selector("[data-hero]", f"el => [document.querySelector('{TIP}').hidden, el.__weave.mode]")
    if mode != "intro":
        pytest.skip(f"the intro had ended ({mode}) before the {HOVER_WINDOW_MS} ms window closed")
    assert hidden is True
    assert intro_errors == []


def test_paused_hover_snaps(make_page, base_url):
    page, errors = live_quilt(make_page, base_url)
    page.locator("[data-pause]").click()
    held = frames(page)
    base = edge(page, 0)
    page.mouse.move(*centre_xy(page, 0))
    ratio, h = page.evaluate(f"() => [({EDGE})(0), ({HOVER_STATE})()]")
    assert abs(ratio / base - 1.03) <= 0.005, ratio / base
    assert h == {"id": "manpower", "amount": 1}
    assert frames(page) == held
    assert errors == []


def test_hovered_click_unstitches_flat(make_page, base_url):
    page, errors = live_quilt(make_page, base_url)
    at = centre_xy(page, 5)
    page.mouse.move(*at)
    wait_hover(page, "h.id === 'travel' && h.amount === 1")
    page.mouse.click(*at)
    wait_for_data_mode(page, "tiles")
    assert_tile_geometry(tile_geometry(page))
    assert errors == []


def test_teardown_removes_the_tooltip(make_page, base_url):
    page, errors = live_quilt(make_page, base_url)
    page.mouse.move(*centre_xy(page, 0))
    wait_tip_shown(page)
    page.eval_on_selector("[data-hero]", "el => el.__weave.stop('context-lost')")
    assert page.locator(TIP).count() == 0
    assert errors == []
