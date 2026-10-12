"""fabric.js: makeCanvas (the one canvas door), the fabric table, paintFabric, the sashing and the textures."""
import re
from pathlib import Path

import pytest

from helpers import DEFAULTS_JS, open_paint

WEAVE = Path(__file__).resolve().parents[1]
JS = WEAVE / "public" / "js"
DEV = WEAVE / "dev"
FABRIC_IMPORT = "const F = await import('/public/js/fabric.js');"


# --- makeCanvas: every hashed canvas reads back in software (U1). ---

def get_context_strays(text):
    """Line numbers of `getContext(` calls outside contextOf (the one context door, which makeCanvas uses), plus a 0
    entry when there is not exactly one inside it."""
    lines = text.splitlines()
    calls = [n for n, line in enumerate(lines, 1) if "getContext(" in line]
    start = next((n for n, line in enumerate(lines, 1) if line.startswith("export function contextOf")), None)
    end = next((n for n in range(start or 1, len(lines) + 1) if lines[n - 1] == "}"), None) if start else None
    inside = [n for n in calls if start and start <= n <= end]
    strays = [n for n in calls if n not in inside]
    return strays + ([] if len(inside) == 1 else [0])


def painter_sources():
    """The painters and the dev pages: every file that may create a canvas it reads back."""
    files = sorted(JS.glob("random.js")) + sorted(JS.glob("icons.js")) + sorted(JS.glob("fabric.js")) \
        + sorted(JS.glob("tiles.js")) + sorted(DEV.glob("*.html"))
    assert JS / "fabric.js" in files
    return files


def test_get_context_check_catches_a_second_call():
    planted = ("export function contextOf(c) {\n  return c.getContext('2d', { willReadFrequently: true });\n}\n"
               "const x = other.getContext('2d');\n")
    assert get_context_strays(planted) == [4]
    assert get_context_strays(planted.replace("contextOf", "makeCanvas")) == [2, 4, 0]
    assert get_context_strays("const y = 1;\n") == [0]


def test_get_context_only_inside_the_context_door():
    found = {}
    for path in painter_sources():
        text = path.read_text(encoding="utf-8")
        if path.name == "fabric.js":
            bad = get_context_strays(text)
        else:
            bad = [n for n, line in enumerate(text.splitlines(), 1) if "getContext(" in line]
        if bad:
            found[path.name] = bad
    assert found == {}, found


def test_make_canvas_is_sized_and_reads_back_in_software(js):
    result = js(FABRIC_IMPORT + r"""
        const a = F.makeCanvas(64), b = F.makeCanvas(32, 16);
        const ctx = a.getContext('2d');
        const plain = document.createElement('canvas');
        return [a.width, a.height, b.width, b.height, ctx === F.contextOf(a),
                ctx.getContextAttributes().willReadFrequently,
                F.contextOf(plain).getContextAttributes().willReadFrequently];
    """)
    assert result == [64, 64, 32, 16, True, True, True]


def test_make_canvas_has_its_reason_beside_it():
    text = (JS / "fabric.js").read_text(encoding="utf-8")
    assert re.search(r"willReadFrequently", text) and "makeCanvas" in text
    assert "read back or hashed" in text


# --- The fabric table and paintFabric. ---

FABRIC_NAMES = sorted(["coalesce-people", "mustard-calico", "indigo-dots", "rose-gingham", "sage-stripe",
                       "sky-chambray", "plum-plaid", "brick-solid", "olive-calico", "navy-dots",
                       "terracotta-gingham", "muslin"])

# paint(name, seed, size) paints a fresh makeCanvas(size); hash(...) returns that canvas's hash.
PAINT = FABRIC_IMPORT + r"""
    const paint = (name, seed, size = 512) => { const c = F.makeCanvas(size); F.paintFabric(c, name, seed); return c; };
    const hash = async (name, seed, size) => sha256Canvas(paint(name, seed, size));
"""


def test_fabric_table_covers_the_defaults(paint_js):
    keys, shipped, kinds, all_kinds, muslin = paint_js(DEFAULTS_JS + FABRIC_IMPORT + r"""
        return [Object.keys(F.FABRICS), DEFAULTS.map((p) => p.fabric), Object.values(F.FABRICS).map((f) => f.kind),
                F.FABRIC_KINDS, [F.FABRICS.muslin.kind, F.FABRICS['coalesce-people'].kind, Object.isFrozen(F.FABRICS)]];
    """)
    assert sorted(keys) == FABRIC_NAMES
    assert set(shipped) <= set(keys)
    assert sorted(set(kinds)) == sorted(all_kinds) == sorted(["calico", "gingham", "dots", "stripe", "chambray",
                                                              "plaid", "solid", "people"])
    assert muslin == ["solid", "people", True]


