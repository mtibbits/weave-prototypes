"""Download the pinned third-party files the site ships with (run once; the results are committed).

  Three.js 0.170.0 (MIT) from the npm registry           -> public/vendor/three/
  Fraunces + Figtree (SIL OFL), latin, variable weights   -> public/fonts/
"""
import io
import re
import tarfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"
THREE_VERSION = "0.170.0"
THREE_TGZ = f"https://registry.npmjs.org/three/-/three-{THREE_VERSION}.tgz"
THREE_FILES = [
    "build/three.module.min.js",
    "examples/jsm/loaders/GLTFLoader.js",
    "examples/jsm/utils/BufferGeometryUtils.js",
    "examples/jsm/environments/RoomEnvironment.js",
    "LICENSE",
]
FONT_CSS = ("https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,300..700;1,9..144,300..700"
            "&family=Figtree:wght@400..700&display=swap")
FONT_FILES = {
    ("Fraunces", "normal"): "Fraunces.woff2",
    ("Fraunces", "italic"): "Fraunces-Italic.woff2",
    ("Figtree", "normal"): "Figtree.woff2",
}
OFL_URLS = {
    "Fraunces": "https://raw.githubusercontent.com/google/fonts/main/ofl/fraunces/OFL.txt",
    "Figtree": "https://raw.githubusercontent.com/google/fonts/main/ofl/figtree/OFL.txt",
}
BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/128.0 Safari/537.36")


def fetch(url):
    request = urllib.request.Request(url, headers={"User-Agent": BROWSER_UA})
    with urllib.request.urlopen(request, timeout=60) as resp:
        return resp.read()


def vendor_three():
    out = PUBLIC / "vendor" / "three"
    with tarfile.open(fileobj=io.BytesIO(fetch(THREE_TGZ)), mode="r:gz") as tgz:
        for rel in THREE_FILES:
            member = tgz.extractfile(f"package/{rel}")
            if member is None:
                raise SystemExit(f"three {THREE_VERSION} has no {rel}")
            dest = out / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(member.read())
            print("wrote", dest.relative_to(ROOT))


def vendor_fonts():
    out = PUBLIC / "fonts"
    out.mkdir(parents=True, exist_ok=True)
    css = fetch(FONT_CSS).decode("utf-8")
    wanted = dict(FONT_FILES)
    for subset, body in re.findall(r"/\*\s*([\w-]+)\s*\*/\s*@font-face\s*\{(.*?)\}", css, flags=re.S):
        if subset != "latin":
            continue
        family = re.search(r"font-family:\s*'([^']+)'", body).group(1)
        style = re.search(r"font-style:\s*(\w+)", body).group(1)
        url = re.search(r"url\((https://[^)]+\.woff2)\)", body).group(1)
        name = wanted.pop((family, style), None)
        if name:
            (out / name).write_bytes(fetch(url))
            print("wrote", (out / name).relative_to(ROOT))
    if wanted:
        raise SystemExit(f"Google Fonts CSS had no latin face for {sorted(wanted)}")
    licences = [f"==== {family} ====\n\n{fetch(url).decode('utf-8')}" for family, url in OFL_URLS.items()]
    (out / "OFL.txt").write_text("\n\n".join(licences), encoding="utf-8")
    print("wrote", (out / "OFL.txt").relative_to(ROOT))


if __name__ == "__main__":
    vendor_three()
    vendor_fonts()
