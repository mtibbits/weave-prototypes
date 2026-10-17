"""#12's release rules (release.js), their boot wiring (stage.__weaveRelease), and the fixed test clock."""
import subprocess
from datetime import datetime
from pathlib import Path

import conftest
import fixed_clock
from conftest import FIXED_DATE, FIXED_INSTANT

WEAVE = Path(__file__).resolve().parents[1]


# --- The clock: one instant, one home (D11). ---


def test_fixed_instant_is_noon_on_2000_01_01():
    assert datetime.fromisoformat(FIXED_INSTANT) == datetime(2000, 1, 1, 12, 0, 0)
    assert FIXED_DATE == datetime.fromisoformat(FIXED_INSTANT).date().isoformat()


def weave_files():
    """Every file git would ship under weave/ (tracked, plus untracked files that are not ignored), as paths."""
    out = subprocess.run(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"], cwd=WEAVE,
                         capture_output=True, check=True).stdout
    return sorted({name for name in out.decode("utf-8").split("\0") if name and (WEAVE / name).is_file()})


def test_fixed_instant_has_one_home():
    """The literal is written only in tools/fixed_clock.py; the planted positive is that module itself."""
    needle = FIXED_INSTANT.encode("ascii")
    hits = [name for name in weave_files() if needle in (WEAVE / name).read_bytes()]
    assert hits == ["tools/fixed_clock.py"], hits
    assert conftest.FIXED_INSTANT is fixed_clock.FIXED_INSTANT
    assert "from fixed_clock import FIXED_DATE, FIXED_INSTANT" in (WEAVE / "tests" / "conftest.py").read_text(
        encoding="utf-8")

