import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "blender"))
import coalesce_layout as L  # noqa: E402


def test_crowd_size_within_budget():
    assert 150 <= len(L.crowd_positions()) <= 300


def test_people_stand_on_the_front_surface():
    for x, y, z in L.crowd_positions():
        assert y < 0, (x, y, z)
        assert abs(y - L.front_y(x, z + 0.14)) < 1e-3


def test_layout_document_is_deterministic_and_json_ready():
    a = L.layout_document("test")
    assert a == L.layout_document("test")
    json.dumps(a)


def test_accent_share_is_small_and_aligned():
    doc = L.layout_document()
    assert len(doc["accent"]) == len(doc["people"])
    assert 0.02 <= sum(doc["accent"]) / len(doc["accent"]) <= 0.14


def test_web_space_is_y_up_facing_the_camera():
    doc = L.layout_document()
    ys = [p[1] for p in doc["people"]]
    zs = [p[2] for p in doc["people"]]
    assert min(ys) >= 0 and max(ys) < 5.2
    assert min(zs) > 0
    cam = doc["camera"]
    assert cam["position"][2] > 10
    assert 25 < cam["vfovDeg"] < 40
    assert abs(cam["aspect"] - 1400 / 1080) < 1e-3


def test_help_focus_is_near_the_resting_aim():
    positions = L.crowd_positions()
    x, _, z = positions[L.help_focus_index(positions)]
    ax, ay = L.MAGNIFIER["restAim"]
    assert abs(x - ax) < 0.3 and abs(z + 0.14 - ay) < 0.3
