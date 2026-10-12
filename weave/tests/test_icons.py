"""icons.js: WEAVE's own appliqué icons, one per default panel plus a fallback, behind one lookup door."""
from pathlib import Path

import pytest

from helpers import DEFAULTS_JS

ICONS_FILE = Path(__file__).resolve().parents[1] / "public" / "js" / "icons.js"
IMPORT = "const I = await import('/public/js/icons.js');"
NAMES = sorted(["people", "person-plus", "mortarboard", "ribbon", "chevrons", "airplane", "speech", "checklist",
                "magnifier", "key", "desk", "fallback"])

# The one bounding-box predicate: a path passes when it lies inside the 100 x 100 box, has extent on at least
# one axis, and has length (a malformed `d` gives an empty box and zero length). Returns the failing indexes.
BBOX_JS = r"""(paths) => {
    const NS = 'http://www.w3.org/2000/svg';
    const svg = document.createElementNS(NS, 'svg');
    svg.setAttribute('viewBox', '0 0 100 100');
    svg.setAttribute('width', '100');
    svg.setAttribute('height', '100');
    document.body.append(svg);
    const bad = [];
    paths.forEach((d, i) => {
      const p = document.createElementNS(NS, 'path');
      p.setAttribute('d', d);
      svg.append(p);
      const b = p.getBBox();
      const inside = b.x >= 0 && b.y >= 0 && b.x + b.width <= 100 && b.y + b.height <= 100;
      if (!(inside && (b.width > 0 || b.height > 0) && p.getTotalLength() > 0)) bad.push(i);
    });
    svg.remove();
    return bad;
}"""


def test_icon_names_are_the_defaults_plus_fallback(js):
    shipped, keys = js(DEFAULTS_JS + IMPORT + r"""
        return [[...new Set(DEFAULTS.map((p) => p.icon).filter((i) => i !== undefined))], Object.keys(I.ICONS)];
    """)
    assert sorted(keys) == sorted(shipped + ["fallback"]) == NAMES


def test_icons_are_frozen_and_use_every_tone(js):
    result = js(IMPORT + r"""
        return Object.entries(I.ICONS).map(([name, icon]) => [name, Object.isFrozen(I.ICONS),
          [...new Set(icon.felt.map((f) => f.tone))].sort(), icon.stitch.length]);
    """)
    assert len(result) == 12
    for name, frozen, tones, stitches in result:
        assert frozen and tones == ["accent", "base", "light"] and stitches >= 1, name


def test_every_icon_path_stays_inside_the_box(js, make_page, base_url):
    paths = js(IMPORT + "return Object.values(I.ICONS).flatMap((i) => [...i.felt.map((f) => f.d), ...i.stitch]);")
    assert len(paths) >= 24
    page = make_page()
    page.goto(f"{base_url}/tests/blank.html")
    assert page.evaluate(BBOX_JS, paths) == []


def test_box_check_catches_an_out_of_box_path(make_page, base_url):
    page = make_page()
    page.goto(f"{base_url}/tests/blank.html")
    assert page.evaluate(BBOX_JS, ["M0 0 L120 50", "M10 10 L20 20", "Mxx", "M20 50 H80"]) == [0, 2]


def test_icons_file_says_they_were_drawn_for_this_repo():
    lines = ICONS_FILE.read_text(encoding="utf-8").splitlines()
    leading = " ".join(line for line in lines[:4] if line.startswith("//")).lower()
    assert "drawn for this repo" in leading and "no third-party icon paths" in leading


@pytest.mark.parametrize("name", ["'nope'", "undefined", "7", "null", "'toString'", "'__proto__'", "'constructor'"],
                         ids=["nope", "undefined", "7", "null", "toString", "__proto__", "constructor"])
def test_icon_for_falls_back(js, name):
    assert js(f"{IMPORT} return [I.iconFor({name}) === I.ICONS.fallback, I.iconFor('key') === I.ICONS.key];") == [
        True, True]
