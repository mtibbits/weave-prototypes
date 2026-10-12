"""tiles.js: the four face kinds and the dashboard tiles, painted from the shipped panel entries."""
import json

import pytest

from helpers import DEFAULTS_JS

SETUP = DEFAULTS_JS + r"""
    const T = await import('/public/js/tiles.js');
    const F = await import('/public/js/fabric.js');
    const byId = (id) => DEFAULTS.find((p) => p.id === id);
    const fresh = () => F.makeCanvas(512);
    // Every fillText on `canvas` during fn(): { text, font, maxWidth } in call order.
    const texts = (canvas, fn) => {
      const proto = CanvasRenderingContext2D.prototype;
      const original = proto.fillText;
      const calls = [];
      proto.fillText = function (text, x, y, maxWidth) {
        if (this.canvas === canvas) calls.push({ text: String(text), font: this.font, maxWidth: maxWidth ?? null });
        return original.apply(this, arguments);
      };
      try { fn(); } finally { proto.fillText = original; }
      return calls;
    };
    const tileTexts = (entry) => { const c = fresh(); return texts(c, () => T.paintTile(c, entry)).map((t) => t.text); };
    const face = (entry, kind) => { const c = fresh(); T.paintFace(c, entry, kind); return c; };
    const faceHash = (entry, kind) => sha256Canvas(face(entry, kind));
"""


def run(paint_js, body):
    return paint_js(SETUP + body)


def in_order(seq, wanted):
    it = iter(seq)
    return all(any(item == w for item in it) for w in wanted)


def test_live_tile_texts(paint_js):
    drawn = run(paint_js, "return tileTexts(byId('manpower'));")
    assert in_order(drawn, ["248", "assigned", "sample", "Open →"]), drawn
    assert "No sample yet" not in drawn


def test_string_value_and_empty_unit(paint_js):
    drawn, unitless = run(paint_js, r"""
        return [tileTexts(byId('training')), tileTexts({ ...byId('training'), sample: { value: '87%', unit: '' } })];
    """)
    assert in_order(drawn, ["87%", "current", "sample"]), drawn
    assert "87%" in unitless and "" not in unitless and "sample" in unitless, unitless


def test_null_sample_reads_no_sample_yet(paint_js):
    drawn = run(paint_js, "return tileTexts({ ...byId('manpower'), sample: null });")
    assert "No sample yet" in drawn and "248" not in drawn and "sample" not in drawn and "assigned" not in drawn
    assert "Open →" in drawn


def test_no_sample_text_is_the_pages_string(paint_js):
    assert run(paint_js, "return (await import('/public/js/dom.js')).NO_SAMPLE;") == "No sample yet"


def test_planned_tile_reads_coming_soon(paint_js):
    drawn = run(paint_js, "return tileTexts(byId('promotions'));")
    assert "Promotions" in drawn and "Coming soon" in drawn and "Open →" not in drawn, drawn


def test_suggest_tile_reads_suggest_a_panel(paint_js):
    drawn = run(paint_js, "return tileTexts(byId('suggest'));")
    assert "Suggest a panel" in drawn and "Open →" not in drawn, drawn


def test_null_tile_is_cleared(paint_js):
    assert run(paint_js, r"""
        const c = fresh();
        T.paintTile(c, byId('manpower'));
        T.paintTile(c, null);
        return c.getContext('2d').getImageData(0, 0, 512, 512).data.every((v) => v === 0);
    """) is True


def test_tile_corners_are_transparent(paint_js):
    result = run(paint_js, r"""
        return ['manpower', 'promotions', 'suggest'].map((id) => {
          const c = fresh();
          T.paintTile(c, byId(id));
          const ctx = c.getContext('2d');
          return [ctx.getImageData(1, 1, 1, 1).data[3], ctx.getImageData(256, 256, 1, 1).data[3]];
        });
    """)
    assert result == [[0, 255]] * 3


def test_tile_bars_are_seeded_from_the_id(paint_js):
    result = run(paint_js, r"""
        // Every fillRect on the tile canvas itself: the tile draws only its bars with fillRect.
        const rects = (entry) => {
          const c = fresh();
          const proto = CanvasRenderingContext2D.prototype;
          const original = proto.fillRect;
          const heights = [];
          proto.fillRect = function (x, y, w, h) {
            if (this.canvas === c) heights.push(h);
            return original.apply(this, arguments);
          };
          try { T.paintTile(c, entry); } finally { proto.fillRect = original; }
          return heights;
        };
        const m = byId('manpower');
        return { again: T.barHeights('manpower'), first: T.barHeights('manpower'), other: T.barHeights('hiring'),
                 drawn: rects(m), noSample: rects({ ...m, sample: null }), otherValue: rects({ ...m, sample: { value: 1, unit: 'x' } }) };
    """)
    assert result["again"] == result["first"] and result["first"] != result["other"]
    assert len(result["first"]) >= 5
    ratios = [d / b for d, b in zip(result["drawn"], result["first"])]
    assert len(result["drawn"]) == len(result["first"]) and max(ratios) - min(ratios) < 1e-9, result
    assert result["noSample"] == result["drawn"] == result["otherValue"]


def test_filler_face_is_paint_fabric_muslin_filler(paint_js):
    same = run(paint_js, r"""
        const a = face(null, 'filler');
        const b = fresh();
        F.paintFabric(b, 'muslin', 'filler');
        return [await sha256Canvas(a) === await sha256Canvas(b), isUniform(a)];
    """)
    assert same == [True, False]


