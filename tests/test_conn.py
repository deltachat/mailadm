import time
from random import randint

import deltachat
import mailadm
import pytest
import requests
from mailadm.conn import DBError, InvalidInputError
from mailadm.mailcow import MailcowError
from mailadm.util import parse_expiry_code


@pytest.fixture
def conn(db):
    with db.write_transaction() as conn:
        yield conn


def test_token_twice(conn):
    conn.add_token("pytest:burner1", expiry="1w", token="1w_7wDioPeeXyZx96v3", prefix="pp")
    with pytest.raises(DBError):
        conn.add_token("pytest:burner2", expiry="1w", token="1w_7wDioPeeXyZx96v3", prefix="xp")


def test_add_del_user(conn, mailcow):
    token = conn.add_token("pytest:burner1", expiry="1w", token="1w_7wDioPeeXyZx96v3", prefix="pp")
    usecount = conn.get_tokeninfo_by_name(token.name).usecount
    addr = conn.add_email_account_tries(token, tries=10).addr
    assert usecount + 1 == conn.get_tokeninfo_by_name(token.name).usecount

    assert mailcow.get_user(addr)
    assert conn.get_user_by_addr(addr)

    conn.delete_email_account(addr)

    with pytest.raises(TypeError):
        conn.get_user_by_addr(addr)
    assert not mailcow.get_user(addr)


def test_token_info(conn):
    conn.add_token("pytest:burner1", expiry="1w", token="1w_7wDioPeeXyZx96v3", prefix="pp")
    conn.add_token("pytest:burner2", expiry="10w", token="10w_7wDioPeeXyZx96v3", prefix="xp")

    assert conn.get_tokeninfo_by_token("1w_7wDio111111") is None
    ti = conn.get_tokeninfo_by_token("1w_7wDioPeeXyZx96v3")
    assert ti.expiry == "1w"
    assert ti.prefix == "pp"
    assert ti.name == "pytest:burner1"
    conn.del_token("pytest:burner2")
    assert not conn.get_tokeninfo_by_token("10w_7wDioPeeXyZx96v3")
    assert not conn.get_tokeninfo_by_name("pytest:burner2")


@pytest.mark.parametrize(
    ("localpart", "result"),
    [
        ("weirdinput.{}@test1@", False),
        ("weirdinput.{}@a", False),
        ("weirdinput.{}@x.testrun.org@test4@", False),
        ("weirdinput.{}/../../@", False),
        ("weirdinput.{}?test6@", False),
        ("weirdinput.{}#test7@", False),
        ("weirdinput./{}@", False),
        ("weirdinput.%2f{}@", False),
        ("weirdinput.{}\\test9\\\\@", False),
        ("weirdinput-{}@", True),
        ("weirdinput.{}", False),
        ("weirdinput+{}@", False),
        ("¹weirdinput.{}@", False),
        ("-weirdinput.{}@", False),
        ("_weirdinput.{}@", False),
        (".weirdinput.{}@", False),
        ("½weirdinput.{}@", False),
        ("weirdinput_{}@", True),
    ],
)
def test_is_email_valid(conn, localpart, result, mailcow_domain):
    addr = localpart.format(randint(0, 99999)) + mailcow_domain
    assert conn.is_valid_email(addr) == result


@pytest.mark.parametrize(
    ("token_name", "result"),
    [
        ("../test", False),
        ("../../test", False),
        ("../../abc/../test", False),
        (".abc/../test/fixed", False),
        ("/test/foo", False),
        ("./test/baz", False),
        (".testbaz", False),
        ("test%baz", False),
        ("test?secret=asdf", False),
        ("test#somewhere", False),
        ("baz123-._@", True),
    ],
)
def test_token_sanitization(conn, token_name, result):
    if result:
        conn.add_token(token_name, expiry="1w", token="1w_7wDioPeeXyZx96va3", prefix="pp")
    else:
        with pytest.raises(InvalidInputError):
            conn.add_token(token_name, expiry="1w", token="1w_7wDioPeeXyZx96va3", prefix="pp")


def test_email_tmp_gen(conn, mailcow):
    conn.add_token("pytest:burner1", expiry="1w", token="1w_7wDioPeeXyZx96v3", prefix="tmp.")
    token_info = conn.get_tokeninfo_by_name("pytest:burner1")
    user_info = conn.add_email_account(token_info=token_info)

    assert user_info.token_name == "pytest:burner1"
    localpart, domain = user_info.addr.split("@")
    assert localpart.startswith("tmp.")
    assert domain == conn.config.mail_domain

    username = localpart[4:]
    assert len(username) == 5
    for c in username:
        assert c in "2345789acdefghjkmnpqrstuvwxyz"

    mailcow.del_user_mailcow(user_info.addr)


