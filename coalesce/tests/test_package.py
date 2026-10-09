import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

MUST_SHIP = [
    "public/index.html", "public/help/index.html", "public/site-config.js", "public/css/site.css",
    "public/js/hero.js", "public/js/crowd.js", "public/js/motion.js", "public/js/config.js", "public/js/eligibility.js",
    "public/assets/coalesce.glb", "public/assets/layout.json", "public/assets/home-still.webp",
    "public/assets/help-still.webp", "public/vendor/three/build/three.module.min.js", "public/fonts/OFL.txt",
    "blender/build_coalesce.py", "blender/coalesce_layout.py", "blender/coalesce.blend",
    "tools/publish-release.ps1", "tools/serve.py", "tools/verify.py", "requirements-dev.txt",
    "SITE-README.md", ".gitlab-ci.yml",
]


def test_zip_ships_the_site_and_its_sources_only(tmp_path):
    import package

    path = package.build(tmp_path / "coalesce-site.zip")
    names = set(zipfile.ZipFile(path).namelist())
    for rel in MUST_SHIP:
        assert f"coalesce-site/{rel}" in names, rel
    unwanted = ("coalesce-site/docs/", "coalesce-site/tests/", "coalesce-site/.venv/", "coalesce-site/dist/")
    assert not [n for n in names if n.startswith(unwanted) or "__pycache__" in n]
    assert "coalesce-site/README.md" not in names  # would overwrite the project's own README
    assert path.stat().st_size < 3_000_000


def test_pages_job_publishes_public():
    ci = (ROOT / ".gitlab-ci.yml").read_text(encoding="utf-8")
    assert "pages:" in ci and "- public" in ci


def test_readme_covers_install_settings_and_releases():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for heading in ("## Install it in your GitLab project", "## The settings file",
                    "## Publishing a release", "## Preview on your PC"):
        assert heading in readme, heading


def test_readme_protects_the_owners_files_and_names_the_gitlab_version():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "keep your `site-config.js`" in readme
    assert "paste our `pages` job" in readme.lower()
    assert "15.9" in readme
