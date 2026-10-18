"""tiles.js: the four face kinds and the dashboard tiles, painted from the shipped panel entries."""
import json

import pytest

from helpers import DEFAULTS_JS

SETUP = DEFAULTS_JS + r"""
    const T = await import('/public/js/tiles.js');
    const F = await import('/public/js/fabric.js');
    const byId = (id) => DEFAULTS.find((p) => p.id === id);
    const fresh = () => F.makeCanvas(512);
    // A design-space box [x0, y0, x1, y1] as the axis-aligned box of its corners in device px.
    const deviceBox = (ctx, [x0, y0, x1, y1]) => {
      const t = ctx.getTransform();
      const pts = [[x0, y0], [x1, y0], [x0, y1], [x1, y1]].map(([x, y]) => t.transformPoint({ x, y }));
      const xs = pts.map((p) => p.x);
      const ys = pts.map((p) => p.y);
      return [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)];
    };
    // Every fillText on `canvas` during fn(): { text, font, maxWidth, box } in call order. box is the text's ink
    // box in device px, from measureText's actual bounds (compressed to maxWidth as fillText draws it).
    const texts = (canvas, fn) => {
      const proto = CanvasRenderingContext2D.prototype;
      const original = proto.fillText;
      const calls = [];
      proto.fillText = function (text, x, y, maxWidth) {
        if (this.canvas === canvas) {
          const m = this.measureText(text);
          const k = maxWidth != null && m.width > maxWidth ? maxWidth / m.width : 1;
          const box = deviceBox(this, [x - m.actualBoundingBoxLeft * k, y - m.actualBoundingBoxAscent,
            x + m.actualBoundingBoxRight * k, y + m.actualBoundingBoxDescent]);
          calls.push({ text: String(text), font: this.font, maxWidth: maxWidth ?? null, box });
        }
        return original.apply(this, arguments);
      };
      try { fn(); } finally { proto.fillText = original; }
      return calls;
    };
    // Every ctx.roundRect on `canvas` during fn(), as its device-px box, in call order.
    const roundRects = (canvas, fn) => {
      const proto = CanvasRenderingContext2D.prototype;
      const original = proto.roundRect;
      const calls = [];
      proto.roundRect = function (x, y, w, h) {
        if (this.canvas === canvas) {
          calls.push(deviceBox(this, [Math.min(x, x + w), Math.min(y, y + h), Math.max(x, x + w), Math.max(y, y + h)]));
        }
        return original.apply(this, arguments);
      };
      try { fn(); } finally { proto.roundRect = original; }
      return calls;
    };
    const tileTexts = (entry, options) => {
      const c = fresh();
      return texts(c, () => T.paintTile(c, entry, options)).map((t) => t.text);
    };
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


def test_face_kind_defaults_to_the_entrys_status(paint_js):
    result = run(paint_js, r"""
        const same = async (id, kind) => await faceHash(byId(id)) === await faceHash(byId(id), kind);
        return [await same('manpower', 'sewn'), await same('promotions', 'planned'), await same('suggest', 'suggest'),
                await faceHash(byId('manpower'), 'bogus') === await faceHash(null, 'filler'), Object.isFrozen(T.FACE_KINDS)];
    """)
    assert result == [True, True, True, True, True]


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


# Context state a caller (#7, #10, #18) might leave behind outside save/restore.
LEFT_BEHIND = {
    "lineCap": "'round'", "lineJoin": "'round'", "miterLimit": "2", "lineWidth": "7", "direction": "'rtl'",
    "letterSpacing": "'2px'", "wordSpacing": "'5px'", "shadowOffsetX": "9", "shadowOffsetY": "9",
    "imageSmoothingEnabled": "false", "fontKerning": "'none'", "fontStretch": "'condensed'",
    "fontVariantCaps": "'small-caps'", "textRendering": "'optimizeSpeed'", "font": "'30px serif'",
}


def test_paints_ignore_state_a_caller_left_behind(paint_js):
    result = paint_js(SETUP + "const LEFT = {" + ", ".join(f"{k}: {v}" for k, v in LEFT_BEHIND.items()) + "};" + r"""
        const dirty = (size) => { const c = F.makeCanvas(size); Object.assign(c.getContext('2d'), LEFT); return c; };
        const paints = {
          face: (c) => T.paintFace(c, byId('actions'), 'sewn'),
          planned: (c) => T.paintFace(c, byId('promotions'), 'planned'),
          tile: (c) => T.paintTile(c, byId('manpower')),
          taggedTile: (c) => T.paintTile(c, byId('travel'), { tagged: true }),
          sashing: (c) => F.paintSashing(c, { cols: 4, rows: 3, block: 1, sashing: 0.14, border: 0.14 }),
          wood: (c) => F.paintWood(c),
        };
        const out = {};
        for (const [name, paint] of Object.entries(paints)) {
          for (const size of [512, 300]) {
            const clean = F.makeCanvas(size), messy = dirty(size);
            paint(clean);
            paint(messy);
            out[`${name}@${size}`] = await sha256Canvas(clean) === await sha256Canvas(messy);
          }
        }
        return out;
    """)
    assert all(result.values()), result


def test_a_caller_clip_is_the_one_state_painters_keep(paint_js):
    """The documented exception to the reset (fabric.js): a clip set outside save/restore confines the paint,
    and one set inside save/restore leaves no trace."""
    result = run(paint_js, r"""
        const clipped = (scoped) => {
          const c = fresh(), ctx = c.getContext('2d');
          if (scoped) ctx.save();
          ctx.beginPath(); ctx.rect(0, 0, 100, 100); ctx.clip();
          if (scoped) ctx.restore();
          T.paintFace(c, byId('manpower'), 'sewn');
          return sha256Canvas(c);
        };
        const clean = await faceHash(byId('manpower'), 'sewn');
        return [await clipped(false) !== clean, await clipped(true) === clean];
    """)
    assert result == [True, True]


# --- The "New" label (#14): a painter option, off by default, drawn on live tiles only. ---

def overlaps(a, b):
    """True when boxes [x0, y0, x1, y1] share an area (touching edges do not count)."""
    return min(a[2], b[2]) > max(a[0], b[0]) and min(a[3], b[3]) > max(a[1], b[1])


def union(boxes):
    return [min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes)]


def inside(inner, outer, slack=0.0):
    return (inner[0] >= outer[0] - slack and inner[1] >= outer[1] - slack
            and inner[2] <= outer[2] + slack and inner[3] <= outer[3] + slack)


def test_box_overlap_catches_a_planted_overlap():
    box = [10, 10, 30, 20]
    assert overlaps(box, [20, 10, 40, 20])  # shifted by half its width
    assert not overlaps(box, [30, 10, 50, 20])  # shares an edge
    assert not overlaps(box, [10, 20, 30, 40])
    assert not overlaps(box, [100, 100, 120, 120])


def test_tagged_live_tile_draws_new(paint_js):
    tagged, untagged, off = run(paint_js, r"""
        const t = byId('travel');
        return [tileTexts(t, { tagged: true }), tileTexts(t), tileTexts(t, { tagged: false })];
    """)
    assert tagged.count("New") == 1, tagged
    assert "New" not in untagged and "New" not in off, (untagged, off)
    assert len(untagged) >= 5, untagged


def test_tag_option_is_off_by_default(paint_js):
    rows = run(paint_js, r"""
        const hash = (entry, ...args) => { const c = fresh(); T.paintTile(c, entry, ...args); return sha256Canvas(c); };
        const out = [];
        for (const e of [byId('manpower'), byId('travel'), { ...byId('manpower'), sample: null }]) {
          out.push([await hash(e), await hash(e, {}), await hash(e, { tagged: false }), await hash(e, { tagged: 'yes' }),
                    await hash(e, null)]);
        }
        return out;
    """)
    assert len(rows) == 3 and all(len(set(row)) == 1 for row in rows), rows


def test_tagged_tile_hash_differs_and_repeats(paint_js):
    a, b, over, plain = run(paint_js, r"""
        const t = byId('travel');
        const a = fresh(); T.paintTile(a, t, { tagged: true });
        const b = fresh(); T.paintTile(b, t, { tagged: true });
        const over = fresh(); T.paintTile(over, byId('hiring')); T.paintTile(over, t, { tagged: true });
        const plain = fresh(); T.paintTile(plain, t);
        return [await sha256Canvas(a), await sha256Canvas(b), await sha256Canvas(over), await sha256Canvas(plain)];
    """)
    assert a == b == over
    assert a != plain


def test_tag_is_ignored_off_live_tiles(paint_js):
    result = run(paint_js, r"""
        const hash = (entry, options) => { const c = fresh(); T.paintTile(c, entry, options); return sha256Canvas(c); };
        const cleared = fresh();
        T.paintTile(cleared, byId('manpower'));
        const painted = !cleared.getContext('2d').getImageData(0, 0, 512, 512).data.every((v) => v === 0);
        T.paintTile(cleared, null, { tagged: true });
        return {
          promotions: await hash(byId('promotions'), { tagged: true }) === await hash(byId('promotions')),
          suggest: await hash(byId('suggest'), { tagged: true }) === await hash(byId('suggest')),
          painted,
          cleared: cleared.getContext('2d').getImageData(0, 0, 512, 512).data.every((v) => v === 0),
        };
    """)
    assert result == {"promotions": True, "suggest": True, "painted": True, "cleared": True}


# (entry expression, its first value-or-no-sample text, at least this many other texts, name lines or None)
LABEL_CASES = {
    "sample": ("byId('travel')", "12", 5, None),
    "no-sample": ("({ ...byId('travel'), sample: null })", "No sample yet", 3, None),
    "wrapped-name": ("({ ...byId('desks'), name: 'Desk Allocation and Seating' })", "18", 5, 2),
}

LABEL_RECORD_JS = r"""
    const entry = %s;
    const record = (options) => {
      const c = fresh();
      let boxes = [];
      const calls = texts(c, () => { boxes = roundRects(c, () => T.paintTile(c, entry, options)); });
      return { texts: calls.map(({ text, box }) => ({ text, box })), rects: boxes, canvas: c };
    };
    const tagged = record({ tagged: true });
    const plain = record();
