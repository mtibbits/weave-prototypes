import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "blender"))
import blazeahead_layout as L  # noqa: E402

W = L.build_world()


def dist(a, b):
    n = min(len(a), len(b))
    return math.dist(a[:n], b[:n])


def test_deterministic():
    assert L.to_web(L.build_world()) == L.to_web(W)


def test_four_stops_in_order_about_24_m_apart_along_the_path():
    assert [s["id"] for s in W["stops"]] == L.STOP_IDS
    path = L.Spline(W["path"])
    ss = [path.nearest(*s["origin"][:2])[0] for s in W["stops"]]
    gaps = [b - a for a, b in zip(ss, ss[1:])]
    assert all(18 <= g <= 32 for g in gaps), gaps


def test_views_face_their_vignettes_and_stand_off_the_path():
    path = L.Spline(W["path"])
    for s in W["stops"]:
        v = s["view"]
        _, d_cam = path.nearest(*v["position"][:2])
        assert 1.8 <= d_cam <= 3.4, (s["id"], d_cam)
        to_target = [t - p for t, p in zip(v["target"], v["position"])]
        to_vig = [g - p for g, p in zip(s["vignette"], v["position"])]
        cosang = (to_target[0] * to_vig[0] + to_target[1] * to_vig[1]) / (
            math.hypot(*to_target[:2]) * math.hypot(*to_vig[:2]))
        assert cosang > 0.9, (s["id"], cosang)


def test_edge_signs_sit_at_the_left_and_right_edges_of_each_stop_view():
    for s in W["stops"]:
        xl = L.screen_x(s["view"], s["signs"]["left"]["board"], aspect=16 / 9)
        xr = L.screen_x(s["view"], s["signs"]["right"]["board"], aspect=16 / 9)
        assert 0.03 <= xl <= 0.2 and 0.8 <= xr <= 0.97, (s["id"], xl, xr)


def test_edge_signs_name_the_previous_and_next_topics():
    keys = [(s["signs"]["left"]["label"], s["signs"]["right"]["label"]) for s in W["stops"]]
    assert keys == [("trailhead", "scaffolding"), ("continuity", "knowledge"), ("scaffolding", "in-flight"),
                    ("knowledge", "download")]


def test_walks_start_and_end_on_their_views():
    views = [W["trailhead"]["view"]] + [s["view"] for s in W["stops"]]
    assert len(W["walks"]) == 4 and W["walks"][0]["from"] == "trailhead"
    for walk, a, b in zip(W["walks"], views, views[1:]):
        assert dist(walk["points"][0], a["position"]) < 1e-6 and dist(walk["points"][-1], b["position"]) < 1e-6
        assert len(walk["points"]) == len(walk["targets"])
        assert all(dist(p, q) < 6.0 for p, q in zip(walk["points"], walk["points"][1:]))


def test_nothing_grows_on_the_path_in_the_stream_or_in_clearings():
    path = L.Spline(W["path"])
    stream = L.Spline(W["props"]["stream"]["centerline"])
    for name, items in W["instances"].items():
        if name.startswith(("Canopy", "Post", "Board", "Torch")):
            continue
        for it in items:
            overhead = it[2] - W["terrain"].h(it[0], it[1]) > 1.5    # branches arching over the path are fine
            if not overhead:
                _, d = path.nearest(it[0], it[1])
                assert d > 0.45, (name, it[:3])
                _, ds = stream.nearest(it[0], it[1])
                assert ds > 1.5, (name, it[:3], ds)
            for (cx, cy), r in W["clearings"]:
                assert math.hypot(it[0] - cx, it[1] - cy) >= r - 1e-9, (name, it[:3])


def test_stream_stays_clear_of_the_path():
    path = L.Spline(W["path"])
    for x, y in W["props"]["stream"]["centerline"]:
        assert path.nearest(x, y)[1] > 3.0


def test_baked_tints_are_bounded_and_torches_warm_their_surroundings():
    tx, ty, tz = W["torches"][0]["pos"]
    near = L.light_at(tx + 0.6, ty, tz - 1.0, 0, 0, 1, W["sources"])
    far = L.light_at(tx + 200.0, ty + 200.0, 0.0, 0, 0, 1, W["sources"])
    assert near[0] > far[0] * 3 and near[0] > near[2]
    for items in W["instances"].values():
        for it in items:
            assert all(0.0 <= c <= 4.0 for c in it[10:13])


def test_web_json_is_y_up_and_within_budget():
    web = L.to_web(W)
    x, y, z = W["torches"][0]["pos"]
    assert web["torches"][0]["pos"] == [round(x, 3), round(z, 3), round(-y, 3)]
    assert len(json.dumps(web, separators=(",", ":"))) < 900_000
    assert [s["id"] for s in web["stops"]] == L.STOP_IDS
    for box in (b for s in web["stillSigns"].values() for k, b in s.items() if k != "board"):
        assert 0.0 <= box[0] < box[2] <= 1.0 and 0.0 <= box[1] < box[3] <= 1.0, box