@pytest.mark.parametrize("name", ["'nope'", "undefined", "7", "'constructor'", "'__proto__'"],
                         ids=["nope", "undefined", "7", "constructor", "__proto__"])
def test_unknown_fabric_paints_as_muslin(paint_js, name):
    same, fallback = paint_js(PAINT + f"""
        return [await hash({name}, 's') === await hash('muslin', 's'), F.fabricFor({name}) === F.FABRICS.muslin];
    """)
    assert same and fallback


def test_known_fabric_and_seed_change_the_pixels(paint_js):
    result = paint_js(PAINT + r"""
        return [await hash('indigo-dots', 's') !== await hash('muslin', 's'),
                await hash('mustard-calico', 'a') !== await hash('mustard-calico', 'b'),
                isUniform(paint('indigo-dots', 's')), isUniform(paint('muslin', 's'))];
    """)
    assert result == [True, True, False, False]


def test_paint_fabric_repeats_in_one_canvas_and_a_fresh_one(paint_js):
    hashes = paint_js(PAINT + r"""
        const c = paint('plum-plaid', 'feedback');
        const first = await sha256Canvas(c);
        F.paintFabric(c, 'indigo-dots', 'other');
        F.paintFabric(c, 'plum-plaid', 'feedback');
        return [first, await sha256Canvas(c), await hash('plum-plaid', 'feedback')];
    """)
    assert len(set(hashes)) == 1


@pytest.mark.parametrize("name, seed", [("rose-gingham", "awards"), ("muslin", "filler")])
def test_paint_fabric_hash_matches_across_two_contexts(make_page, base_url, name, seed):
    body = PAINT + f"return await hash('{name}', '{seed}');"
    first = open_paint(make_page, base_url)(body)
    second = open_paint(make_page, base_url)(body)
    assert first == second and len(first) == 64


SCALE_JS = PAINT + r"""
    const rgb = (c) => c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
    // Average each 2 x 2 block of a 1024 canvas down to 512.
    const half = (c) => {
      const d = rgb(c), out = new Float64Array(512 * 512 * 3);
      for (let y = 0; y < 512; y += 1) for (let x = 0; x < 512; x += 1) for (let k = 0; k < 3; k += 1) {
        let sum = 0;
        for (const [dx, dy] of [[0, 0], [1, 0], [0, 1], [1, 1]]) sum += d[((2 * y + dy) * 1024 + 2 * x + dx) * 4 + k];
        out[(y * 512 + x) * 3 + k] = sum / 4;
      }
      return out;
    };
    const mad = (a, b) => {
      let sum = 0;
      for (let i = 0; i < 512 * 512; i += 1) for (let k = 0; k < 3; k += 1) sum += Math.abs(a[i * 4 + k] - b[i * 3 + k]);
      return sum / (512 * 512 * 3);
    };
    const small = paint(NAME, 'scale');
    const scaled = mad(rgb(small), half(paint(NAME, 'scale', 1024)));
    // The planted control: a print fixed in pixels repeats the 512 paint 2 x 2 at 1024.
    const tiled = F.makeCanvas(1024);
    for (const [x, y] of [[0, 0], [512, 0], [0, 512], [512, 512]]) tiled.getContext('2d').drawImage(small, x, y);
    return [scaled, mad(rgb(small), half(tiled))];
"""


@pytest.mark.parametrize("name", ["mustard-calico", "coalesce-people", "plum-plaid", "indigo-dots"])
def test_paint_fabric_scales_with_the_canvas(paint_js, name):
    scaled, control = paint_js(SCALE_JS.replace("NAME", repr(name)))
    print(f"scale {name}: scaled_MAD={scaled:.3f} control_MAD={control:.3f}")
    # B7: the rule is fixed before red. T = control_MAD / 2, and the gap must be real (at least 4x).
    assert scaled < control / 2, (scaled, control)
    assert control >= 4 * scaled, (scaled, control)


# --- The sashing and its UV rule (D38). ---

EPIC = "{ cols: 4, rows: 3, block: 1, sashing: 0.14, border: 0.14 }"


def test_sashing_size_for_the_epic_geometry(js):
    size, quilt, extra = js(FABRIC_IMPORT + f"""
        return [F.sashingSize({EPIC}), F.quiltSize({EPIC}), F.quiltSize({{ ...{EPIC}, extra: 9 }})];
    """)
    assert size == [1204, 912]
    assert abs(quilt[0] - 4.70) < 1e-9 and abs(quilt[1] - 3.56) < 1e-9
    assert extra == quilt


