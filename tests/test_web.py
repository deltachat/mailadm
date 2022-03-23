import time
from mailadm.web import create_app_from_db_path
from mailadm.mailcow import MailcowConnection
import mailadm
import random


def test_new_user_random(db, monkeypatch):
    token = "12319831923123"
    with db.write_transaction() as conn:
        conn.add_token(name="test123", token=token, prefix="pytest.", expiry="1w")

    app = create_app_from_db_path(db.path)
    app.debug = True
    app = app.test_client()

    r = app.post('/?t=00000')
    assert r.status_code == 403
    r = app.post('/?t=123123&username=hello')
    assert r.status_code == 403

    chars = list("ab")

    def get_human_readable_id(*args, **kwargs):
        return random.choice(chars)

    monkeypatch.setattr(mailadm.util, "get_human_readable_id", get_human_readable_id)

    r = app.post('/?t=' + token)
    assert r.status_code == 200
    assert r.json["email"].endswith("@x.testrun.org")
    assert r.json["password"]
    email = r.json["email"]
    assert email in ["pytest.a@x.testrun.org", "pytest.b@x.testrun.org"]

    r2 = app.post('/?t=' + token)
    assert r2.status_code == 200
    assert r2.json["email"] != email
    assert r2.json["email"] in ["pytest.a@x.testrun.org", "pytest.b@x.testrun.org"]

    r3 = app.post('/?t=' + token)
    assert r3.status_code == 409

    with db.write_transaction() as conn:
        mailcow = MailcowConnection(conn.config)
        mailcow.del_user_mailcow(email)
        mailcow.del_user_mailcow(r2.json["email"])


def test_env(db, monkeypatch):
    monkeypatch.setenv("MAILADM_DB", str(db.path))
    from mailadm.app import app
    assert app.db.path == db.path


# we used to allow setting the username/password through the web
# but the code has been removed, let's keep the test around
def xxxtest_new_user_usermod(db):
    app = create_app_from_db_path(db.path)
    app.debug = True
    app = app.test_client()

    r = app.post('/?t=00000')
    assert r.status_code == 403

    r = app.post('/?t=123123123123123&username=hello')
    assert r.status_code == 200

    assert r.json["email"] == "hello@x.testrun.org"
    assert len(r.json["password"]) >= 12

    now = time.time()
    r = app.post('/?t=123123123123123&username=hello2&password=l123123123123')
    assert r.status_code == 200
    assert r.json["email"] == "hello2@x.testrun.org"
    assert r.json["password"] == "l123123123123"
    assert int(r.json["expires"]) > (now + 4 * 24 * 60 * 60)
