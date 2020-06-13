import pytest
import sys

from mailadm.config import Config
from mailadm.db import parse_expiry_code


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
        dovecot_uid = 1000
        dovecot_gid = 1000
    """.format(dbpath))
    config = Config(inipath)
    sysconfig = config.sysconfig
    assert sysconfig.mail_domain == "testrun.org"
    assert sysconfig.path_dovecot_users == "/etc/dovecot/users"
    assert sysconfig.path_virtual_mailboxes == "/etc/postfix/virtual_mailboxes"
    assert sysconfig.path_vmaildir == "/home/vmail/testrun.org"
    assert sysconfig.path_mailadm_db == str(dbpath)

@pytest.fixture
def conn(make_ini):
    inipath = make_ini("")
    config = Config(inipath)
    with config.write_transaction() as conn:
        yield conn

def test_token_twice(conn):
    conn.add_token("burner1", expiry="1w", token="1w_7wDioPeeXyZx96v3", prefix="pp")
    with pytest.raises(ValueError):
        conn.add_token("burner2", expiry="1w", token="1w_7wDioPeeXyZx96v3", prefix="xp")


def test_token_info(conn):
    conn.add_token("burner1", expiry="1w", token="1w_7wDioPeeXyZx96v3", prefix="pp")
    conn.add_token("burner2", expiry="10w", token="10w_7wDioPeeXyZx96v3", prefix="xp")

    assert conn.get_tokenconfig_by_token("1w_7wDio111111") is None
    tc = conn.get_tokenconfig_by_token("1w_7wDioPeeXyZx96v3")
    assert tc.info.expiry == "1w"
    assert tc.info.prefix == "pp"
    assert tc.info.name == "burner1"
    conn.del_token("burner2")
    assert not conn.get_tokenconfig_by_token("10w_7wDioPeeXyZx96v3")
    assert not conn.get_tokenconfig_by_name("burner2")


def test_email_tmp_gen(conn):
    conn.add_token("burner1", expiry="1w", token="1w_7wDioPeeXyZx96v3", prefix="tmp.")
    tc = conn.get_tokenconfig_by_name("burner1")
    user_info = conn.add_email_account(token_config=tc)

    assert user_info.token_name == "burner1"
    localpart, domain = user_info.addr.split("@")
    assert localpart.startswith("tmp.")
    assert domain == conn.config.sysconfig.mail_domain

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
