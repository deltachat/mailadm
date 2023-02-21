import pytest
from mailadm.conn import DBError, TokenExhaustedError, UserNotFoundError
from mailadm.util import gen_password


def test_token(tmpdir, make_db):
    db = make_db(tmpdir)
    with db._get_connection(closing=True, write=True) as conn:
        assert not conn.get_token_list()
        conn.add_token(name="pytest:1w", prefix="xyz", expiry="1w", maxuse=5, token="1234567890123")
        conn.commit()
    with db._get_connection(closing=True) as conn:
        assert len(conn.get_token_list()) == 1
        entry = conn.get_tokeninfo_by_name("pytest:1w")
        assert entry.expiry == "1w"
        assert entry.prefix == "xyz"
        assert entry.usecount == 0

        entry = conn.get_tokeninfo_by_token("1234567890123")
        assert entry.name == "pytest:1w"
        assert entry.expiry == "1w"
        assert entry.prefix == "xyz"
        assert entry.maxuse == 5

    with db.write_transaction() as conn:
        assert conn.get_token_list()
        conn.del_token(name="pytest:1w")
        assert not conn.get_token_list()


class TestTokenAccounts:
    MAXUSE = 10

    @pytest.fixture
    def conn(self, tmpdir, make_db):
        db = make_db(tmpdir.mkdir("conn"))
        conn = db._get_connection(write=True)
        conn.add_token(
            name="pytest:1h",
            prefix="xyz",
            expiry="1h",
            maxuse=self.MAXUSE,
            token="123456789012345",
        )
        conn.commit()
        return conn

    def test_add_with_wrong_token(self, conn, mailcow_domain):
        now = 10000
        addr = "tmp.123@" + mailcow_domain
        with pytest.raises(DBError):
            conn.add_user_db(addr=addr, date=now, ttl=60 * 60, token_name="112l3kj123123")

    def test_add_maxuse(self, conn, mailcow_domain):
        now = 10000
        password = gen_password()
        for i in range(self.MAXUSE):
            addr = "tmp.%s@%s" % (i, mailcow_domain)
            conn.add_user_db(addr=addr, date=now, ttl=60 * 60, token_name="pytest:1h")

        token_info = conn.get_tokeninfo_by_name("pytest:1h")
        with pytest.raises(TokenExhaustedError):
            conn.add_email_account(token_info, addr="tmp.xx@" + mailcow_domain, password=password)

    def test_add_expire_del(self, conn, mailcow_domain):
        now = 10000
        addr = "tmp.123@" + mailcow_domain
        addr2 = "tmp.456@" + mailcow_domain
        addr3 = "tmp.789@" + mailcow_domain
        conn.add_user_db(addr=addr, date=now, ttl=60 * 60, token_name="pytest:1h")
        with pytest.raises(DBError):
            conn.add_user_db(addr=addr, date=now, ttl=60 * 60, token_name="pytest:1h")
        conn.add_user_db(addr=addr2, date=now, ttl=30 * 60, token_name="pytest:1h")
        conn.add_user_db(addr=addr3, date=now, ttl=32 * 60, token_name="pytest:1h")
        conn.commit()
        expired = conn.get_expired_users(sysdate=now + 31 * 60)
        assert len(expired) == 1
        assert expired[0].addr == addr2

        users = conn.get_user_list(token="pytest:1h")
        assert len(users) == 3
        conn.del_user_db(addr2)
        conn.commit()
        assert len(conn.get_user_list(token="pytest:1h")) == 2
        addrs = [u.addr for u in conn.get_user_list(token="pytest:1h")]
        assert addrs == [addr, addr3]
        with pytest.raises(UserNotFoundError):
            conn.del_user_db(addr2)
        assert conn.get_tokeninfo_by_name("pytest:1h").usecount == 3
