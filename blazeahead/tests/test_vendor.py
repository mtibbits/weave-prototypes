import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"


def test_three_is_vendored_at_the_pinned_version():
    build = (PUBLIC / "vendor/three/build/three.module.min.js").read_text(encoding="utf-8")
    # the minified build declares the revision as a short constant and exports it as REVISION
    assert re.search(r'const \w+="170"', build) and "as REVISION" in build
    for rel in ("examples/jsm/loaders/GLTFLoader.js", "examples/jsm/utils/BufferGeometryUtils.js", "LICENSE"):
        assert (PUBLIC / "vendor/three" / rel).is_file(), rel


def test_fonts_and_licence_are_vendored():
    for name in ("Fraunces.woff2", "Fraunces-Italic.woff2", "Figtree.woff2", "OFL.txt"):
        assert (PUBLIC / "fonts" / name).is_file(), name
    licence = (PUBLIC / "fonts" / "OFL.txt").read_text(encoding="utf-8")
    assert "Fraunces" in licence and "Figtree" in licence and "SIL OPEN FONT LICENSE" in licence.upper()


def test_three_imports_work_in_the_browser(js):
    assert js("const THREE = await import('three'); return THREE.REVISION;") == "170"