def uv_pixel(x, y, width, height):
    """The issue's rule: u = (x + 2.35) / 4.70, v = (y + 1.78) / 3.56; pixel x = u * width, y = (1 - v) * height."""
    u, v = (x + 2.35) / 4.70, (y + 1.78) / 3.56
    return round(u * width), round((1 - v) * height)


def test_sashing_follows_the_uv_rule(paint_js):
    points = [list(uv_pixel(x, y, 1204, 912)) for x, y in [(-1.14, 0.57), (-1.14, 0), (-2.28, 0)]]
    patches, colors = paint_js(FABRIC_IMPORT + f"""
        const c = F.makeCanvas(1204, 912);
        F.paintSashing(c, {EPIC});
        const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
        const patch = ([px, py]) => [0, 1, 2].map((k) => {{
          let sum = 0;
          for (let y = py - 2; y <= py + 2; y += 1) for (let x = px - 2; x <= px + 2; x += 1) sum += d[(y * c.width + x) * 4 + k];
          return sum / 25;
        }});
        const hex = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
        const S = F.SASHING_COLORS;
        return [{points}.map(patch), [hex(S.cornerstone), hex(S.muslin), hex(S.binding)]];
    """)
    for patch, color in zip(patches, colors):
        assert all(abs(p - c) <= 24 for p, c in zip(patch, color)), (patch, color)
    for i in range(3):
        for j in range(i + 1, 3):
            assert max(abs(a - b) for a, b in zip(colors[i], colors[j])) > 48


# --- The scene textures. ---

TEXTURES = {
    "sashing": f"(c) => F.paintSashing(c, {EPIC})",
    "wood": "(c) => F.paintWood(c)",
    "weave-normal": "(c) => F.paintWeaveNormal(c)",
    "shadow": "(c) => F.paintShadow(c)",
}
SIZES = {"sashing": (1204, 912), "wood": (1024, 256), "weave-normal": (512, 512), "shadow": (512, 512)}

NORMAL_JS = r"""
    let minLen = 9, maxLen = 0, minZ = 9;
    for (let i = 0; i < d.length; i += 4) {
      const n = [0, 1, 2].map((k) => d[i + k] / 255 * 2 - 1);
      const len = Math.hypot(...n);
      minLen = Math.min(minLen, len); maxLen = Math.max(maxLen, len); minZ = Math.min(minZ, n[2]);
    }
    const diff = (a, b) => [0, 1, 2].reduce((s, k) => s + Math.abs(a[k] - b[k]), 0);
    const colDiff = (x0, x1) => { let s = 0; for (let y = 0; y < H; y += 1) s += diff(px(x0, y), px(x1, y)); return s / H; };
    const rowDiff = (y0, y1) => { let s = 0; for (let x = 0; x < W; x += 1) s += diff(px(x, y0), px(x, y1)); return s / W; };
    let interior = 0;
    for (let x = 1; x < W - 2; x += 1) interior += colDiff(x, x + 1);
    interior /= W - 3;
    out.normal = { minLen, maxLen, minZ, seamX: colDiff(W - 1, 0), seamY: rowDiff(H - 1, 0), interior };
"""


@pytest.mark.parametrize("name", list(TEXTURES))
def test_textures_paint_and_repeat(paint_js, name):
    w, h = SIZES[name]
    result = paint_js(FABRIC_IMPORT + f"""
        const W = {w}, H = {h};
        const painter = {TEXTURES[name]};
        const fresh = () => {{ const c = F.makeCanvas(W, H); painter(c); return c; }};
        const a = fresh(), b = fresh();
        const d = a.getContext('2d').getImageData(0, 0, W, H).data;
        const px = (x, y) => [...d.slice((y * W + x) * 4, (y * W + x) * 4 + 4)];
        const out = {{ uniform: isUniform(a), equal: await sha256Canvas(a) === await sha256Canvas(b),
                       corners: [px(0, 0), px(W - 1, 0), px(0, H - 1), px(W - 1, H - 1)].map((p) => p[3]) }};
        if ('{name}' === 'weave-normal') {{ {NORMAL_JS} }}
        return out;
    """)
    assert result["uniform"] is False and result["equal"] is True
    if name == "shadow":
        assert result["corners"] == [0, 0, 0, 0]
    if name == "weave-normal":
        n = result["normal"]
        assert 0.9 <= n["minLen"] and n["maxLen"] <= 1.1 and n["minZ"] > 0, n
        assert n["seamX"] <= 1.5 * n["interior"] and n["seamY"] <= 1.5 * n["interior"], n
