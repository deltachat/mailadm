import pytest
import sys

from mailadm.config import Config, parse_expiry_code


def test_simple(make_ini):
    inipath = make_ini("""
        [token:burner1]
        domain = testrun.org
        prefix = tmp_
        expiry = 1w
        path_dovecot_users= /etc/dovecot/users
        path_virtual_mailboxes= /etc/postfix/virtual_mailboxes
        path_vmaildir = /home/vmail/testrun.org
        token = 1w_7wDioPeeXyZx96v3
    """)
    config = Config(inipath)
    assert config.get_mail_config_from_token("1qwljkewe") is None
    mc = config.get_mail_config_from_token("1w_7wDioPeeXyZx96v3")
    assert mc.domain == "testrun.org"
    assert mc.prefix == "tmp_"
    assert mc.path_dovecot_users == "/etc/dovecot/users"
    assert mc.path_virtual_mailboxes == "/etc/postfix/virtual_mailboxes"
    assert mc.path_vmaildir == "/home/vmail/testrun.org"


def test_email_check(make_ini):
    inipath = make_ini("""
        [token:burner1]
        domain = testrun.org
        prefix = tmp_
        expiry = 1w
        path_dovecot_users= /etc/dovecot/users
        path_virtual_mailboxes= /etc/postfix/virtual_mailboxes
        path_vmaildir = /home/vmail/testrun.org
        token = 1w_7wDioPeeXyZx96v3

        [token:burner2]
        domain = testrun.org
        prefix =
        expiry = never
        path_dovecot_users= /etc/dovecot/users
        path_virtual_mailboxes= /etc/postfix/virtual_mailboxes
        path_vmaildir = /home/vmail/testrun.org
        token = 1w_7wDioPeeXyZx96v3
    """)
    config = Config(inipath)
    assert config.get_mail_config_from_email("xyz@testrun.o123") is None
    mc = config.get_mail_config_from_email("xyz@testrun.org")
    assert mc.name == "burner2"
    assert mc.expiry == "never"
    assert mc.make_email_address(username="hello") == "hello@testrun.org"

    mc = config.get_mail_config_from_email("tmp_xyz@testrun.org")
    assert mc.name == "burner1"
    assert mc.expiry == "1w"
    assert mc.get_maxdays() == 7


@pytest.mark.parametrize("code,duration", [
    ("never", sys.maxsize),
    ("1w", 7 * 24 * 60 * 60),
    ("2w", 2 * 7 * 24 * 60 * 60),
    ("2d", 2 * 24 * 60 * 60),
    ("5h", 5 * 60 * 60),
    ("15h", 15 * 60 * 60),
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
