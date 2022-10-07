import pytest
from random import randint
import requests
import time
import mailadm
from mailadm.conn import DBError
from mailadm.mailcow import MailcowError
from mailadm.util import parse_expiry_code


@pytest.fixture
def conn(db):
    with db.write_transaction() as conn:
        yield conn


def test_token_twice(conn):
    conn.add_token("burner1", expiry="1w", token="1w_7wDioPeeXyZx96v3", prefix="pp")
    with pytest.raises(DBError):
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


def test_email_tmp_gen(conn, mailcow):
    conn.add_token("burner1", expiry="1w", token="1w_7wDioPeeXyZx96v3", prefix="tmp.")
    token_info = conn.get_tokeninfo_by_name("burner1")
    user_info = conn.add_email_account(token_info=token_info)

    assert user_info.token_name == "burner1"
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
        token_info = conn.add_token("burner1", expiry="1w", token="1w_7wDioPeeXyZx96v3",
                                    prefix="tmp.", maxuse=1)

    with db.write_transaction() as conn:
        conn.set_config("mailcow_token", "wrong")
        with pytest.raises(MailcowError):
            conn.add_email_account(token_info)

    with db.write_transaction() as conn:
        token_info = conn.get_tokeninfo_by_name(token_info.name)
        token_info.check_exhausted()
        assert conn.get_user_list(token=token_info.name) == []


def test_adduser_db_error(conn, monkeypatch):
    """Test that no mailcow user is created if there is a DB error"""
    token_info = conn.add_token("burner1", expiry="1w", token="1w_7wDioPeeXyZx96v3", prefix="tmp.")
    addr = "pytest.%s@x.testrun.org" % (randint(0, 999),)

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


def test_adduser_mailcow_exists(conn, mailcow):
    """Test that no user is created if Mailcow user already exists"""
    token_info = conn.add_token("burner1", expiry="1w", token="1w_7wDioPeeXyZx96v3", prefix="tmp.")
    addr = "pytest.%s@x.testrun.org" % (randint(0, 999),)

    mailcow.add_user_mailcow(addr, "asdf1234", token_info.name)
    with pytest.raises(MailcowError):
        conn.add_email_account(token_info, addr=addr)
    for user in conn.get_user_list():
        assert user.token_name == "created in mailcow"

    mailcow.del_user_mailcow(addr)


def test_delete_user_mailcow_missing(conn, mailcow):
    """Test if a mailadm user is deleted successfully if mailcow user is already missing"""
    token_info = conn.add_token("burner1", expiry="1w", token="1w_7wDioPeeXyZx96v3", prefix="tmp.")
    addr = "pytest.%s@x.testrun.org" % (randint(0, 999),)

    conn.add_email_account(token_info, addr=addr)
    mailcow.del_user_mailcow(addr)
    conn.delete_email_account(addr)


def test_db_version(conn):
    version = conn.get_dbversion()
    assert type(version) == int


def test_users_to_warn(conn, monkeypatch):
    yeartoken = conn.add_token("1y", token="asd1", expiry="1y", prefix="tmp.")
    monthtoken = conn.add_token("1m", token="asd2", expiry="1m", prefix="tmp.")
    weektoken = conn.add_token("1w", token="asd3", expiry="1w", prefix="tmp.")
    daytoken = conn.add_token("1d", token="asd4", expiry="1d", prefix="tmp.")

    yearuser = conn.add_email_account(yeartoken)
    monthuser = conn.add_email_account(monthtoken)
    weekuser = conn.add_email_account(weektoken)
    dayuser = conn.add_email_account(daytoken)

    def futuredate(code, basedate=int(time.time())):
        return basedate + parse_expiry_code(code)

    # test day user warning
    assert not conn.get_expired_users(futuredate("20h"))
    assert conn.get_expired_users(futuredate("25h"))[0].addr == dayuser.addr
    users = conn.get_users_to_warn(futuredate("20h"))
    assert len(users) == 1
    assert "360 minutes" in users[0]["message"]
    assert users[0]["user"].addr == dayuser.addr

    # test week user warning
    sysdate = futuredate("6d")
    users = conn.get_users_to_warn(sysdate)
    assert len(users) == 2
    for user in users:
        conn.increment_warning_count(user["user"])
        if user["user"].addr == weekuser.addr:
            assert "1 day" in user["message"]
    assert not conn.get_users_to_warn(sysdate)
    expired_users = conn.get_expired_users(sysdate)
    assert len(expired_users) == 1

    # test month user warning
    sysdate = futuredate("23d")
    users = conn.get_users_to_warn(sysdate)
    assert len(users) == 1
    assert "7 days" in users[0]["message"]
    assert users[0]["user"].addr == monthuser.addr
    conn.increment_warning_count(users[0]["user"])
    expired_users = conn.get_expired_users(sysdate)
    assert len(expired_users) == 2

    # test day/week/month expiry and yearly user warning
    sysdate = futuredate("340d")
    expired_users = conn.get_expired_users(sysdate)
    assert len(expired_users) == 3
    for user in expired_users:
        conn.delete_email_account(user.addr)
    expired_users = conn.get_expired_users(sysdate)
    assert len(expired_users) == 0

    users = conn.get_users_to_warn(sysdate)
    assert len(users) == 1
    assert users[0]["user"].addr == yearuser.addr
    assert "30 days" in users[0]["message"]
    conn.increment_warning_count(users[0]["user"])

    sysdate = futuredate("363d")
    users = conn.get_users_to_warn(sysdate)
    assert len(users) == 1
    assert users[0]["user"].addr == yearuser.addr
    assert "7 days" in users[0]["message"]
    conn.increment_warning_count(users[0]["user"])

    sysdate += parse_expiry_code("20h")
    users = conn.get_users_to_warn(sysdate)
    assert len(users) == 0

    sysdate = futuredate("364d")
    users = conn.get_users_to_warn(sysdate)
    assert len(users) == 1
    assert users[0]["user"].addr == yearuser.addr
    assert "1 day" in users[0]["message"]
    conn.increment_warning_count(users[0]["user"])

    sysdate = futuredate("366d")
    expired_users = conn.get_expired_users(sysdate)
    assert len(expired_users) == 1
    conn.delete_email_account(expired_users[0].addr)
    expired_users = conn.get_expired_users(sysdate)
    assert len(expired_users) == 0


def test_remember_warning(conn):
    daytoken = conn.add_token("1d", token="asdf", expiry="1d", prefix="tmp.")
    conn.add_email_account(daytoken)

    sysdate = int(time.time())
    # add 20 hours to time
    sysdate += parse_expiry_code("20h")
    users = conn.get_users_to_warn(sysdate)
    assert len(users) == 1
    # don't remember warning

    # add 1 hour to time
    sysdate += parse_expiry_code("1h")
    users = conn.get_users_to_warn(sysdate)
    assert len(users) == 1
    conn.increment_warning_count(users[0]["user"])

    # add 1 hour to time
    sysdate += parse_expiry_code("1h")
    users = conn.get_users_to_warn(sysdate)
    assert len(users) == 0

    # add 3 hours to time
    sysdate += parse_expiry_code("3h")
    expired_users = conn.get_expired_users(sysdate)
    assert len(expired_users) == 1
    conn.delete_email_account(expired_users[0].addr)
    expired_users = conn.get_expired_users(sysdate)
    assert len(expired_users) == 0
