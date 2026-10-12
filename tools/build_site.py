"""Assemble the GitHub Pages site: the front page plus each prototype's public/ folder.

The Pages workflow and local previews both use this script, so what you preview is what gets published.

Usage:  python tools/build_site.py [--out _site]
        python tools/serve.py _site
"""
import argparse
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONT_PAGE = ROOT / "site"
PROTOTYPES = {
    "coalesce": ROOT / "coalesce" / "public",
    "weave": ROOT / "weave" / "public",
    "blazeahead": ROOT / "blazeahead" / "public",
}


def build(out):
    """Write the site to `out`, replacing anything already there; returns the output path."""
    out = Path(out)
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(FRONT_PAGE, out)
    for name, source in PROTOTYPES.items():
        shutil.copytree(source, out / name)
    return out


def main():
    parser = argparse.ArgumentParser(description="Assemble the Pages site from the front page and every prototype.")
    parser.add_argument("--out", default=str(ROOT / "_site"))
    args = parser.parse_args()
    out = build(args.out)
    print(f"Site assembled in {out}")


if __name__ == "__main__":
    main()
