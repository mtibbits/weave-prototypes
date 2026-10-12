"""?pose=rest and ?frame=still (the capture recipe), the page's snapshot(), and the corners that must stay in view."""
import pytest

from helpers import HOME, frames, hero_result, open_live, wait_for_reason

# Stores the stage's snapshot as JSON in window.__snap; SAME_AS_STORED compares a fresh one with it.
STORE = "el => { window.__snap = JSON.stringify(el.__weave.snapshot()); }"
SAME_AS_STORED = "el => JSON.stringify(el.__weave.snapshot()) === window.__snap"


def sweep(page, points=10):
    box = page.locator("[data-hero]").bounding_box()
    for i in range(points):
        t = (i + 0.5) / points
        page.mouse.move(box["x"] + box["width"] * t, box["y"] + box["height"] * (0.2 + 0.6 * t))
        page.wait_for_timeout(30)


@pytest.mark.parametrize("rest", [True, False])
def test_pose_rest_is_still_but_not_paused(make_page, base_url, rest):
    """D34: the rest pose holds the quilt still while the loop runs; without it (the control) the same sweep moves it."""
    page, errors = open_live(make_page, base_url, query="?pose=rest&nowatchdog" if rest else "?nowatchdog")
    sweep(page)
    page.eval_on_selector("[data-hero]", STORE)
    before = frames(page)
    page.wait_for_timeout(1000)
    assert frames(page) > before
    assert page.eval_on_selector("[data-hero]", SAME_AS_STORED) is rest
    assert errors == []


def test_pose_rest_still_falls_back_when_slow(make_page, base_url):
    page = make_page()
    page.goto(f"{base_url}{HOME}?pose=rest&watchdogLimitMs=0")
    wait_for_reason(page, "too-slow")
    assert hero_result(page) == ["still", "too-slow"]


def test_rest_pose_recipe_fills_the_viewport(make_page, base_url):
    """D19 / U7: the capture recipe gives a 1600 x 1000 quilt and nothing else, with no scrollbar."""
    page, errors = open_live(make_page, base_url, query="?pose=rest&frame=still&nowatchdog",
                             viewport={"width": 1600, "height": 1000}, device_scale_factor=1)
    page.wait_for_timeout(300)
    rect = page.eval_on_selector("[data-hero]", "el => { const r = el.getBoundingClientRect(); return [r.x, r.y, r.width, r.height]; }")
    assert rect == [0, 0, 1600, 1000]
    assert page.eval_on_selector("[data-hero] canvas", "c => [c.width, c.height]") == [1600, 1000]
    for selector in (".site-header", "[data-controls]", "#panels", ".why", ".site-footer"):
        assert page.locator(selector).count() == 1 and not page.locator(selector).is_visible(), selector
    hits = page.evaluate("""() => [0.1, 0.5, 0.9].flatMap((fx) => [0.1, 0.5, 0.9].map((fy) =>
        !!document.elementFromPoint(innerWidth * fx, innerHeight * fy)?.closest('[data-hero]')))""")
    assert hits == [True] * 9
    assert page.evaluate("[innerWidth === document.documentElement.clientWidth,"
                         " innerHeight === document.documentElement.clientHeight]") == [True, True]
    assert errors == []


def test_page_snapshot_at_rest_is_quilt_space(make_page, base_url):
    page, _ = open_live(make_page, base_url, query="?pose=rest&nowatchdog")
    r = page.eval_on_selector("[data-hero]", r"""el => {
        const snap = el.__weave.snapshot();
        return { roundTrip: JSON.stringify(JSON.parse(JSON.stringify(snap))) === JSON.stringify(snap),
                 blocks: snap.blocks.length, rod: Object.keys(snap.rod).sort(), shadow: Object.keys(snap.shadow).sort(),
                 aspect: snap.camera.aspect };
    }""")
    assert r["roundTrip"] is True and r["blocks"] == 12
    assert r["rod"] == ["end", "radius", "start"] and r["shadow"] == ["height", "position", "quaternion", "width"]
    assert abs(r["aspect"] - 1.6) < 0.01


# One snapshot and its projections in a single task, so no frame moves the quilt in between: the 48 block corners
# and the rod ends +- capRadius along y and z, the rod ends' z spread (the rod lies on the sway axis, so only the
# pointer's turn about y separates them), and every block z.
CORNERS = r"""el => {
    const w = el.__weave;
    const snap = w.snapshot();
    const LAYOUT_CAP = %s;
    const points = [];
    for (const b of snap.blocks) for (const j of [0, 40, 1640, 1680]) points.push(b.positions.slice(3 * j, 3 * j + 3));
    for (const end of [snap.rod.start, snap.rod.end]) {
      for (const [dy, dz] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) points.push([end[0], end[1] + dy * LAYOUT_CAP, end[2] + dz * LAYOUT_CAP]);
    }
    const r = el.querySelector('canvas').getBoundingClientRect();
    const outside = points.map((p) => w.project(p)).filter(([x, y]) => !(x >= r.left && x <= r.right && y >= r.top && y <= r.bottom));
    let lowest = Infinity;
    for (const b of snap.blocks) for (let j = 2; j < b.positions.length; j += 3) lowest = Math.min(lowest, b.positions[j]);
    return { count: points.length, outside, spread: Math.abs(snap.rod.start[2] - snap.rod.end[2]), lowest, shadowZ: snap.shadow.position[2] };
}"""


@pytest.mark.parametrize("case", ["rest", "pointer"])
@pytest.mark.parametrize("size", [(1440, 900), (1024, 768)], ids=["1440x900", "1024x768"])
def test_corners_stay_in_the_canvas(make_page, base_url, size, case):
    page, errors = open_live(make_page, base_url, query="?pose=rest&nowatchdog" if case == "rest" else "?nowatchdog",
                             viewport={"width": size[0], "height": size[1]})
    cap = page.evaluate("import('/public/js/layout.js').then((L) => L.LAYOUT.rod.capRadius)")
    if case == "pointer":
        box = page.locator("[data-hero]").bounding_box()
        page.mouse.move(box["x"] + 1, box["y"] + 1)
        page.wait_for_timeout(3000)
    r = page.eval_on_selector("[data-hero]", CORNERS % cap)
    assert r["count"] == 56
    if case == "pointer":
        assert r["spread"] > 0.05  # precondition: the pointer tilt really turned the quilt
        assert r["lowest"] > r["shadowZ"]
    else:
        assert r["spread"] < 1e-9
    assert r["outside"] == []
    assert errors == []