def test_adduser_mailcow_error(db):
    """Test that DB doesn't change if mailcow doesn't work"""
    with db.write_transaction() as conn:
        token_info = conn.add_token(
            "pytest:burner1",
            expiry="1w",
            token="1w_7wDioPeeXyZx96v3",
            prefix="tmp.",
            maxuse=1,
        )

    with db.write_transaction() as conn:
        conn.set_config("mailcow_token", "wrong")
        with pytest.raises(MailcowError):
            conn.add_email_account(token_info)

    with db.write_transaction() as conn:
        token_info = conn.get_tokeninfo_by_name(token_info.name)
        token_info.check_exhausted()
        assert conn.get_user_list(token=token_info.name) == []


def test_adduser_db_error(conn, monkeypatch, mailcow_domain):
    """Test that no mailcow user is created if there is a DB error"""
    token_info = conn.add_token(
        "pytest:burner1",
        expiry="1w",
        token="1w_7wDioPeeXyZx96v3",
        prefix="tmp.",
    )
    addr = "pytest.%s@%s" % (randint(0, 99999), mailcow_domain)

    def add_user_db(*args, **kwargs):
        raise DBError

    monkeypatch.setattr(mailadm.conn.Connection, "add_user_db", add_user_db)

    with pytest.raises(DBError):
        conn.add_email_account(token_info, addr=addr)

    url = "%sget/mailbox/%s" % (conn.config.mailcow_endpoint, addr)
    auth = {"X-API-Key": conn.config.mailcow_token}
    result = requests.get(url, headers=auth)
    assert result.status_code == 200
    if result.json() is not {} and type(result.json()) == list:
        for user in result.json():
            assert user["username"] != addr


def test_adduser_mailcow_exists(conn, mailcow, mailcow_domain):
    """Test that no user is created if Mailcow user already exists"""
    token_info = conn.add_token("pytest:burner1", expiry="1w", token="1w_7wDioPeeXyZx", prefix="p.")
    addr = "%s@%s" % (randint(0, 99999), mailcow_domain)

    mailcow.add_user_mailcow(addr, "asdf1234", token_info.name)
    with pytest.raises(MailcowError):
        conn.add_email_account(token_info, addr=addr)
    for user in conn.get_user_list():
        assert user.token_name == "created in mailcow"

    mailcow.del_user_mailcow(addr)


@pytest.mark.parametrize(
    ("expiry", "time_overdue", "time_since_last_login", "to_be_pruned"),
    [
        ("1h", "1h", "0s", True),
        ("1s", "1s", "0s", True),
        ("5w", "2w", "1w", False),
        ("2y", "2y", "20d", False),
        ("2y", "1d", "1y", True),
        ("90d", "30d", "2d", False),
    ],
)
def test_soft_expiry(conn, mailcow_domain, tmp_db_path, monkeypatch, expiry, time_overdue,
                     time_since_last_login, to_be_pruned, mailcow):
    """Test whether a user expires depending on last login"""
    to_expire = time.time() - parse_expiry_code(expiry) - parse_expiry_code(time_overdue)
    # create an account which is living for longer than its expiry time so far
    with monkeypatch.context() as m:
        m.setattr(time, "time", lambda: to_expire)
        token_info = conn.add_token("pytest:soft", expiry=expiry, token="1w_7wDioPeex", prefix="p.")
        addr = "pytest.%s@%s" % (randint(0, 99999), mailcow_domain)
        mailadm_user = conn.add_email_account(token_info, addr=addr)

    # login with IMAP
    ac = deltachat.Account(tmp_db_path)
    ac.run_account(addr=mailadm_user.addr, password=mailadm_user.password)

    # make mailadm think that it's in the future and user hasn't been logged in for a while
    future = time.time() + parse_expiry_code(time_since_last_login)

    expired_users = conn.get_expired_users(future)
    expired = mailadm_user.addr in [user.addr for user in expired_users]
    assert expired == to_be_pruned

    mailcow.del_user_mailcow(addr)


def test_delete_user_mailcow_missing(conn, mailcow, mailcow_domain):
    """Test if a mailadm user is deleted successfully if mailcow user is already missing"""
    token_info = conn.add_token("pytest:burner1", expiry="1w", token="1w_7wDioPeeXyZx", prefix="p.")
    addr = "pytest.%s@%s" % (randint(0, 99999), mailcow_domain)

    conn.add_email_account(token_info, addr=addr)
    mailcow.del_user_mailcow(addr)
    conn.delete_email_account(addr)


def test_db_version(conn):
    version = conn.get_dbversion()
    assert type(version) == int
