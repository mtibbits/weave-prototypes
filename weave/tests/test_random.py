"""random.js: Coalesce's mulberry32, frozen for hash stability, plus string-seeded streams (FNV-1a over a JSON key)."""
import json
import re
from pathlib import Path

import pytest

WEAVE = Path(__file__).resolve().parents[1]
REPO = WEAVE.parent
IMPORT = "const R = await import('/public/js/random.js');"


def mulberry32_source(path):
    """`export function mulberry32` up to the first column-0 `}`, line endings normalised (autocrlf)."""
    lines = path.read_text(encoding="utf-8").splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith("export function mulberry32"))
    end = next(i for i in range(start, len(lines)) if lines[i] == "}")
    return lines[start:end + 1]


def test_mulberry32_is_coalesces_function():
    ours = mulberry32_source(WEAVE / "public" / "js" / "random.js")
    theirs = mulberry32_source(REPO / "coalesce" / "public" / "js" / "motion.js")
    assert ours == theirs, ("WEAVE's mulberry32 is frozen for hash stability (#7, #10 and #20 depend on it): "
                            "a mismatch with Coalesce means decide deliberately, never re-sync blindly.")


def fnv1a(text):
    """FNV-1a 32-bit over UTF-16 code units, the independent oracle for seedFor."""
    data = text.encode("utf-16-le")
    h = 0x811C9DC5
    for i in range(0, len(data), 2):
        h ^= data[i] | (data[i + 1] << 8)
        h = (h * 0x01000193) & 0xFFFFFFFF
    return h


def py_mulberry32(seed):
    a = seed & 0xFFFFFFFF

    def imul(x, y):
        return (x * y) & 0xFFFFFFFF

    def draw():
        nonlocal a
        a = (a + 0x6D2B79F5) & 0xFFFFFFFF
        t = a
        t = imul(t ^ (t >> 15), t | 1)
        t ^= (t + imul(t ^ (t >> 7), t | 61)) & 0xFFFFFFFF
        return ((t ^ (t >> 14)) & 0xFFFFFFFF) / 4294967296

    return draw


@pytest.mark.parametrize("id_, purpose", [("manpower", "bars"), ("filler", "fabric"), ("sashing", "speckle"),
                                          ("", "x"), ("Désk", "face")])
def test_seed_for_matches_an_independent_fnv1a(js, id_, purpose):
    key = json.dumps([id_, purpose], separators=(",", ":"), ensure_ascii=False)
    got = js(f"{IMPORT} return R.seedFor({json.dumps(id_)}, {json.dumps(purpose)});")
    assert got == fnv1a(key)


def test_rng_for_matches_an_independent_mulberry32(js):
    got = js(f"{IMPORT} const r = R.rngFor('manpower', 'bars'); return [r(), r(), r(), r(), r()];")
    draw = py_mulberry32(fnv1a('["manpower","bars"]'))
    expected = [draw() for _ in range(5)]
    assert all(abs(g - e) < 1e-12 for g, e in zip(got, expected)), (got, expected)
    assert len(set(got)) == 5


def test_streams_are_independent_and_repeatable(js):
    result = js(IMPORT + r"""
        const a1 = R.rngFor('a', 'x'), a2 = R.rngFor('a', 'x'), ay = R.rngFor('a', 'y');
        const s1 = [], s2 = [];
        for (let i = 0; i < 10; i += 1) { s1.push(a1()); ay(); s2.push(a2()); ay(); }
        return {
          same: s1.every((v, i) => v === s2[i]),
          firsts: [R.rngFor('a', 'x')(), R.rngFor('a', 'y')(), R.rngFor('b', 'x')()],
          joined: R.seedFor('a|b', 'c') !== R.seedFor('a', 'b|c'),
        };
    """)
    assert result["same"]
    assert len(set(result["firsts"])) == 3
    assert result["joined"]


def test_random_js_has_no_ambient_inputs():
    text = (WEAVE / "public" / "js" / "random.js").read_text(encoding="utf-8")
    assert not re.search(r"Math\.random|Date|performance\.now", text)
