import time
from mailadm.web import create_app_from_file
import mailadm


def test_new_user_random(config, monkeypatch):
    token = "12319831923123"
    with config.write_transaction() as conn:
        conn.add_token(name="test123", token=token, prefix="tmp.", expiry="1w")

    app = create_app_from_file(config.path)
    app.debug = True
    app = app.test_client()

    r = app.post('/?t=00000')
    assert r.status_code == 403
    r = app.post('/?t=123123&username=hello')
    assert r.status_code == 403

    monkeypatch.setattr(mailadm.db, "TMP_EMAIL_LEN", 1)
    monkeypatch.setattr(mailadm.db, "TMP_EMAIL_CHARS", "ab")

    r = app.post('/?t=' + token)
    assert r.status_code == 200
    assert r.json["email"].endswith("@testrun.org")
    assert r.json["password"]
    email = r.json["email"]
    assert email in ["tmp.a@testrun.org", "tmp.b@testrun.org"]

    r2 = app.post('/?t=' + token)
    assert r2.status_code == 200
    assert r2.json["email"] != email
    assert r2.json["email"] in ["tmp.a@testrun.org", "tmp.b@testrun.org"]

    r3 = app.post('/?t=' + token)
    assert r3.status_code == 409


def test_gensysfiles(config):
    token = "12319831923123"
    with config.write_transaction() as conn:
        conn.add_token(name="test123", token=token, prefix="tmp.", expiry="1w")
    app = create_app_from_file(config.path)
    app.debug = True

    config = app.mailadm_config
    app = app.test_client()

    r = app.post('/?t=' + token)
    assert r.status_code == 200

    email = r.json["email"]
    assert email.endswith("@testrun.org")
    password = r.json["password"]
    assert password

    dovecot_users = open(config.sysconfig.path_dovecot_users).read()
    postfix_map = open(config.sysconfig.path_virtual_mailboxes).read()
    assert email in dovecot_users
    assert email in postfix_map


# we used to allow setting the username/password through the web
# but the code has been removed, let's keep the test around
def xxxtest_new_user_usermod(make_ini_from_values):
    inipath = make_ini_from_values(
        name="test123",
        token="123123123123123",
        prefix="",
        expiry="5w",
    )
    app = create_app_from_file(inipath)
    app.debug = True
    app = app.test_client()

    r = app.post('/?t=00000')
    assert r.status_code == 403

    r = app.post('/?t=123123123123123&username=hello')
    assert r.status_code == 200

    assert r.json["email"] == "hello@testrun.org"
    assert len(r.json["password"]) >= 12

    now = time.time()
    r = app.post('/?t=123123123123123&username=hello2&password=l123123123123')
    assert r.status_code == 200
    assert r.json["email"] == "hello2@testrun.org"
    assert r.json["password"] == "l123123123123"
    assert int(r.json["expires"]) > (now + 4 * 24 * 60 * 60)
