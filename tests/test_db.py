

import pytest
from mailadm.db import DB, get_doveadm_pw


def test_token(tmp_path):
    db = DB(tmp_path.joinpath("mailadm.db"), config=None)
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


def test_get_doveadm_pw():
    clear, hash_pw = get_doveadm_pw("hello")
    assert clear == "hello"
    assert hash_pw.startswith("{SHA512-CRYPT}")


class TestTokenAccounts:
    MAXUSE = 10

    @pytest.fixture
    def conn(self, tmpdir, make_config):
        config = make_config(tmpdir.join("conn"))

        db = DB(config.db.sqlpath, config=config)
        conn = db.get_connection(write=True)
        conn.add_token(name="onehour", prefix="xyz", expiry="1h",
                       maxuse=self.MAXUSE, token="123456789012345")
        conn.commit()
        return conn

    def test_add_with_wrong_token(self, conn):
        now = 10000
        addr = "tmp.123@testrun.org"
        clear_pw, hash_pw = get_doveadm_pw()
        with pytest.raises(ValueError):
            conn.add_user(addr=addr, hash_pw=hash_pw,
                          date=now, ttl=60 * 60, token_name="112l3kj123123")

    def test_add_maxuse(self, conn):
        now = 10000
        clear_pw, hash_pw = get_doveadm_pw()
        for i in range(self.MAXUSE):
            addr = "tmp.{}@testrun.org".format(i)
            conn.add_user(addr=addr, hash_pw=hash_pw, date=now, ttl=60 * 60, token_name="onehour")

        with pytest.raises(ValueError):
            conn.add_user(addr="tmp.xx@testrun.org", hash_pw=hash_pw,
                          date=now, ttl=60 * 60, token_name="onehour")

    def test_different_vmaildirs(self, conn):
        clear_pw, hash_pw = get_doveadm_pw()
        conn.add_user(
            addr="tmp.1@testrun.org", hash_pw=hash_pw,
            date=10, ttl=60 * 60, token_name="onehour")
        conn.add_user(
            addr="tmp.2@testrun.org", hash_pw=hash_pw,
            date=11, ttl=60 * 60, token_name="onehour")
        conn.gen_sysfiles()
        with open(conn.config.sysconfig.path_dovecot_users) as f:
            vmaildirs = set()
            for line in f:
                # {addr}:{hash_pw}:{dovecot_uid}:{dovecot_gid}::{user_vmaildir}::
                parts = line.strip().split(":")
                vmaildir = parts[5]
                if vmaildir and vmaildir in vmaildirs:
                    pytest.fail("duplicate vmaildir: {}".format(vmaildir))
                vmaildirs.add(vmaildir)

    def test_add_expire_del(self, conn):
        now = 10000
        addr = "tmp.123@testrun.org"
        addr2 = "tmp.456@testrun.org"
        addr3 = "tmp.789@testrun.org"
        clear_pw, hash_pw = get_doveadm_pw()
        conn.add_user(addr=addr, hash_pw=hash_pw, date=now, ttl=60 * 60, token_name="onehour")
        with pytest.raises(ValueError):
            conn.add_user(addr=addr, hash_pw=hash_pw, date=now, ttl=60 * 60, token_name="onehour")
        conn.add_user(addr=addr2, hash_pw=hash_pw, date=now, ttl=30 * 60, token_name="onehour")
        conn.add_user(addr=addr3, hash_pw=hash_pw, date=now, ttl=32 * 60, token_name="onehour")
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
        with pytest.raises(ValueError):
            conn.del_user(addr2)
        assert conn.get_tokeninfo_by_name("onehour").usecount == 3
