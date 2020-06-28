import pytest

from mailadm.conn import DBError


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


def test_email_tmp_gen(conn):
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


def test_gen_sysfiles(db):
    with db.write_transaction() as conn:
        conn.add_token(name="burner1", expiry="1w", token="1w_7wDioPeeXyZx96v3", prefix="pp")

    with db.write_transaction() as conn:
        token_info = conn.get_tokeninfo_by_name("burner1")

        NUM_USERS = 50
        users = []
        for i in range(NUM_USERS):
            users.append(conn.add_email_account(token_info))

        conn.gen_sysfiles()
        config = conn.config

    # check postfix virtual mailboxes was generated
    data = config.path_virtual_mailboxes.read_text()
    for user in users:
        assert data.count(user.addr) == 2
