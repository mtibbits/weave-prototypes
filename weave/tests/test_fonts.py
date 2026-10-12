"""fontsReady: the faces wait for the web fonts, and warn (rather than paint blank) when a font fails."""
from helpers import collect_console, font_warnings

TILES_IMPORT = "const T = await import('/public/js/tiles.js');"


def test_fonts_ready_resolves_false_and_warns_when_no_face_is_declared(make_page, base_url):
    page = make_page()
    messages = collect_console(page)
    page.goto(f"{base_url}/tests/blank.html")
    ok = page.evaluate(f"async () => {{ {TILES_IMPORT} return await T.fontsReady(); }}")
    warnings = font_warnings(messages)
    assert ok is False
    assert len(warnings) == 3 and all("could not load" in w for w in warnings), warnings
    specs = page.evaluate(f"async () => {{ {TILES_IMPORT} return T.FONT_SPECS; }}")
    assert [w for spec in specs for w in warnings if f"font {spec} could" in w] == warnings


def test_fonts_ready_resolves_true_with_the_real_faces(paint_js):
    assert paint_js(f"{TILES_IMPORT} return await T.fontsReady();") is True
    assert font_warnings(paint_js.console) == []
    assert paint_js("return [...document.fonts].filter((f) => f.status === 'loaded').length;") >= 3
