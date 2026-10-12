import json

import pytest

from helpers import FULL

FIXTURE_HTML = """
<a id="docs" data-link="docs" href="#"><span data-cta>Read the docs</span></a>
<a id="dl" data-link="download" href="#"><span data-cta>Download blazeAhead</span></a>
<a id="nav" data-link="issues" href="#">Report an issue</a>
<span id="team" data-text="teamName">placeholder</span>
<p id="ver" data-requires="version">Version <span data-text="version"></span><span id="date" data-requires="releaseDate">, <span data-text="releaseDate"></span></span></p>
"""


def resolve(js, cfg):
    return js(f"const m = await import('/public/js/config.js'); return m.resolveConfig({json.dumps(cfg)});")


def apply(js, cfg):
    return js(f"""
        document.body.innerHTML = {json.dumps(FIXTURE_HTML)};
        const m = await import('/public/js/config.js');
        m.applyConfig(document, m.resolveConfig({json.dumps(cfg)}));
        const q = (s) => document.querySelector(s);
        return {{
          docsHref: q('#docs').getAttribute('href'), docsText: q('#docs').textContent.trim(),
          dlHref: q('#dl').getAttribute('href'), dlDisabled: q('#dl').getAttribute('aria-disabled'),
          dlText: q('#dl').textContent.trim(), dlMissing: q('#dl').classList.contains('is-missing'),
          navTitle: q('#nav').getAttribute('title'), navText: q('#nav').textContent.trim(),
          team: q('#team').textContent, verHidden: q('#ver').hidden, dateHidden: q('#date').hidden,
          verText: q('#ver').innerText.trim(),
        }};
    """)


def test_full_settings_derive_gitlab_urls(js):
    r = resolve(js, FULL)
    assert r["urls"]["project"] == "https://gitlab.example.com/devtools/blazeahead"
    assert r["urls"]["releases"] == "https://gitlab.example.com/devtools/blazeahead/-/releases"
    assert r["urls"]["download"] == (
        "https://gitlab.example.com/devtools/blazeahead/-/releases/permalink/latest/downloads/blazeAhead.vsix")
    assert r["urls"]["issues"] == FULL["links"]["issues"]
    assert (r["teamName"], r["version"], r["releaseDate"]) == ("Developer Tools", "1.4.0", "25 Sep 2026")


def test_release_page_is_the_default_download(js):
    cfg = {k: v for k, v in FULL.items() if k != "downloadLink"}
    assert resolve(js, cfg)["urls"]["download"] == (
        "https://gitlab.example.com/devtools/blazeahead/-/releases/permalink/latest")


def test_empty_settings_fall_back_quietly(js):
    r = resolve(js, {})
    assert all(value == "" for value in r["urls"].values())
    assert r["teamName"] == "the blazeAhead team"


@pytest.mark.parametrize("bad", ["javascript:alert(1)", "www.example.com/docs", "   ", "ftp://x.example", 42, None])
def test_unsafe_or_malformed_links_are_dropped(js, bad):
    r = resolve(js, {"gitlabProjectUrl": bad, "links": {"docs": bad}})
    assert r["urls"]["docs"] == ""
    assert r["urls"]["download"] == "" and r["urls"]["releases"] == "" and r["urls"]["project"] == ""


def test_apply_fills_links_and_text(js):
    r = apply(js, {**FULL, "releaseDate": ""})
    assert r["docsHref"] == FULL["links"]["docs"] and r["docsText"] == "Read the docs"
    assert r["team"] == "Developer Tools"
    assert r["verHidden"] is False and r["dateHidden"] is True
    assert r["verText"] == "Version 1.4.0"


def test_apply_marks_missing_links(js):
    r = apply(js, {})
    assert r["dlHref"] is None and r["dlDisabled"] == "true" and r["dlMissing"] is True
    assert r["dlText"] == "Link coming soon"
    assert r["navTitle"] == "Link coming soon" and r["navText"] == "Report an issue"
    assert r["team"] == "the blazeAhead team"
    assert r["verHidden"] is True


def test_boot_reads_window_settings(js):
    href = js(f"""
        document.body.innerHTML = {json.dumps(FIXTURE_HTML)};
        window.BLAZEAHEAD_SITE = {json.dumps(FULL)};
        const m = await import('/public/js/config.js');
        m.boot(window);
        return document.querySelector('#docs').getAttribute('href');
    """)
    assert href == FULL["links"]["docs"]


def test_a_custom_vsix_name_is_used_for_the_direct_download(js):
    r = resolve(js, {**FULL, "vsixFileName": "blazeahead-1.4.0.vsix"})
    assert r["urls"]["download"].endswith("/-/releases/permalink/latest/downloads/blazeahead-1.4.0.vsix")


def test_a_download_url_overrides_the_gitlab_release(js):
    r = resolve(js, {**FULL, "downloadUrl": "https://artifactory.example.com/vsix/blazeAhead.vsix"})
    assert r["urls"]["download"] == "https://artifactory.example.com/vsix/blazeAhead.vsix"
    assert resolve(js, {"downloadUrl": "https://artifactory.example.com/x.vsix"})["urls"]["download"] == (
        "https://artifactory.example.com/x.vsix")
    assert resolve(js, {**FULL, "downloadUrl": "javascript:alert(1)"})["urls"]["download"].endswith("blazeAhead.vsix")
