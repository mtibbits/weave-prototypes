import pytest

from helpers import collect_errors, stage_result

TOUR = "/public/tour/index.html"


def open_tour(make_page, base_url, hash_="", **context_args):
    page = make_page(**context_args)
    errors = collect_errors(page)
    page.goto(base_url + TOUR + "?nowatchdog" + hash_)
    assert stage_result(page, timeout=45000) == ["live", "ok"]
    return page, errors


def wait_stop(page, index, timeout=20000):
    page.wait_for_function("(i) => document.body.dataset.tourIndex === String(i)"
                           " && document.body.dataset.tourWalking === 'false'", arg=index, timeout=timeout)


def test_the_tour_walks_from_the_trailhead_to_stop_one(make_page, base_url):
    page, errors = open_tour(make_page, base_url)
    page.wait_for_function("() => document.body.dataset.tourWalking === 'true'", timeout=10000)
    wait_stop(page, 0)
    assert page.locator("[data-card-heading]").inner_text() == "The continuity proxy"
    assert page.evaluate("location.hash") == "#continuity"
    assert not page.locator("[data-tour-card]").get_attribute("data-hidden")
    assert errors == []


def test_mashing_next_during_a_walk_lands_on_one_stop(make_page, base_url):
    page, _ = open_tour(make_page, base_url, "#continuity")
    wait_stop(page, 0)
    page.keyboard.press("ArrowRight")
    page.wait_for_function("() => document.body.dataset.tourWalking === 'true'")
    for _ in range(4):
        page.keyboard.press("ArrowRight")
    page.wait_for_function("() => document.body.dataset.tourWalking === 'false'", timeout=40000)   # two ~9.5 s walks
    index = int(page.eval_on_selector("body", "b => b.dataset.tourIndex"))
    assert index == 2  # the walk to stop 2 finished, then only the latest queued request (one more) ran
    assert page.locator("[data-tour-card]").get_attribute("data-hidden") is None
    assert page.locator("button[data-sign=right]").is_enabled()


@pytest.mark.parametrize("size", [(1024, 768), (2560, 1080)])
def test_sign_buttons_sit_over_the_boards(make_page, base_url, size):
    page, _ = open_tour(make_page, base_url, "#scaffolding", viewport={"width": size[0], "height": size[1]})
    wait_stop(page, 1)
    for side in ("left", "right"):
        board = page.evaluate(f"document.querySelector('[data-stage]').__blaze.signBox('{side}')")
        btn = page.locator(f"button[data-sign={side}]").bounding_box()
        assert board and btn
        assert abs(btn["x"] - max(0, board[0])) < 40 and abs(btn["y"] - board[1]) < 60, (side, board, btn)
        assert btn["x"] >= 0 and btn["x"] + btn["width"] <= size[0], (side, btn)
        assert btn["y"] >= 0 and btn["y"] + btn["height"] <= size[1], (side, btn)


def test_hovering_a_rock_names_the_error_it_stands_for(make_page, base_url):
    page, _ = open_tour(make_page, base_url, "#continuity")
    wait_stop(page, 0)
    found = page.evaluate("""() => {
        const s = document.querySelector('[data-stage]').__blaze;
        const r = s.view.canvas.getBoundingClientRect();
        for (let y = 0.25; y < 0.8; y += 0.02) for (let x = 0.1; x < 0.9; x += 0.02) {
          if (s.view.rockAt(x * 2 - 1, 1 - y * 2)) return [r.left + x * r.width, r.top + y * r.height];
        }
        return null;
    }""")
    assert found, "a rock should be visible from the continuity stop"
    page.mouse.move(found[0], found[1])
    tip = page.locator(".stage-tip")
    tip.wait_for(state="visible", timeout=3000)
    assert "absorbed" in tip.inner_text()


def test_losing_the_gpu_mid_walk_finishes_on_stills(make_page, base_url):
    page, errors = open_tour(make_page, base_url, "#continuity")
    wait_stop(page, 0)
    page.keyboard.press("ArrowRight")
    page.wait_for_function("() => document.body.dataset.tourWalking === 'true'")
    page.evaluate("document.querySelector('[data-stage]').__blaze.stop('context-lost')")
    wait_stop(page, 1)
    assert page.locator("[data-stage] canvas").count() == 0
    src = page.eval_on_selector_all("[data-stage] img.stage-still:not(.is-hidden)", "els => els.map((e) => e.src)")
    assert src and src[0].endswith("/stills/scaffolding.webp")
    page.locator("button[data-sign=right]").click()
    wait_stop(page, 2)
    assert not [e for e in errors if "pageerror" in e]


