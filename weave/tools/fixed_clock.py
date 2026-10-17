"""The one fixed instant WEAVE's tests run at (#12, cross-epic D11): noon on 1 January 2000, before every release,
so no release's news window can contain it.

This module is the instant's only home. tests/conftest.py pins every browser context the shared fixture makes to it,
and the tools that load /weave/ open each page with `now=` set to its date (see weave/README.md, "The fixed test
clock"). No other file writes the literal.
"""
from datetime import datetime

FIXED_INSTANT = "2000-01-01T12:00:00"
FIXED_DATE = datetime.fromisoformat(FIXED_INSTANT).date().isoformat()
