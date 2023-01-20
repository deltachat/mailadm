
import sys
import pytest

from mailadm.util import parse_expiry_code, get_human_readable_id


@pytest.mark.parametrize(("code", "duration"), [
    ("never", sys.maxsize),
    ("1w", 7 * 24 * 60 * 60),
    ("2w", 2 * 7 * 24 * 60 * 60),
    ("2d", 2 * 24 * 60 * 60),
    ("5h", 5 * 60 * 60),
    ("15h", 15 * 60 * 60),
    ("20s", 20),
    ("0h", 0),
])
def test_parse_expiries(code, duration):
    res = parse_expiry_code(code)
    assert res == duration


def test_parse_expiries_short():
    with pytest.raises(ValueError):
        parse_expiry_code("h")


def test_parse_expiries_wrong():
    with pytest.raises(ValueError):
        parse_expiry_code("123h123d")
    with pytest.raises(ValueError):
        parse_expiry_code("12j")


def test_human_readable_id():
    s = get_human_readable_id(len=20)
    assert s.isalnum()
