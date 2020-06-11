
import pytest
from mailadm.db import Storage


def test_token(tmp_path):
    db = Storage(tmp_path.joinpath("mailadm.db"))
    with db.get_connection(write=True) as conn:
        assert not conn.get_token_list()
        conn.add_token(name="oneweek", prefix="xyz", expiry="1w", token="123456789012345")
        conn.commit()
    with db.get_connection() as conn:
        assert len(conn.get_token_list()) == 1
        entry = conn.get_tokeninfo_by_name("oneweek")
        assert entry.expiry == "1w"
        assert entry.prefix == "xyz"
        assert entry.usecount == 0

        entry = conn.get_tokeninfo_by_token("123456789012345")
        assert entry.name == "oneweek"
        assert entry.expiry == "1w"
        assert entry.prefix == "xyz"
