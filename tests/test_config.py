import pytest
import sys

from mailadm.config import Config, parse_expiry_code


def test_sysconfigsimple(make_ini, tmp_path):
    dbpath = tmp_path.joinpath("db")

    inipath = make_ini("""
        [sysconfig]
        mail_domain = testrun.org
        web_endpoint = https://web.domain
        path_mailadm_db= {}
        path_dovecot_users= /etc/dovecot/users
        path_virtual_mailboxes= /etc/postfix/virtual_mailboxes
        path_vmaildir = /home/vmail/testrun.org
    """.format(dbpath))
    config = Config(inipath)
    sysconfig = config.sysconfig
    assert sysconfig.mail_domain == "testrun.org"
    assert sysconfig.path_dovecot_users == "/etc/dovecot/users"
    assert sysconfig.path_virtual_mailboxes == "/etc/postfix/virtual_mailboxes"
    assert sysconfig.path_vmaildir == "/home/vmail/testrun.org"
    assert sysconfig.path_mailadm_db == str(dbpath)


def test_token_info(make_ini):
    inipath = make_ini("")
    config = Config(inipath)
    config.add_token("burner1", expiry="1w", token="1w_7wDioPeeXyZx96v3", prefix="pp")
    config.add_token("burner2", expiry="10w", token="10w_7wDioPeeXyZx96v3", prefix="xp")

    assert config.get_tokenconfig_by_token("1w_7wDio111111") is None
    tc = config.get_tokenconfig_by_token("1w_7wDioPeeXyZx96v3")
    assert tc.info.expiry == "1w"
    assert tc.info.prefix == "pp"
    assert tc.info.name == "burner1"


def test_email_tmp_gen(make_ini):
    inipath = make_ini("")
    config = Config(inipath)
    config.add_token("burner1", expiry="1w", token="1w_7wDioPeeXyZx96v3", prefix="tmp.")
    tc = config.get_tokenconfig_by_name("burner1")
    email = tc.make_email_address()
    localpart, domain = email.split("@")
    assert localpart.startswith("tmp.")
    assert domain == config.sysconfig.mail_domain

    username = localpart[4:]
    assert len(username) == 5
    for c in username:
        assert c in "2345789acdefghjkmnpqrstuvwxyz"


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