@pytest.mark.parametrize("size", [(1440, 900), (1024, 768), (800, 900)])
def test_the_pause_button_stays_clear_of_the_trail_map_and_the_card(make_page, base_url, size):
    page, _ = open_tour(make_page, base_url, "#knowledge", viewport={"width": size[0], "height": size[1]})
    wait_stop(page, 2)
    pause = page.locator("[data-pause]")
    assert pause.is_visible()
    a = pause.bounding_box()
    for other in ("[data-trail-map]", "[data-tour-card]"):
        b = page.locator(other).bounding_box()
        apart = (a["x"] + a["width"] <= b["x"] or b["x"] + b["width"] <= a["x"]
                 or a["y"] + a["height"] <= b["y"] or b["y"] + b["height"] <= a["y"])
        assert apart, (other, a, b)


def open_tour_holding_the_world(make_page, base_url, hash_=""):
    """The tour with the 3D world's download held back, as on a slow network. Returns the page and a release()."""
    page = make_page()
    held = []
    page.route("**/assets/blazeahead.glb", lambda route: held.append(route))
    page.goto(base_url + TOUR + "?nowatchdog" + hash_)

    def release():
        for route in held:
            route.continue_()
        page.unroute("**/assets/blazeahead.glb")
    return page, release


def test_a_deep_link_opens_its_stop_before_the_3d_arrives(make_page, base_url):
    page, release = open_tour_holding_the_world(make_page, base_url, "#knowledge")
    wait_stop(page, 2, timeout=5000)
    assert page.locator("[data-card-heading]").inner_text() == "The knowledge base"
    assert page.eval_on_selector("[data-stage]", "el => el.dataset.stageReason") == "loading"
    src = page.eval_on_selector("[data-stage] img.stage-still:not(.is-hidden)", "img => img.getAttribute('src')")
    assert src.endswith("knowledge.webp")
    page.wait_for_function("() => !document.querySelector('button[data-sign=right]').hidden", timeout=5000)
    page.keyboard.press("ArrowRight")
    wait_stop(page, 3)
    release()
    assert stage_result(page, timeout=45000) == ["live", "ok"]
    wait_stop(page, 3)
    assert page.evaluate("document.querySelector('[data-stage]').__blaze.signBox('left')") is not None


def test_a_first_visit_sets_off_on_stills_when_the_3d_is_late(make_page, base_url):
    page, release = open_tour_holding_the_world(make_page, base_url)
    wait_stop(page, 0, timeout=12000)
    assert page.eval_on_selector("[data-stage]", "el => el.dataset.stageReason") == "loading"
    release()
    assert stage_result(page, timeout=45000) == ["live", "ok"]
    page.wait_for_timeout(500)
    assert page.eval_on_selector("body", "b => [b.dataset.tourIndex, b.dataset.tourWalking]") == ["0", "false"]
    assert page.evaluate("document.querySelector('[data-stage]').__blaze.signBox('right')") is not None


BOARD = "document.querySelector('[data-stage]').__blaze.view.board"


def test_the_kiosk_map_lights_the_trail_on_each_card_page(make_page, base_url):
    page, errors = open_tour(make_page, base_url, "#knowledge")
    wait_stop(page, 2)
    page.wait_for_function(f"() => {BOARD} && {BOARD}.draws > 0", timeout=10000)
    assert page.evaluate(f"{BOARD}.focus") is None
    before = page.evaluate(f"{BOARD}.draws")
    page.locator("[data-card-next]").click()
    page.wait_for_function(f"(n) => {BOARD}.draws > n", arg=before)
    assert page.evaluate(f"{BOARD}.focus") == 0
    page.locator("[data-card-prev]").click()
    page.wait_for_function(f"() => {BOARD}.focus === null")
    # the same map with the same trail lit is painted (and uploaded) once, not again
    draws = page.evaluate("""async () => { const v = document.querySelector('[data-stage]').__blaze.view;
        const K = await import('../js/kbmap.js');
        const laid = K.layoutMap(window.__tour.tour.stops[2].map, K.canvasMeasure(document));
        v.paintBoard(laid, 1); const once = v.board.draws; v.paintBoard(laid, 1); return [once, v.board.draws]; }""")
    assert draws[1] == draws[0], draws
    assert errors == []


def test_clicking_the_kiosk_map_unfolds_it(make_page, base_url):
    page, _ = open_tour(make_page, base_url, "#knowledge")
    wait_stop(page, 2)
    page.wait_for_function(f"() => {BOARD} && {BOARD}.draws > 0", timeout=10000)
    xy = page.evaluate("""() => { const v = document.querySelector('[data-stage]').__blaze.view;
        const p = v.board.mesh.position.clone().project(v.camera); const r = v.canvas.getBoundingClientRect();
        return [r.left + (p.x + 1) / 2 * r.width, r.top + (1 - p.y) / 2 * r.height]; }""")
    page.mouse.click(xy[0], xy[1])
    page.wait_for_function("() => document.querySelector('[data-kb-sheet]').open")
    page.keyboard.press("Escape")
    page.wait_for_function("() => !document.querySelector('[data-kb-sheet]').open")
    assert page.evaluate("document.activeElement.hasAttribute('data-card-heading')")
    assert page.evaluate("location.hash") == "#knowledge"
