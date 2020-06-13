import pytest
import sys

from pathlib import Path

from mailadm.config import Config
from mailadm.db import parse_expiry_code


@pytest.fixture
def conn(make_ini):
    inipath = make_ini("")
    config = Config(inipath)
    with config.write_transaction() as conn:
        yield conn


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


def test_token_twice(conn):
    conn.add_token("burner1", expiry="1w", token="1w_7wDioPeeXyZx96v3", prefix="pp")
    with pytest.raises(ValueError):
        conn.add_token("burner2", expiry="1w", token="1w_7wDioPeeXyZx96v3", prefix="xp")


def test_token_info(conn):
    conn.add_token("burner1", expiry="1w", token="1w_7wDioPeeXyZx96v3", prefix="pp")
    conn.add_token("burner2", expiry="10w", token="10w_7wDioPeeXyZx96v3", prefix="xp")

    assert conn.get_tokeninfo_by_token("1w_7wDio111111") is None
    ti = conn.get_tokeninfo_by_token("1w_7wDioPeeXyZx96v3")
    assert ti.expiry == "1w"
    assert ti.prefix == "pp"
    assert ti.name == "burner1"
    conn.del_token("burner2")
    assert not conn.get_tokeninfo_by_token("10w_7wDioPeeXyZx96v3")
    assert not conn.get_tokeninfo_by_name("burner2")


def test_email_tmp_gen(conn):
    conn.add_token("burner1", expiry="1w", token="1w_7wDioPeeXyZx96v3", prefix="tmp.")
    token_info = conn.get_tokeninfo_by_name("burner1")
    user_info = conn.add_email_account(token_info=token_info)

    assert user_info.token_name == "burner1"
    localpart, domain = user_info.addr.split("@")
    assert localpart.startswith("tmp.")
    assert domain == conn.config.sysconfig.mail_domain

    username = localpart[4:]
    assert len(username) == 5
    for c in username:
        assert c in "2345789acdefghjkmnpqrstuvwxyz"


def test_gen_sysfiles(make_ini_from_values):
    inipath = make_ini_from_values(
        name="burner1", expiry="1w", token="1w_7wDioPeeXyZx96v3", prefix="pp")
    config = Config(inipath)
    with config.write_transaction() as conn:
        token_info = conn.get_tokeninfo_by_name("burner1")

        NUM_USERS = 50
        users = []
        for i in range(NUM_USERS):
            users.append(conn.add_email_account(token_info))

        user_list = conn.get_user_list()
        config.sysconfig.gen_sysfiles(user_list)

    # check dovecot user db was generated
    p = Path(config.sysconfig.path_dovecot_users)
    data = p.read_text()
    for user in users:
        assert user.addr in data and user.hash_pw in data

    # check postfix virtual mailboxes was generated
    p = Path(config.sysconfig.path_virtual_mailboxes)
    data = p.read_text()
    for user in users:
        assert user.addr in data


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
