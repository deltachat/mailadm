import random
import time

import mailadm
from mailadm.web import create_app_from_db_path


def test_new_user_random(request, db, monkeypatch, mailcow, mailcow_domain):
    token = "12319831923123"
    with db.write_transaction() as conn:
        conn.add_token(name="pytest", token=token, prefix="pytest.", expiry="1w")

    app = create_app_from_db_path(db.path)
    app.debug = True
    app = app.test_client()

    r = app.post("/?username=hello")
    assert r.status_code == 403
    assert r.json.get("reason") == "?t (token) parameter not specified"
    r = app.post("/?t=00000")
    assert r.status_code == 403
    assert r.json.get("reason") == "token 00000 is invalid"
    r = app.post("/?t=123123&username=hello")
    assert r.status_code == 403
    assert r.json.get("reason") == "token 123123 is invalid"

    # delete a@x.testrun.org and b@x.testrun.org in case earlier tests failed to clean them up
    user_a = "pytest.a@" + mailcow_domain
    user_b = "pytest.b@" + mailcow_domain

    def clean_up_test_users():
        mailcow.del_user_mailcow(user_a)
        mailcow.del_user_mailcow(user_b)

    request.addfinalizer(clean_up_test_users)

    chars = list("ab")

    def get_human_readable_id(*args, **kwargs):
        return random.choice(chars)

    monkeypatch.setattr(mailadm.util, "get_human_readable_id", get_human_readable_id)

    r = app.post("/?t=" + token)
    assert r.status_code == 200
    assert r.json["email"].endswith(mailcow_domain)
    assert r.json["password"]
    email = r.json["email"]
    assert email in [user_a, user_b]

    r2 = app.post("/?t=" + token)
    assert r2.status_code == 200
    assert r2.json["email"] != email
    assert r2.json["email"] in [user_a, user_b]

    r3 = app.post("/?t=" + token)
    assert r3.status_code == 409
    assert r3.json.get("reason") == "user already exists in mailcow"

    mailcow.del_user_mailcow(email)
    mailcow.del_user_mailcow(r2.json["email"])


def test_env(db, monkeypatch):
    monkeypatch.setenv("MAILADM_DB", str(db.path))
    from mailadm.app import app

    assert app.db.path == db.path


def test_user_in_db(db, mailcow):
    with db.write_transaction() as conn:
        token = conn.add_token("pytest:web", expiry="1w", token="1w_7wDioPeeXyZx96v", prefix="")
    app = create_app_from_db_path(db.path)
    app.debug = True
    app = app.test_client()

    r = app.post("/?t=" + token.token)
    assert r.status_code == 200
    assert r.json["password"]
    addr = r.json["email"]

    assert mailcow.get_user(addr)
    with db.read_connection() as conn:
        assert conn.get_user_by_addr(addr)

    with db.write_transaction() as conn:
        conn.delete_email_account(addr)


# we used to allow setting the username/password through the web
# but the code has been removed, let's keep the test around
def xxxtest_new_user_usermod(db, mailcow_domain):
    app = create_app_from_db_path(db.path)
    app.debug = True
    app = app.test_client()

    r = app.post("/?t=00000")
    assert r.status_code == 403

    r = app.post("/?t=123123123123123&username=hello")
    assert r.status_code == 200

    assert r.json["email"] == "hello@" + mailcow_domain
    assert len(r.json["password"]) >= 12

    now = time.time()
    r = app.post("/?t=123123123123123&username=hello2&password=l123123123123")
    assert r.status_code == 200
    assert r.json["email"] == "hello2@" + mailcow_domain
    assert r.json["password"] == "l123123123123"
    assert int(r.json["expires"]) > (now + 4 * 24 * 60 * 60)
