import json
import struct
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = ["Trunk0", "Branch", "Clump0", "Canopy0", "Fern0", "Rock0", "Post", "Board", "TorchStaff", "TorchCup",
            "FlameOuter", "FlameMid", "FlameInner", "Crystal", "Tent", "TentDoor", "Rack", "Key", "Kiosk",
            "KioskMap", "LaunchBoard", "Tag", "TagLit", "Ground", "Water", "Foam", "JunctionGround"]


def glb_json(path):
    data = path.read_bytes()
    assert data[:4] == b"glTF"
    length, kind = struct.unpack("<I4s", data[12:20])
    assert kind == b"JSON"
    return json.loads(data[20:20 + length])


def node_colors(path, name):
    """The baked vertex colours (linear RGB) of one named node's mesh."""
    data = path.read_bytes()
    gltf = glb_json(path)
    json_len = struct.unpack("<I", data[12:16])[0]
    bin_start = 20 + json_len + 8
    node = next(n for n in gltf["nodes"] if n.get("name") == name)
    colors = []
    for prim in gltf["meshes"][node["mesh"]]["primitives"]:
        acc = gltf["accessors"][prim["attributes"]["COLOR_0"]]
        view = gltf["bufferViews"][acc["bufferView"]]
        width = {"VEC3": 3, "VEC4": 4}[acc["type"]]
        fmt, size, scale = {5126: ("f", 4, 1.0), 5123: ("H", 2, 65535.0), 5121: ("B", 1, 255.0)}[acc["componentType"]]
        stride = view.get("byteStride", width * size)
        start = bin_start + view.get("byteOffset", 0) + acc.get("byteOffset", 0)
        for i in range(acc["count"]):
            vals = struct.unpack_from(f"<{width}{fmt}", data, start + i * stride)
            colors.append(tuple(v / scale for v in vals[:3]))
    return colors


def luminance(rgb):
    return 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]


def run_build(blender_exe, out, *extra):
    return subprocess.run([blender_exe, "-b", "--factory-startup", "--python-exit-code", "1", "--python",
                           str(ROOT / "blender/build_blazeahead.py"), "--", "--out", str(out),
                           "--blend", str(out / "w.blend"), *extra],
                          capture_output=True, text=True, timeout=3600)


@pytest.fixture(scope="module")
def built(blender_exe, tmp_path_factory):
    """One Blender build shared by the slow tests below, given an owner's tour file with one sign renamed."""
    out_dir = tmp_path_factory.mktemp("build")
    tour = out_dir / "tour-content.js"
    tour.write_text((ROOT / "public" / "tour-content.js").read_text(encoding="utf-8")
                    .replace("sign: 'Knowledge'", "sign: 'Maps'"), encoding="utf-8")
    out = run_build(blender_exe, out_dir, "--tour", str(tour))
    assert out.returncode == 0, out.stdout[-3000:] + out.stderr[-3000:]
    return out_dir, out


@pytest.mark.slow
def test_the_stills_paint_the_owners_sign_words(built):
    line = next(ln for ln in built[1].stdout.splitlines() if ln.startswith("SIGNS "))
    words = json.loads(line[len("SIGNS "):])
    assert words["knowledge"] == "Maps" and words["in-flight"] == "In Flight", words


@pytest.mark.slow
def test_blender_build_exports_the_world(built):
    tmp_path, out = built
    assert "SELFCHECK" in out.stdout and "BUILD OK" in out.stdout
    glb = tmp_path / "blazeahead.glb"
    assert glb.stat().st_size <= 600_000, glb.stat().st_size
    gltf = glb_json(glb)
    names = {n.get("name") for n in gltf["nodes"]}
    assert set(REQUIRED) <= names, set(REQUIRED) - names
    # every mesh carries baked colour and nothing the browser doesn't use
    for mesh in gltf["meshes"]:
        for prim in mesh["primitives"]:
            assert "COLOR_0" in prim["attributes"], mesh["name"]
            assert "NORMAL" not in prim["attributes"], mesh["name"]
    world = json.loads((tmp_path / "world.json").read_text())
    assert world["version"] == 1
    assert [s["id"] for s in world["stops"]] == ["continuity", "scaffolding", "knowledge", "in-flight"]
    assert {i["mesh"] for i in world["instances"]} <= names
    assert (tmp_path / "world.json").stat().st_size <= 900_000
    junction = json.loads((tmp_path / "junction.json").read_text())
    assert [b["key"] for b in junction["junction"]["boards"]] == ["left", "right", "ahead"]
    assert {i["mesh"] for i in junction["instances"]} <= names
    assert set(world["props"]["kioskBoard"]) >= {"centre", "right", "up", "normal", "size", "grid", "light"}
    assert not [lb for lb in world.get("labels", []) if (lb.get("key") or "").startswith("map:")]
    signs = json.loads((tmp_path / "still-signs.json").read_text())
    assert len(signs["knowledge"]["board"]) == 4


@pytest.mark.slow
def test_the_tent_glows_from_inside_at_night(built):
    """Its canvas takes lantern and torch light from outside but stays well below its lit doorway."""
    glb = built[0] / "blazeahead.glb"
    walls = max(luminance(c) for c in node_colors(glb, "Tent"))
    door = min(luminance(c) for c in node_colors(glb, "TentDoor"))
    assert walls <= 0.5 * door, (walls, door)


VIEWS = ["trailhead", "continuity", "scaffolding", "knowledge", "in-flight", "junction"]


def webp_size(path):
    data = path.read_bytes()
    assert data[:4] == b"RIFF" and data[8:12] == b"WEBP", path
    kind = data[12:16]
    if kind == b"VP8X":
        return (int.from_bytes(data[24:27], "little") + 1, int.from_bytes(data[27:30], "little") + 1)
    if kind == b"VP8 ":
        return (int.from_bytes(data[26:28], "little") & 0x3FFF, int.from_bytes(data[28:30], "little") & 0x3FFF)
    if kind == b"VP8L":
        bits = int.from_bytes(data[21:25], "little")
        return ((bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1)
    raise AssertionError(f"unknown WebP chunk {kind!r}")


@pytest.mark.stills
def test_stills_render_every_view(blender_exe, tmp_path):
    out = run_build(blender_exe, tmp_path, "--stills", "--samples", "8")
    assert out.returncode == 0, out.stdout[-3000:] + out.stderr[-3000:]
    for name in VIEWS:
        still = tmp_path / "stills" / f"{name}.webp"
        assert still.is_file(), name
        assert still.stat().st_size <= 300_000, (name, still.stat().st_size)
        assert webp_size(still) == (1600, 900), name
