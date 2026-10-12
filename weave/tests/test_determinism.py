"""Every faces-page canvas is a pure function of its inputs: same bytes on repaint, in a fresh context, and with
Math.random made to throw. (#20 hashes these canvases; hashes compare only within one machine and browser build.)"""
from pathlib import Path

from helpers import canvas_hashes, open_faces, uniform_canvases

PANELS = Path(__file__).resolve().parents[1] / "public" / "panels.js"
TEN = PANELS.read_text(encoding="utf-8") + "\nwindow.WEAVE_PANELS.panels = window.WEAVE_PANELS.panels.slice(0, 10);"


def test_hashes_cover_every_canvas_and_are_distinct(make_page, base_url, faces_baseline):
    page, errors = open_faces(make_page, base_url)
    assert len(faces_baseline) == 28
    assert sum(k.startswith("face:") for k in faces_baseline) == 12
    assert sum(k.startswith("tile:") for k in faces_baseline) == 12
    assert sum(k.startswith("texture:") for k in faces_baseline) == 4
    assert len(set(faces_baseline.values())) == 28
    assert uniform_canvases(page) == []
    assert errors == []


REPAINT = r"""async () => {
    const F = await import('/public/js/fabric.js');
    const T = await import('/public/js/tiles.js');
    const { entries } = window.WEAVE_FACES;
    const GEOMETRY = { cols: 4, rows: 3, block: 1.0, sashing: 0.14, border: 0.14 };
    const hash = async (c) => {
      const digest = new Uint8Array(await crypto.subtle.digest('SHA-256', c.getContext('2d').getImageData(0, 0, c.width, c.height).data));
      return [...digest].map((b) => b.toString(16).padStart(2, '0')).join('');
    };
    const out = {};
    for (let slot = 0; slot < entries.length; slot += 1) {
      const face = F.makeCanvas(512);
      T.paintFace(face, entries[slot], T.faceKind(entries[slot]));
      out[`face:${slot}`] = await hash(face);
      if (entries[slot]) {
        const tile = F.makeCanvas(512);
        T.paintTile(tile, entries[slot]);
        out[`tile:${slot}`] = await hash(tile);
      }
    }
    const textures = { sashing: [...F.sashingSize(GEOMETRY), (c) => F.paintSashing(c, GEOMETRY)],
      wood: [1024, 256, F.paintWood], 'weave-normal': [512, 512, F.paintWeaveNormal], shadow: [512, 512, F.paintShadow] };
    for (const [name, [w, h, paint]] of Object.entries(textures)) {
      const c = F.makeCanvas(w, h);
      paint(c);
      out[`texture:${name}`] = await hash(c);
    }
    return out;
}"""


def test_hashes_repeat_within_one_page(make_page, base_url, faces_baseline):
    page, errors = open_faces(make_page, base_url)
    page.evaluate("() => window.WEAVE_FACES.paintAll()")
    assert canvas_hashes(page) == faces_baseline
    assert page.evaluate(REPAINT) == faces_baseline
    assert errors == []


def test_hashes_match_across_two_fresh_contexts(make_page, base_url, faces_baseline):
    first, _ = open_faces(make_page, base_url)
    second, _ = open_faces(make_page, base_url)
    assert canvas_hashes(first) == canvas_hashes(second) == faces_baseline
    # The filler limb: the two fillers of a 10-entry list, in two contexts.
    a, _ = open_faces(make_page, base_url, TEN)
    b, _ = open_faces(make_page, base_url, TEN)
    ha, hb = canvas_hashes(a), canvas_hashes(b)
    assert ha["face:10"] == hb["face:10"] == ha["face:11"] == hb["face:11"]
    assert ha["face:10"] not in faces_baseline.values()


def test_painters_never_call_math_random(make_page, base_url, faces_baseline):
    throw = "Math.random = () => { throw new Error('WEAVE painters must not call Math.random'); };"
    page, errors = open_faces(make_page, base_url, before_goto=lambda p: p.add_init_script(throw))
    assert errors == []
    assert page.evaluate("() => { try { Math.random(); return false; } catch { return true; } }") is True
    assert canvas_hashes(page) == faces_baseline
