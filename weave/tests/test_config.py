"""config.js (#17): the owner's settings in site-config.js, resolved and wired into the Help page. Ported from Coalesce."""
import json
import re
from pathlib import Path

import pytest

from helpers import BAD_LINKS, EMPTY_SITE, FILLED_SITE, open_help

PUBLIC = Path(__file__).resolve().parents[1] / "public"

FIXTURE_HTML = """
<a id="desk" data-link="serviceDesk" href="#"><span data-cta>Open a ticket</span></a>
<a id="bare" data-link="docs" href="#">Docs</a>
<span id="team" data-text="teamName">placeholder</span>
<p id="req" data-requires="teamName">x</p>
<p id="never" data-requires="version">y</p>
"""

READ_FIXTURE = """
    const q = (s) => document.querySelector(s);
    return {
      deskHref: q('#desk').getAttribute('href'), deskDisabled: q('#desk').getAttribute('aria-disabled'),
      deskMissing: q('#desk').classList.contains('is-missing'), deskText: q('#desk').textContent.trim(),
      bareTitle: q('#bare').getAttribute('title'), bareText: q('#bare').textContent.trim(),
      team: q('#team').textContent, reqHidden: q('#req').hidden, neverHidden: q('#never').hidden,
    };
"""

ACCEPTED = [(v, v) for v in ["https://a.example.com/x", "http://a.example.com", "mailto:help@example.com", "/abs",
                             "./rel", "../up", "//host/x", "https://", "HTTPS://X.EXAMPLE", "Mailto:a@b"]]
ACCEPTED.append(("  https://pad.example.com/  ", "https://pad.example.com/"))


def resolve(js, cfg):
    return js(f"const m = await import('/public/js/config.js'); return m.resolveConfig({json.dumps(cfg)});")


def apply(js, cfg):
    return js(f"""
        document.body.innerHTML = {json.dumps(FIXTURE_HTML)};
        const m = await import('/public/js/config.js');
        m.applyConfig(document, m.resolveConfig({json.dumps(cfg)}));
        {READ_FIXTURE}
    """)


def test_exports_are_the_interface(js):
    r = js("""const m = await import('/public/js/config.js');
              return { keys: Object.keys(m), missing: m.MISSING_LABEL, team: m.DEFAULT_TEAM };""")
    # A superset: #18 and #19 may add exports without editing this test.
    assert set(r["keys"]) >= {"DEFAULT_TEAM", "MISSING_LABEL", "applyConfig", "boot", "resolveConfig", "safeUrl"}
    assert r["missing"] == "Link coming soon"
    assert r["team"] == "the WEAVE team"


def test_resolve_returns_only_team_and_three_links(js):
    expected = {"teamName": "Workforce Systems", "urls": FILLED_SITE["links"]}
    assert resolve(js, FILLED_SITE) == expected
    coalesce_only = {**FILLED_SITE, "gitlabProjectUrl": "https://gitlab.example.com/x", "version": "2.4.0",
                     "releaseDate": "23 Sep 2026", "links": {**FILLED_SITE["links"], "access": "https://a.example.com"}}
    assert resolve(js, coalesce_only) == expected


@pytest.mark.parametrize("cfg", [{}, EMPTY_SITE, {"teamName": "   "}, {"teamName": 42}],
                         ids=["empty", "empty-site", "team-blank", "team-number"])
def test_empty_settings_fall_back_quietly(js, cfg):
    r = resolve(js, cfg)
    assert r["urls"] == EMPTY_SITE["links"]
    assert r["teamName"] == "the WEAVE team"


@pytest.mark.parametrize("bad", BAD_LINKS)
def test_unsafe_or_malformed_links_are_dropped(js, bad):
    r = resolve(js, {"links": {"serviceDesk": bad, "tutorial": bad, "docs": bad}})
    assert r["urls"] == EMPTY_SITE["links"]
    assert js(f"const m = await import('/public/js/config.js'); return m.safeUrl({json.dumps(bad)});") == ""


@pytest.mark.parametrize("value, expected", ACCEPTED)
def test_accepted_links_resolve_to_their_trimmed_value(js, value, expected):
    assert resolve(js, {"links": {"docs": value}})["urls"]["docs"] == expected
    assert js(f"const m = await import('/public/js/config.js'); return m.safeUrl({json.dumps(value)});") == expected


def test_apply_fills_links_and_team(js):
    r = apply(js, FILLED_SITE)
    assert r["deskHref"] == FILLED_SITE["links"]["serviceDesk"]
    assert r["deskDisabled"] is None and r["deskMissing"] is False
    assert r["deskText"] == "Open a ticket"
    assert r["team"] == "Workforce Systems"
    # WEAVE's resolved settings have no version, so [data-requires="version"] stays hidden.
    assert r["reqHidden"] is False and r["neverHidden"] is True


def test_apply_marks_missing_links(js):
    r = apply(js, {})
    assert r["deskHref"] is None and r["deskDisabled"] == "true" and r["deskMissing"] is True
    assert r["deskText"] == "Link coming soon"
    assert r["bareTitle"] == "Link coming soon" and r["bareText"] == "Docs"
    assert r["team"] == "the WEAVE team"
    assert r["reqHidden"] is False and r["neverHidden"] is True


def test_boot_reads_window_settings(js):
    href = js(f"""
        document.body.innerHTML = {json.dumps(FIXTURE_HTML)};
        window.WEAVE_SITE = {json.dumps(FILLED_SITE)};
        const m = await import('/public/js/config.js');
        m.boot(window);
        return document.querySelector('#desk').getAttribute('href');
    """)
    assert href == FILLED_SITE["links"]["serviceDesk"]


def test_boot_without_settings_falls_back(js):
    r = js(f"""
        document.body.innerHTML = {json.dumps(FIXTURE_HTML)};
        delete window.WEAVE_SITE;
        const m = await import('/public/js/config.js');
        m.boot(window);
        {READ_FIXTURE}
    """)
    assert r["deskHref"] is None and r["deskMissing"] is True
    assert r["team"] == "the WEAVE team"


# --- The committed site-config.js (#17): its comments, and that it loads. Its values are never read. ---

def test_site_config_comments_explain_every_key():
    text = (PUBLIC / "site-config.js").read_text(encoding="utf-8")
    lines = text.splitlines()
    for key in ["teamName", "serviceDesk", "tutorial", "docs"]:
        assert any(re.search(rf"\b{key}\b", line) and "//" in line for line in lines), key
    assert "public" in text.lower() and "internal" in text.lower()
    assert "Link coming soon" in text


def test_committed_settings_file_loads_with_every_key(make_page, base_url):
    page, errors = open_help(make_page, base_url, site=None)
    assert errors == []
    shape = page.evaluate("""() => { const s = window.WEAVE_SITE;
        return [typeof s.teamName, typeof s.links.serviceDesk, typeof s.links.tutorial, typeof s.links.docs]; }""")
    assert shape == ["string"] * 4
