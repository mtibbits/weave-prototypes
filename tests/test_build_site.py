"""The Pages site is the front page plus each prototype's public/ folder, assembled by tools/build_site.py."""
from pathlib import Path

import build_site

ROOT = Path(__file__).resolve().parents[1]


def test_build_assembles_the_front_page_and_both_prototypes(tmp_path):
    out = build_site.build(tmp_path / "_site")

    assert (out / "index.html").is_file()
    assert (out / "coalesce" / "index.html").is_file()
    assert (out / "coalesce" / "help" / "index.html").is_file()
    assert (out / "coalesce" / "assets" / "coalesce.glb").is_file()
    assert (out / "weave" / "index.html").is_file()


def test_build_replaces_a_stale_output_folder(tmp_path):
    out = tmp_path / "_site"
    out.mkdir()
    (out / "stale.txt").write_text("left over from an old build")

    build_site.build(out)

    assert not (out / "stale.txt").exists()
    assert (out / "index.html").is_file()


def test_the_front_page_links_to_both_prototypes_with_relative_urls():
    html = (ROOT / "site" / "index.html").read_text(encoding="utf-8")

    assert 'href="weave/"' in html
    assert 'href="coalesce/"' in html
