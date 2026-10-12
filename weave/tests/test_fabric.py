"""fabric.js: makeCanvas (the one canvas door), the fabric table, paintFabric, the sashing and the textures."""
import re
from pathlib import Path

WEAVE = Path(__file__).resolve().parents[1]
JS = WEAVE / "public" / "js"
DEV = WEAVE / "dev"
FABRIC_IMPORT = "const F = await import('/public/js/fabric.js');"


# --- makeCanvas: every hashed canvas reads back in software (U1). ---

def get_context_strays(text):
    """Line numbers of `getContext(` calls outside makeCanvas, plus a 0 entry when there is not exactly one inside."""
    lines = text.splitlines()
    calls = [n for n, line in enumerate(lines, 1) if "getContext(" in line]
    start = next((n for n, line in enumerate(lines, 1) if line.startswith("export function makeCanvas")), None)
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
    planted = ("export function makeCanvas(w) {\n  c.getContext('2d', { willReadFrequently: true });\n}\n"
               "const x = other.getContext('2d');\n")
    assert get_context_strays(planted) == [4]
    assert get_context_strays("const y = 1;\n") == [0]


def test_get_context_only_inside_make_canvas():
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
        return [a.width, a.height, b.width, b.height, ctx === a.getContext('2d'),
                ctx.getContextAttributes().willReadFrequently];
    """)
    assert result == [64, 64, 32, 16, True, True]


def test_make_canvas_has_its_reason_beside_it():
    text = (JS / "fabric.js").read_text(encoding="utf-8")
    assert re.search(r"willReadFrequently", text) and "makeCanvas" in text
    assert "read back or hashed" in text
