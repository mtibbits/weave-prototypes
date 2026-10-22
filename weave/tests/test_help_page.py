"""The Help page (#17): its shell, placeholder still, three help cards and the links site-config.js gives them."""
from pathlib import Path

from helpers import jpeg_size

PUBLIC = Path(__file__).resolve().parents[1] / "public"


def test_help_still_is_1600_by_1000_and_at_most_250_kb():
    data = (PUBLIC / "assets" / "help-still.jpg").read_bytes()
    assert len(data) <= 250_000
    assert jpeg_size(data) == (1600, 1000)
