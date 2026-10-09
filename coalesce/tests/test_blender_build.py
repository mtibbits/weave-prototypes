import json
import struct
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "blender"))
import coalesce_layout as L  # noqa: E402

WEB_MESHES = {"Person", "MagnifierRim", "MagnifierCollar", "MagnifierHandle"}


def run_build(blender_exe, *extra, timeout=900):
    cmd = [blender_exe, "-b", "--factory-startup", "--python-exit-code", "1",
           "--python", str(ROOT / "blender" / "build_coalesce.py"), "--", *extra]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def glb_json(path):
    data = Path(path).read_bytes()
    magic, version, length = struct.unpack_from("<4sII", data, 0)
    assert magic == b"glTF" and version == 2 and length == len(data)
    chunk_length, chunk_type = struct.unpack_from("<I4s", data, 12)
    assert chunk_type == b"JSON"
    return json.loads(data[20:20 + chunk_length])


def webp_size(path):
    data = Path(path).read_bytes()
    assert data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    kind = data[12:16]
    if kind == b"VP8X":
        return 1 + int.from_bytes(data[24:27], "little"), 1 + int.from_bytes(data[27:30], "little")
    if kind == b"VP8 ":
        w, h = struct.unpack_from("<HH", data, 26)
        return w & 0x3FFF, h & 0x3FFF
    if kind == b"VP8L":
        bits = int.from_bytes(data[21:25], "little")
        return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
    raise AssertionError(f"unknown WebP chunk {kind!r}")


def output_of(result):
    return result.stdout[-4000:] + result.stderr[-4000:]


@pytest.mark.slow
def test_build_exports_pieces_and_layout(blender_exe, tmp_path):
    result = run_build(blender_exe, "--out", str(tmp_path), "--blend", str(tmp_path / "c.blend"))
    assert result.returncode == 0, output_of(result)
    assert "BUILD OK" in result.stdout
    line = next(l for l in result.stdout.splitlines() if l.startswith("SELFCHECK {"))
    triangles = json.loads(line.split(" ", 1)[1])
    assert WEB_MESHES <= set(triangles)
    assert triangles["Person"] <= 900
    glb = tmp_path / "coalesce.glb"
    assert glb.stat().st_size <= 150_000
    assert WEB_MESHES <= {node.get("name") for node in glb_json(glb)["nodes"]}
    layout = json.loads((tmp_path / "layout.json").read_text(encoding="utf-8"))
    assert layout["people"] == L.layout_document()["people"]
    assert layout["blender"].startswith("5.2")
    assert (tmp_path / "c.blend").is_file()


@pytest.mark.stills
def test_stills_render_at_size_within_budget(blender_exe, tmp_path):
    result = run_build(blender_exe, "--out", str(tmp_path), "--blend", str(tmp_path / "c.blend"),
                       "--stills", "--samples", "8", timeout=1800)
    assert result.returncode == 0, output_of(result)
    for name in ("home-still.webp", "help-still.webp"):
        assert webp_size(tmp_path / name) == (1400, 1080), name
        assert (tmp_path / name).stat().st_size <= 250_000, name
