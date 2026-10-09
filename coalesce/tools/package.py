"""Build dist/coalesce-site.zip: everything needed at work, and nothing else.

  .venv/Scripts/python tools/package.py
"""
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHIP = ["public", "blender", "tools", ".gitlab-ci.yml", "README.md", "requirements-dev.txt"]
SKIP_PARTS = {"__pycache__"}
SKIP_SUFFIXES = {".pyc", ".blend1"}
# Shipped under a name that can't overwrite the owner's own README when the folder is copied into their project.
RENAMES = {"README.md": "SITE-README.md"}


def files_to_ship():
    for item in SHIP:
        path = ROOT / item
        candidates = [path] if path.is_file() else sorted(p for p in path.rglob("*") if p.is_file())
        for file in candidates:
            if SKIP_PARTS.isdisjoint(file.relative_to(ROOT).parts) and file.suffix not in SKIP_SUFFIXES:
                yield file


def build(dest=ROOT / "dist" / "coalesce-site.zip"):
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dest, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file in files_to_ship():
            rel = file.relative_to(ROOT).as_posix()
            archive.write(file, f"coalesce-site/{RENAMES.get(rel, rel)}")
    return dest


if __name__ == "__main__":
    path = build()
    print(f"wrote {path.relative_to(ROOT)} ({path.stat().st_size / 1e6:.2f} MB)")
