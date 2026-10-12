from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
THREE = ROOT / "public" / "vendor" / "three"
FONTS = ROOT / "public" / "fonts"
FONT_FILES = ["InstrumentSans.woff2", "InstrumentSerif-Regular.woff2", "InstrumentSerif-Italic.woff2"]


def test_three_files_present_with_license():
    assert (THREE / "build" / "three.module.min.js").is_file()
    assert (THREE / "LICENSE").is_file()
    assert "MIT" in (THREE / "LICENSE").read_text(encoding="utf-8")
    # No addons yet: #22 vendors GLTFLoader under examples/ when the quilt needs it.
    assert not (THREE / "examples").exists()


def test_three_loads_in_the_browser(js):
    assert js("const T = await import('three'); return T.REVISION;") == "170"


def test_fonts_present_with_license():
    for name in FONT_FILES:
        data = (FONTS / name).read_bytes()
        assert data[:4] == b"wOF2", name
        assert len(data) > 10_000, name
    assert "SIL OPEN FONT LICENSE" in (FONTS / "OFL.txt").read_text(encoding="utf-8").upper()
