
from pathlib import Path

import pytest
from mailadm.db import Storage


def test_token(tmp_path):
    db = Storage(tmp_path.joinpath("mailadm.db"))
    with db.get_connection(closing=True, write=True) as conn:
        assert not conn.get_token_list()
        conn.add_token(name="oneweek", prefix="xyz", expiry="1w", token="123456789012345")
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


class TestTokenAccounts:
    @pytest.fixture
    def conn(self, tmpdir):
        pathdir = tmpdir.mkdir("paths")
        path = pathdir.join("tokenusers.db")
        db = Storage(Path(path.strpath))
        conn = db.get_connection(write=True)
        conn.add_token(name="onehour", prefix="xyz", expiry="1h", token="123456789012345")
        conn.commit()
        return conn

    def test_add_expire_del(self, conn):
        now = 10000
        addr = "tmp.123@testrun.org"
        addr2 = "tmp.456@testrun.org"
        conn.add_user(addr=addr, date=now, expiry=60*60, token="123456789012345")
        conn.add_user(addr=addr2, date=now, expiry=30*60, token="123456789012345")
        conn.commit()
        expired = conn.get_expired_users(sysdate=now+31*60)
        assert len(expired) == 1
        assert expired == [addr2]

        assert conn.get_user_list() == [addr, addr2]
        conn.delete_user(addr2)
        assert conn.get_user_list() == [addr]