@pytest.mark.parametrize("kind", ["sewn", "planned"])
def test_null_entry_paints_as_filler(paint_js, kind):
    assert run(paint_js, f"return await faceHash(null, '{kind}') === await faceHash(null, 'filler');") is True


def test_unknown_kind_paints_as_filler(paint_js):
    assert run(paint_js, "return await faceHash(byId('manpower'), 'quilted') === await faceHash(null, 'filler');")


ICON_CASES = {"nope": "'nope'", "absent": None, "7": "7", "toString": "'toString'", "__proto__": "'__proto__'"}


@pytest.mark.parametrize("case", list(ICON_CASES))
@pytest.mark.parametrize("kind", ["sewn", "planned"])
def test_unknown_icon_face_matches_the_fallback(paint_js, case, kind):
    value = ICON_CASES[case]
    entry = "(() => { const e = { ...byId('access') }; delete e.icon; return e; })()" if value is None \
        else f"{{ ...byId('access'), icon: {value} }}"
    assert run(paint_js, f"""
        return await faceHash({entry}, '{kind}') === await faceHash({{ ...byId('access'), icon: 'fallback' }}, '{kind}');
    """) is True


FABRIC_CASES = {"nope": "'nope'", "absent": None, "constructor": "'constructor'"}


@pytest.mark.parametrize("case", list(FABRIC_CASES))
@pytest.mark.parametrize("kind", ["sewn", "planned"])
def test_unknown_fabric_face_matches_muslin(paint_js, case, kind):
    value = FABRIC_CASES[case]
    entry = "(() => { const e = { ...byId('access') }; delete e.fabric; return e; })()" if value is None \
        else f"{{ ...byId('access'), fabric: {value} }}"
    assert run(paint_js, f"""
        return await faceHash({entry}, '{kind}') === await faceHash({{ ...byId('access'), fabric: 'muslin' }}, '{kind}');
    """) is True


def test_known_icon_fabric_and_kind_change_the_face(paint_js):
    result = run(paint_js, r"""
        const a = byId('access');
        const kinds = await Promise.all(['sewn', 'planned', 'suggest'].map((k) => faceHash(a, k)));
        const fonts = (entry, kind) => { const c = fresh(); return texts(c, () => T.paintFace(c, entry, kind)); };
        return {
          icon: await faceHash(a, 'sewn') !== await faceHash({ ...a, icon: 'fallback' }, 'sewn'),
          fabric: await faceHash(a, 'sewn') !== await faceHash({ ...a, fabric: 'muslin' }, 'sewn'),
          kinds: new Set(kinds).size,
          uniform: ['sewn', 'planned', 'suggest'].some((k) => isUniform(face(a, k))),
          runs: [...fonts(a, 'sewn'), ...fonts(a, 'planned'), ...fonts(byId('suggest'), 'suggest')],
        };
    """)
    assert result["icon"] and result["fabric"] and result["kinds"] == 3 and not result["uniform"]
    runs = result["runs"]
    texts = [r["text"] for r in runs]
    assert {"Building", "Access", "coming soon", "?", "Suggest a panel"} <= set(texts), texts
    for r in runs:
        if r["text"] == "?":
            assert "italic" in r["font"] and "Instrument Serif" in r["font"], r
        else:
            # Chromium reads weight 700 back as "bold".
            assert r["font"].startswith(("bold ", "700 ")) and "Instrument Sans" in r["font"], r


def test_face_name_uses_the_rule(paint_js):
    drawn = run(paint_js, r"""
        const c = fresh();
        return texts(c, () => T.paintFace(c, byId('actions'), 'sewn')).map((t) => t.text);
    """)
    assert "Action" in drawn and "Tracking" in drawn and "Action Tracking" not in drawn, drawn


def test_a_name_at_the_floor_is_drawn_compressed_into_its_width(paint_js):
    name = "W" * 60
    calls = run(paint_js, f"""
        const c = fresh();
        return texts(c, () => T.paintFace(c, {{ ...byId('manpower'), name: {json.dumps(name)} }}, 'sewn'));
    """)
    run_ = next(r for r in calls if r["text"] == name)
    assert " 12px " in run_["font"] and run_["maxWidth"] == pytest.approx(0.6 * 512), run_
    others = [r for r in calls if r["text"] != name]
    assert all(r["maxWidth"] is None for r in others), others


def test_face_kinds_follow_status(paint_js):
    result = run(paint_js, r"""
        return [T.FACE_KINDS, DEFAULTS.map(T.faceKind), T.faceKind(null), T.faceKind({ status: 'archived' })];
    """)
    kinds, defaults, null_kind, unknown = result
    assert kinds == ["sewn", "planned", "suggest", "filler"]
    assert defaults == ["sewn", "sewn", "sewn", "sewn", "planned", "sewn", "planned", "sewn", "planned", "planned",
                        "sewn", "suggest"]
    assert null_kind == "filler" and unknown == "filler"


def test_face_repaint_is_byte_identical(paint_js):
    hashes = run(paint_js, r"""
        const c = fresh();
        T.paintFace(c, byId('manpower'), 'sewn');
        const first = await sha256Canvas(c);
        T.paintTile(c, byId('hiring'));
        T.paintFace(c, byId('manpower'), 'sewn');
        return [first, await sha256Canvas(c), await faceHash(byId('manpower'), 'sewn')];
    """)
    assert len(set(hashes)) == 1