"""


@pytest.mark.parametrize("case", list(LABEL_CASES))
def test_tag_label_clears_every_tile_text(paint_js, case):
    entry, first_value, min_others, name_lines = LABEL_CASES[case]
    r = run(paint_js, LABEL_RECORD_JS % entry + r"""
        return { name: entry.name, tagged: { texts: tagged.texts, rects: tagged.rects },
                 plain: { texts: plain.texts, rects: plain.rects } };
    """)
    assert r["plain"]["rects"] == [] and len(r["tagged"]["rects"]) >= 1, r["tagged"]["rects"]
    news = [t for t in r["tagged"]["texts"] if t["text"] == "New"]
    assert len(news) == 1, r["tagged"]["texts"]
    patch = union(r["tagged"]["rects"])
    assert inside(news[0]["box"], patch), (news, patch)
    label = union([patch, news[0]["box"]])
    others = [t for t in r["tagged"]["texts"] if t["text"] != "New"]
    assert len(others) >= min_others, others
    texts = [t["text"] for t in others]
    names = texts[:texts.index(first_value)]
    assert " ".join(names) == r["name"], names
    if name_lines is not None:
        assert len(names) == name_lines, names
    hits = [t for t in others if overlaps(label, t["box"])]
    assert hits == [], (label, hits)
    assert others == r["plain"]["texts"]


@pytest.mark.parametrize("case", list(LABEL_CASES))
def test_tag_changes_only_the_label_pixels(paint_js, case):
    r = run(paint_js, LABEL_RECORD_JS % LABEL_CASES[case][0] + r"""
        const a = plain.canvas.getContext('2d').getImageData(0, 0, 512, 512).data;
        const b = tagged.canvas.getContext('2d').getImageData(0, 0, 512, 512).data;
        let box = null;
        for (let i = 0; i < a.length; i += 4) {
          if (a[i] === b[i] && a[i + 1] === b[i + 1] && a[i + 2] === b[i + 2] && a[i + 3] === b[i + 3]) continue;
          const x = (i / 4) % 512;
          const y = Math.floor(i / 4 / 512);
          box = box ? [Math.min(box[0], x), Math.min(box[1], y), Math.max(box[2], x + 1), Math.max(box[3], y + 1)]
            : [x, y, x + 1, y + 1];
        }
        return { diff: box, rects: tagged.rects, news: tagged.texts.filter((t) => t.text === 'New').map((t) => t.box) };
    """)
    assert r["diff"] is not None and len(r["rects"]) >= 1 and len(r["news"]) == 1, r
    label = union([*r["rects"], *r["news"]])
    assert inside(r["diff"], label, slack=2), (r["diff"], label)
