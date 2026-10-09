from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
THREE = ROOT / "public" / "vendor" / "three"
FONTS = ROOT / "public" / "fonts"
THREE_FILES = [
    "build/three.module.min.js",
    "examples/jsm/loaders/GLTFLoader.js",
    "examples/jsm/utils/BufferGeometryUtils.js",
    "examples/jsm/environments/RoomEnvironment.js",
    "LICENSE",
]
FONT_FILES = ["InstrumentSans.woff2", "InstrumentSerif-Regular.woff2", "InstrumentSerif-Italic.woff2"]


def test_three_files_present_with_license():
    for rel in THREE_FILES:
        assert (THREE / rel).is_file(), rel
    assert "MIT" in (THREE / "LICENSE").read_text(encoding="utf-8")


def test_three_and_addons_load_in_the_browser(js):
    result = js("""
        const THREE = await import('three');
        const { GLTFLoader } = await import('three/addons/loaders/GLTFLoader.js');
        const { RoomEnvironment } = await import('three/addons/environments/RoomEnvironment.js');
        return [THREE.REVISION, typeof GLTFLoader, typeof RoomEnvironment];
    """)
    assert result == ["170", "function", "function"]


def test_fonts_present_with_license():
    for name in FONT_FILES:
        data = (FONTS / name).read_bytes()
        assert data[:4] == b"wOF2", name
        assert len(data) > 10_000, name
    assert "SIL OPEN FONT LICENSE" in (FONTS / "OFL.txt").read_text(encoding="utf-8").upper()
