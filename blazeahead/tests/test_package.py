import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

VIEWS = ["trailhead", "continuity", "scaffolding", "knowledge", "in-flight", "junction"]
MUST_SHIP = [
    "public/index.html", "public/tour/index.html", "public/help/index.html", "public/site-config.js",
    "public/tour-content.js", "public/css/site.css",
    *[f"public/js/{m}.js" for m in ("config", "content", "eligibility", "kbmap", "rig", "tour-state", "tour", "stage",
                                    "stage-live", "world")],
    "public/assets/blazeahead.glb", "public/assets/world.json", "public/assets/junction.json",
    "public/assets/still-signs.json", "public/assets/favicon.svg",
    *[f"public/assets/stills/{v}.webp" for v in VIEWS],
    "public/vendor/three/build/three.module.min.js", "public/vendor/three/LICENSE", "public/fonts/OFL.txt",
    "blender/build_blazeahead.py", "blender/blazeahead_layout.py", "blender/blazeahead.blend",
    "tools/publish-release.ps1", "tools/serve.py", "tools/verify.py", "requirements-dev.txt",
    "SITE-README.md", ".gitlab-ci.yml",
]


def test_zip_ships_the_site_and_its_sources_only(tmp_path):
    import package

    path = package.build(tmp_path / "blazeahead-site.zip")
    names = set(zipfile.ZipFile(path).namelist())
    for rel in MUST_SHIP:
        assert f"blazeahead-site/{rel}" in names, rel
    unwanted = ("blazeahead-site/docs/", "blazeahead-site/tests/", "blazeahead-site/.venv/", "blazeahead-site/dist/",
                "blazeahead-site/blender/_render/", "blazeahead-site/.superpowers/", "blazeahead-site/verify-output/")
    assert not [n for n in names if n.startswith(unwanted) or "__pycache__" in n]
    assert "blazeahead-site/README.md" not in names  # would overwrite the project's own README
    assert path.stat().st_size < 4_000_000


def test_pages_job_publishes_public():
    ci = (ROOT / ".gitlab-ci.yml").read_text(encoding="utf-8")
    assert "pages:" in ci and "- public" in ci


def test_readme_covers_install_settings_releases_and_open_decisions():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for heading in ("## Install it in your GitLab project", "## The settings files", "## Publishing a release",
                    "## Preview on your PC", "## Decisions waiting for you", "## Rebuilding the 3D world"):
        assert heading in readme, heading
    assert "keep your `site-config.js` and `tour-content.js`" in readme
    assert "paste our `pages` job" in readme.lower()
    assert "15.9" in readme
    assert "Install from VSIX" in readme
