"""weave/dev/faces.html: the dev-only review page that paints every block face, tile and texture."""
from pathlib import Path

from helpers import E1, W_MANY, font_warnings, open_faces

PANELS = Path(__file__).resolve().parents[1] / "public" / "panels.js"
DEFAULT_IDS = ["manpower", "hiring", "training", "awards", "promotions", "travel", "feedback", "actions",
               "oversight", "access", "desks", "suggest"]
DEFAULT_KINDS = ["sewn", "sewn", "sewn", "sewn", "planned", "sewn", "planned", "sewn", "planned", "planned", "sewn",
                 "suggest"]

CANVASES = r"""() => [...document.querySelectorAll('canvas')].map((c) => ({
    slot: c.getAttribute('data-slot'), id: c.getAttribute('data-id'), kind: c.getAttribute('data-kind'),
    texture: c.getAttribute('data-texture'), size: [c.width, c.height],
    soft: c.getContext('2d').getContextAttributes().willReadFrequently }))"""
FACE_SELECTOR = 'canvas[data-slot]:not([data-kind="tile"])'


def panels_with(extra):
    return PANELS.read_text(encoding="utf-8") + "\n" + extra


def canvases(page):
    found = page.evaluate(CANVASES)
    faces = [c for c in found if c["slot"] is not None and c["kind"] != "tile"]
    tiles = [c for c in found if c["kind"] == "tile"]
    textures = [c for c in found if c["texture"] is not None]
    return found, faces, tiles, textures


def test_default_faces_page(make_page, base_url):
    messages = []
    page, errors = open_faces(make_page, base_url, messages=messages)
    found, faces, tiles, textures = canvases(page)
    assert errors == []
    assert [f["slot"] for f in faces] == [str(i) for i in range(12)]
    assert [f["id"] for f in faces] == DEFAULT_IDS
    assert [f["kind"] for f in faces] == DEFAULT_KINDS
    assert [(t["slot"], t["id"]) for t in tiles] == [(str(i), i_d) for i, i_d in enumerate(DEFAULT_IDS)]
    assert page.locator(FACE_SELECTOR).count() == 12
    assert sorted(t["texture"] for t in textures) == ["sashing", "shadow", "weave-normal", "wood"]
    assert all(t["slot"] is None for t in textures)
    assert all(c["size"] == [512, 512] for c in faces + tiles)
    assert next(t for t in textures if t["texture"] == "sashing")["size"] == [1204, 912]
    assert len(found) == 28 and all(c["soft"] is True for c in found)
    assert page.get_attribute("body", "data-painted") == "fonts"
    assert font_warnings(messages) == []


def test_ten_entry_panels_file_draws_two_fillers(make_page, base_url):
    body = panels_with("window.WEAVE_PANELS.panels = window.WEAVE_PANELS.panels.slice(0, 10);")
    page, errors = open_faces(make_page, base_url, body)
    _, faces, tiles, _ = canvases(page)
    assert len(faces) == 12 and len(tiles) == 10
    assert [(f["kind"], f["id"]) for f in faces[10:]] == [("filler", ""), ("filler", "")]
    assert errors == []


def test_thirteen_entries_draw_the_first_twelve(make_page, base_url):
    body = panels_with("window.WEAVE_PANELS.panels.push({ id: 'extra', name: 'Extra', status: 'planned', sample: null });")
    messages = []
    page, errors = open_faces(make_page, base_url, body, messages=messages)
    _, faces, tiles, _ = canvases(page)
    assert [f["id"] for f in faces] == DEFAULT_IDS and len(tiles) == 12
    assert [text for kind, text in messages if kind == "warning" and text.startswith("WEAVE: panels.js")] == [
        W_MANY.format(count=13)]
    assert errors == []


def test_broken_panels_file_draws_twelve_fillers(make_page, base_url):
    page, errors = open_faces(make_page, base_url, "window.WEAVE_PANELS = {")
    _, faces, tiles, _ = canvases(page)
    assert [f["kind"] for f in faces] == ["filler"] * 12 and tiles == []
    assert len([e for e in errors if e.startswith("pageerror:")]) == 1
    assert [e for e in errors if e.startswith("console.error:")] == [f"console.error: {E1}"]
    assert len(errors) == 2


# Records every fillText onto its canvas as canvas.__texts, before any page script runs.
RECORD_TEXTS = r"""
    const original = CanvasRenderingContext2D.prototype.fillText;
    CanvasRenderingContext2D.prototype.fillText = function (text, ...rest) {
      (this.canvas.__texts ||= []).push(String(text));
      return original.call(this, text, ...rest);
    };
"""


def test_every_live_tile_number_carries_the_sample_caption(make_page, base_url):
    page, errors = open_faces(make_page, base_url, before_goto=lambda p: p.add_init_script(RECORD_TEXTS))
    tiles = page.evaluate(r"""() => [...document.querySelectorAll('canvas[data-kind="tile"]')].map((c) => {
        const e = window.WEAVE_FACES.entries[Number(c.dataset.slot)];
        return [e.status, e.sample ? String(e.sample.value) : null, c.__texts || []];
    })""")
    checked = 0
    for status, value, texts in tiles:
        if status == "live" and value is not None:
            assert value in texts, (value, texts)
            assert "sample" in texts[texts.index(value) + 1:], (value, texts)
            checked += 1
    assert checked == 7
    assert errors == []