def test_junction_has_three_boards_and_three_branches():
    J = L.build_junction()
    assert [b["key"] for b in J["junction"]["boards"]] == ["left", "right", "ahead"]
    assert len([k for k in J["flows"] if k.startswith("branch")]) == 3
    web = L.to_web(J)
    assert set(web["views"]) == {"junction"}


# centre heights of the props each stop is about, as the Blender build makes them (rack board, map, launch board)
PROP_CENTRES = {"scaffolding": ("rack", 1.02), "knowledge": ("kiosk", 1.35), "in-flight": ("board", 1.25)}


def test_each_stops_prop_sits_above_the_tour_card():
    """The tour card covers about the bottom 40 % of a stop view; the prop the stop is about must clear it."""
    for s in W["stops"]:
        if s["id"] not in PROP_CENTRES:
            continue
        name, h = PROP_CENTRES[s["id"]]
        x, y, z = W["props"][name]["pos"]
        assert L.screen_xy(s["view"], (x, y, z + h))[1] <= 0.55, s["id"]


def test_the_lights_taking_flight_stay_in_view_for_a_stretch():
    view = next(s["view"] for s in W["stops"] if s["id"] == "in-flight")
    seen = [p for p in W["flows"]["flight"] if 0.0 <= L.screen_xy(view, p)[0] <= 1.0
            and 0.03 <= L.screen_xy(view, p)[1] <= 1.0]
    assert len(seen) >= 12, len(seen)


ROOT = Path(__file__).resolve().parents[1]


def test_the_stills_take_their_sign_words_from_the_owners_tour_file():
    text = (ROOT / "public" / "tour-content.js").read_text(encoding="utf-8")
    assert L.read_tour_signs(text) == L.DEFAULT_SIGNS
    renamed = text.replace("sign: 'Knowledge'", "sign: 'Maps'").replace("tourSign: 'The tour'", 'tourSign: "Walk it"')
    words = L.read_tour_signs(renamed)
    assert (words["knowledge"], words["tour"], words["in-flight"]) == ("Maps", "Walk it", "In Flight")


def test_a_stop_without_a_sign_keeps_its_own_word_and_the_rest_stay_in_order():
    words = L.read_tour_signs("window.BLAZEAHEAD_TOUR = { stops: [ { sign: 'Stream' }, { title: 'x' }, "
                              "{ sign: '  ' }, { sign: 'Qu' + 'eue' } ], help: { signs: { ahead: 'Walk' } } };")
    assert [words[k] for k in L.STOP_IDS] == ["Stream", "Scaffolding", "Knowledge", "Queue"]
    assert (words["left"], words["ahead"]) == ("Issues", "Walk")


def test_an_unreadable_tour_file_keeps_the_shipped_words():
    for broken in ("", "window.BLAZEAHEAD_TOUR = { stops: [ { sign: ", "window.BLAZEAHEAD_TOUR = 5;"):
        assert L.read_tour_signs(broken) == L.DEFAULT_SIGNS


def test_the_shipped_sign_words_match_the_live_sites_defaults():
    text = (ROOT / "public" / "js" / "content.js").read_text(encoding="utf-8")
    assert L.read_tour_signs(text, name="DEFAULT_TOUR") == L.DEFAULT_SIGNS
    # and that comparison really read the file: a changed word shows up
    assert L.read_tour_signs(text.replace("sign: 'Download'", "sign: 'Get it'"), name="DEFAULT_TOUR")["download"] == "Get it"


def test_the_kiosk_board_is_exported_for_the_live_map():
    web = L.to_web(W)
    b = web["props"]["kioskBoard"]
    assert b["size"] == [1.38, 0.88] and b["grid"] == [9, 6] and len(b["light"]) == 54
    assert all(0.0 < c <= 4.0 for rgb in b["light"] for c in rgb)
    r, u, n = b["right"], b["up"], b["normal"]
    assert abs(sum(x * y for x, y in zip(r, u))) < 1e-3
    cross = [r[1] * u[2] - r[2] * u[1], r[2] * u[0] - r[0] * u[2], r[0] * u[1] - r[1] * u[0]]
    assert all(abs(a - c) < 1e-3 for a, c in zip(cross, n))
    cam = web["views"]["knowledge"]["position"]
    assert sum((c - p) * q for c, p, q in zip(cam, b["centre"], n)) > 0      # it faces the knowledge view
    top = sum(rgb[0] for rgb in b["light"][:9]) / 9
    bottom = sum(rgb[0] for rgb in b["light"][-9:]) / 9
    assert top > bottom                                                       # the two lanterns hang above it


def test_the_still_knows_where_the_kiosk_board_is():
    corners = L.to_web(W)["stillSigns"]["knowledge"]["board"]
    assert len(corners) == 4 and all(0.0 < v < 1.0 for c in corners for v in c)
    tl, tr, br, bl = corners
    assert tl[0] < tr[0] and bl[0] < br[0] and tl[1] < bl[1] and tr[1] < br[1]
    assert 0.15 < tr[0] - tl[0] < 0.5 and tl[1] < 0.5
