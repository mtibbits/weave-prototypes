"""The WEAVE page's static parts, its accessibility basics, its still and its stage."""
import json
import os
import posixpath
import re
from pathlib import Path

import pytest

from helpers import open_page

PUBLIC = Path(__file__).resolve().parents[1] / "public"
SOURCE = "https://github.com/mtibbits/weave-prototypes"
BROKEN = "window.WEAVE_PANELS = {"
EMPTY = "window.WEAVE_PANELS = { panels: [] };"


def test_header_nav_and_pill(make_page, base_url):
    page, _ = open_page(make_page, base_url)
    links = page.eval_on_selector_all(
        ".site-nav a", "els => els.map((a) => [a.textContent.trim(), a.getAttribute('href')])")
    # Exactly three links: #17 adds "Help" and updates this list.
    assert links == [["What's in it", "#panels"], ["Coalesce", "../coalesce/"], ["Source", SOURCE]]
    assert page.locator(".pill").text_content().strip() == "Prototype · work in progress"


def test_hero_copy(make_page, base_url):
    page, _ = open_page(make_page, base_url)
    assert page.locator(".eyebrow").text_content().strip() == "Workforce Engagement, Actions & Visibility Environment"
    assert page.locator("h1").inner_text() == "Every part of your workforce, woven together."
    assert page.locator("h1 em").inner_text() == "woven"


def test_why_a_quilt(make_page, base_url):
    page, _ = open_page(make_page, base_url)
    why = page.locator("section.why")
    assert why.locator("h2").inner_text() == "Why a quilt?"
    assert "Coalesce lives on as the Manpower patch" in why.inner_text()


def test_footer(make_page, base_url):
    page, _ = open_page(make_page, base_url)
    footer = page.locator("footer")
    assert "Sample data only" in footer.inner_text()
    assert footer.locator(f'a[href="{SOURCE}"]').count() == 1
    assert footer.locator('a[href="../"]').inner_text() == "← All prototypes"


@pytest.mark.parametrize("body", [None, BROKEN, EMPTY], ids=["defaults", "broken", "empty"])
def test_accessibility_basics(make_page, base_url, body):
    page, _ = open_page(make_page, base_url, body)
    assert page.locator("a.skip-link").get_attribute("href") == "#main"
    assert page.locator("main#main").count() == 1
    assert page.locator("main#main #panels").count() == 1
    assert page.locator("h1").count() == 1
    stage = page.locator("[data-hero]")
    assert stage.get_attribute("role") == "img" and len(stage.get_attribute("aria-label")) > 40
    assert page.evaluate("[...document.images].every((i) => i.hasAttribute('alt'))")
    if body is None:
        assert page.evaluate("document.images.length") == 1


@pytest.mark.parametrize("width", [390, 1440])
def test_no_horizontal_scroll(make_page, base_url, width):
    page, _ = open_page(make_page, base_url, viewport={"width": width, "height": 844})
    assert page.locator("[data-hero]").count() == 1  # the real page rendered (a 404 never scrolls sideways either)
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")


def test_page_loads_cleanly_with_its_fonts(make_page, base_url):
    page, errors = open_page(make_page, base_url)
    statuses = page.evaluate("""async () => {
        await Promise.all([...document.fonts].map((f) => f.load().catch(() => null)));
        return [...document.fonts].map((f) => f.status);
    }""")
    assert len(statuses) == 3 and set(statuses) == {"loaded"}
    assert errors == []


@pytest.mark.parametrize("width", [390, 1440])
def test_stage_keeps_its_shape(make_page, base_url, width):
    page, _ = open_page(make_page, base_url, viewport={"width": width, "height": 844})
    box = page.locator("[data-hero]").bounding_box()
    assert box["width"] > 0 and abs(box["width"] / box["height"] - 1.6) < 0.01


def test_still_is_1600_by_1000_and_at_most_250_kb(make_page, base_url):
    assert (PUBLIC / "assets" / "weave-still.jpg").stat().st_size <= 250_000
    page, _ = open_page(make_page, base_url)
    still = page.locator(".hero-still")
    assert still.evaluate("img => [img.complete, img.naturalWidth, img.naturalHeight]") == [True, 1600, 1000]


# --- File-name case: Windows serves a mis-cased path, GitHub Pages does not. ---

def _resolve(base_dir, ref):
    """Resolve a reference against its file's directory (relative to public/); None when it leaves public/."""
    path = posixpath.normpath(posixpath.join(base_dir, ref.split("#")[0].split("?")[0]))
    if path == ".." or path.startswith("../"):
        return None
    if ref.endswith("/") or path == ".":
        path = posixpath.join("" if path == "." else path, "index.html")
    return path


def local_references():
    """Every local file the page, its stylesheet and its modules point at, as paths relative to public/."""
    refs = set()
    html = (PUBLIC / "index.html").read_text(encoding="utf-8")
    for ref in re.findall(r'(?:src|href)="([^"]+)"', html):
        if not re.match(r"[a-z]+:", ref) and not ref.startswith("#"):
            refs.add(_resolve("", ref))
    importmap = re.search(r'<script type="importmap">(.*?)</script>', html, re.S)
    for ref in json.loads(importmap.group(1))["imports"].values():
        refs.add(_resolve("", ref))
    css = (PUBLIC / "css" / "weave.css").read_text(encoding="utf-8")
    for ref in re.findall(r"""url\(\s*["']?([^"')]+)""", css):
        if not re.match(r"[a-z]+:", ref):
            refs.add(_resolve("css", ref))
    for module in (PUBLIC / "js").glob("*.js"):
        text = module.read_text(encoding="utf-8")
        for ref in re.findall(r"""(?:from|import\()\s*['"](\.{1,2}/[^'"]+)['"]""", text):
            refs.add(_resolve("js", ref))
    refs.discard(None)
    return refs


def case_mismatches(refs):
    """References whose every path component is not an exact directory entry (missing or mis-cased)."""
    bad = []
    for ref in sorted(refs):
        here = PUBLIC
        for part in ref.split("/"):
            if part not in os.listdir(here):
                bad.append(ref)
                break
            here = here / part
    return bad


def test_case_check_catches_a_mis_cased_reference():
    assert case_mismatches({"Panels.js", "js/Main.js", "fonts/instrumentsans.woff2"}) == [
        "Panels.js", "fonts/instrumentsans.woff2", "js/Main.js"]


def test_local_references_match_file_case():
    refs = local_references()
    assert {"panels.js", "js/main.js", "assets/weave-still.jpg", "css/weave.css",
            "fonts/InstrumentSans.woff2", "index.html"} <= refs, refs
    assert case_mismatches(refs) == []
