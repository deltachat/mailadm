import os.path

import pytest

from mailadm.conn import DBError, TokenExhausted, UserNotFound
from mailadm.util import gen_password


def test_token(tmpdir, make_db):
    db = make_db(tmpdir)
    with db.get_connection(closing=True, write=True) as conn:
        assert not conn.get_token_list()
        conn.add_token(name="oneweek", prefix="xyz", expiry="1w", maxuse=5, token="123456789012345")
        conn.commit()
    with db.get_connection(closing=True) as conn:
        assert len(conn.get_token_list()) == 1
        entry = conn.get_tokeninfo_by_name("oneweek")
        assert entry.expiry == "1w"
        assert entry.prefix == "xyz"
        assert entry.usecount == 0

        entry = conn.get_tokeninfo_by_token("123456789012345")
        assert entry.name == "oneweek"
        assert entry.expiry == "1w"
        assert entry.prefix == "xyz"
        assert entry.maxuse == 5

    with db.write_transaction() as conn:
        assert conn.get_token_list()
        conn.del_token(name="oneweek")
        assert not conn.get_token_list()


class TestTokenAccounts:
    MAXUSE = 10

    @pytest.fixture
    def conn(self, tmpdir, make_db):
        db = make_db(tmpdir.mkdir("conn"))
        conn = db.get_connection(write=True)
        conn.add_token(name="onehour", prefix="xyz", expiry="1h",
                       maxuse=self.MAXUSE, token="123456789012345")
        conn.commit()
        return conn

    def test_add_with_wrong_token(self, conn):
        now = 10000
        addr = "tmp.123@x.testrun.org"
        with pytest.raises(DBError):
            conn.add_user(addr=addr, date=now, ttl=60 * 60, token_name="112l3kj123123")

    def test_add_maxuse(self, conn):
        now = 10000
        password = gen_password()
        for i in range(self.MAXUSE):
            addr = "tmp.{}@x.testrun.org".format(i)
            conn.add_user(addr=addr, date=now, ttl=60 * 60, token_name="onehour")

        token_info = conn.get_tokeninfo_by_name("onehour")
        with pytest.raises(TokenExhausted):
            conn.add_email_account(token_info, addr="tmp.xx@x.testrun.org", password=password)

    def test_add_expire_del(self, conn):
        now = 10000
        addr = "tmp.123@x.testrun.org"
        addr2 = "tmp.456@x.testrun.org"
        addr3 = "tmp.789@x.testrun.org"
        conn.add_user(addr=addr, date=now, ttl=60 * 60, token_name="onehour")
        with pytest.raises(DBError):
            conn.add_user(addr=addr, date=now, ttl=60 * 60, token_name="onehour")
        conn.add_user(addr=addr2, date=now, ttl=30 * 60, token_name="onehour")
        conn.add_user(addr=addr3, date=now, ttl=32 * 60, token_name="onehour")
        conn.commit()
        expired = conn.get_expired_users(sysdate=now + 31 * 60)
        assert len(expired) == 1
        assert expired[0].addr == addr2

        users = conn.get_user_list()
        assert len(users) == 3
        conn.del_user(addr2)
        conn.commit()
        assert len(conn.get_user_list()) == 2
        addrs = [u.addr for u in conn.get_user_list()]
        assert addrs == [addr, addr3]
        with pytest.raises(UserNotFound):
            conn.del_user(addr2)
        assert conn.get_tokeninfo_by_name("onehour").usecount == 3


def test_dbmigration_1(db):
    if not os.path.exists("docker-data/mailadm1.sql"):
        pytest.skip("store a DB version 1 dump in docker-data/mailadm1.sql to test DB migration")
    # apply SQL dump
    with open("docker-data/mailadm1.sql", "r") as dump:
        statements = dump.read().split(";\n")
        statements_cleaned = []
        for s in statements:
            if s not in ["PRAGMA foreign_keys=OFF", "BEGIN TRANSACTION", "COMMIT"]:
                statements_cleaned.append(s)
    with db.write_transaction() as conn:
            conn.execute("DROP TABLE users")
            conn.execute("DROP TABLE tokens")
            conn.execute("DROP TABLE config")
            for statement in statements_cleaned:
                conn.execute(statement)

    with db.read_connection() as conn:
        old_token_info = conn.get_tokeninfo_by_name("täst")
        old_user_info = conn.get_user_by_addr("tmp.migrdb@x.testrun.org")
        old_conf = conn.config

    db.ensure_tables()

    with db.read_connection() as conn:
        token_info = conn.get_tokeninfo_by_name("täst")
        user_info = conn.get_user_by_addr("tmp.migrdb@x.testrun.org")
        conf = conn.config

    assert token_info.name == old_token_info.name
    assert token_info.token == old_token_info.token
    assert token_info.expiry == old_token_info.expiry
    assert token_info.prefix == old_token_info.prefix
    assert token_info.maxuse == old_token_info.maxuse
    assert token_info.usecount == old_token_info.usecount

    assert user_info.addr == old_user_info.addr
    assert user_info.date == old_user_info.date
    assert user_info.ttl == old_user_info.ttl
    assert user_info.token_name == old_user_info.token_name

    assert conf.mail_domain == old_conf.mail_domain
    assert conf.web_endpoint == old_conf.web_endpoint
