"""spool.js: the Help corner's coded spool (#18): its children, frame and size, its thread colour and its header, which
E4's #22 builds on."""
import re
from pathlib import Path

import pytest

SPOOL = Path(__file__).resolve().parents[1] / "public" / "js" / "spool.js"

SPOOL_JS = "const THREE = await import('three'); const S = await import('/public/js/spool.js');"


def test_create_spool_has_spool_and_thread_children(js):
    """AC 13: exactly two children, named as E4's modelled Spool and SpoolThread map onto them."""
    r = js(SPOOL_JS + "const s = S.createSpool(); return { isObject: s.isObject3D, names: s.children.map((c) => c.name) };")
    assert r == {"isObject": True, "names": ["spool", "thread"]}


def test_spool_bounds_match_its_constants(js):
    """AC 13: the bounding box is SPOOL_HEIGHT tall along +Y and twice SPOOL_FLANGE_RADIUS across x and z, centred on
    the origin, within 1e-3 (float32-safe, Issue-10)."""
    r = js(SPOOL_JS + r"""
        const s = S.createSpool();
        const box = new THREE.Box3().setFromObject(s, true);
        const size = box.getSize(new THREE.Vector3()).toArray();
        const centre = box.getCenter(new THREE.Vector3()).toArray();
        const thread = new THREE.Box3().setFromObject(s.getObjectByName('thread'), true).getSize(new THREE.Vector3()).toArray();
        return { size, centre, thread, H: S.SPOOL_HEIGHT, R: S.SPOOL_FLANGE_RADIUS };
    """)
    h, rad = r["H"], r["R"]
    assert 0.15 <= h <= 0.2 and 0 < rad < h / 2, r
    assert r["size"] == pytest.approx([2 * rad, h, 2 * rad], abs=1e-3), r
    assert r["centre"] == pytest.approx([0, 0, 0], abs=1e-3), r
    # The axis is +Y: the x and z extents match each other, and the height is the y extent.
    assert abs(r["size"][0] - r["size"][2]) < 1e-3 and r["size"][1] > r["size"][0], r
    # The wound thread sits inside the flanges.
    assert r["thread"][0] < 2 * rad and r["thread"][1] < h, r


@pytest.mark.parametrize("options, hex_", [("", "c9a227"), ("{ threadColor: '#3366CC' }", "3366cc")],
                         ids=["default", "blue"])
def test_thread_takes_the_thread_color(js, options, hex_):
    """AC 13: the thread is tinted by threadColor, whose default is the needle tail's #C9A227 (#13)."""
    r = js(SPOOL_JS + f"""
        const s = S.createSpool({options});
        return [s.getObjectByName('thread').material.color.getHexString(), s.getObjectByName('spool').material.color.getHexString()];
    """)
    assert r[0] == hex_
    assert r[1] != hex_  # control: the body is not tinted


def test_importing_spool_builds_nothing(js):
    """The global geometry and material id counters show anything built at import time (test_needle.py's probe)."""
    r = js(r"""
        const THREE = await import('three');
        const probe = () => [new THREE.BufferGeometry().id, new THREE.MeshBasicMaterial().id];
        const before = probe();
        const S = await import('/public/js/spool.js');
        const after = probe();
        S.createSpool();
        const built = probe();
        return { before, after, built };
    """)
    assert r["after"] == [r["before"][0] + 1, r["before"][1] + 1], r
    assert r["built"][0] - r["after"][0] > 1 and r["built"][1] - r["after"][1] > 1, r


def test_spools_share_no_geometry_or_material(js):
    """Each spool owns its parts, so disposing one by traversal never breaks another."""
    r = js(SPOOL_JS + r"""
        const parts = (s) => { const out = []; s.traverse((o) => { if (o.isMesh) out.push(o.geometry.uuid, o.material.uuid); }); return out; };
        return [parts(S.createSpool()), parts(S.createSpool())];
    """)
    assert len(r[0]) == 4 and not set(r[0]) & set(r[1]), r


# --- The header: the frame, the children and the size E4's #22 swaps in behind. ---

HEADER_PHRASES = ("origin", "+Y", "`spool`", "`thread`", "Spool", "SpoolThread", "SPOOL_HEIGHT", "SPOOL_FLANGE_RADIUS",
                  "#C9A227", "scene units", "live-path")


def header_lines(text):
    lines = []
    for line in text.splitlines():
        if not line.startswith("//"):
            break
        lines.append(line)
    return lines


def header_claims(text):
    prose = " ".join(" ".join(re.sub(r"^// ?", "", line) for line in header_lines(text)).split())
    return all(phrase in prose for phrase in HEADER_PHRASES)


def test_spool_js_header_states_frame_children_size():
    """AC 16. Planted controls: the header trimmed to one line, and the header without its frame line."""
    text = SPOOL.read_text(encoding="utf-8")
    assert header_claims(text) is True
    rest = "\n".join(text.splitlines()[len(header_lines(text)):])
    assert header_claims("// Spools.\n" + rest) is False
    lines = text.splitlines()
    frame = [i for i, line in enumerate(header_lines(text)) if "+Y" in line]
    assert len(frame) == 1, frame
    assert header_claims("\n".join(lines[:frame[0]] + lines[frame[0] + 1:])) is False
