"""Keyboard focus and text contrast, each helper proven against a planted failure first."""
import pytest

from helpers import contrast_failures, focus_failures, open_page


def test_focus_failures_catches_a_missing_outline(make_page, base_url):
    page, _ = open_page(make_page, base_url)
    page.add_style_tag(content='a[href="#panels"]:focus-visible { outline: none; }')
    failures = focus_failures(page)
    assert any("What's in it" in f for f in failures), failures


def test_contrast_failures_catches_low_contrast_text(make_page, base_url):
    page, _ = open_page(make_page, base_url)
    page.add_style_tag(content=".lede { color: #C9C2B4; }")
    failures = contrast_failures(page)
    assert any(f["text"].startswith("WEAVE is the planned web dashboard") for f in failures), failures


def test_helpers_fail_closed_on_an_empty_page(make_page, base_url):
    page = make_page()
    page.goto(f"{base_url}/tests/blank.html")
    with pytest.raises(AssertionError):
        focus_failures(page)
    with pytest.raises(AssertionError):
        contrast_failures(page)


def test_tab_reaches_every_link_and_button_with_a_visible_outline(make_page, base_url):
    page, _ = open_page(make_page, base_url)
    assert focus_failures(page) == []


@pytest.mark.parametrize("width", [390, 1440])
def test_text_meets_contrast(make_page, base_url, width):
    # The h1's terracotta em (3.52:1, large) exercises the 3:1 branch.
    page, _ = open_page(make_page, base_url, viewport={"width": width, "height": 844})
    assert contrast_failures(page) == []
