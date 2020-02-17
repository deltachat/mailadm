import time
from mailadm.web import create_app_from_file
import mailadm


def test_new_user_random(make_ini_from_values, monkeypatch):
    inipath = make_ini_from_values(
        name="test123",
        token="123123",
        prefix="tmp.",
        expiry="1w",
        domain="testdomain.org",
        webdomain="testdomain.org",
    )
    app = create_app_from_file(inipath)
    app.debug = True
    app = app.test_client()

    r = app.post('/new_email?t=00000')
    assert r.status_code == 403
    r = app.post('/new_email?t=123123&username=hello')
    assert r.status_code == 403

    monkeypatch.setattr(mailadm.config, "TMP_EMAIL_LEN", 1)
    monkeypatch.setattr(mailadm.config, "TMP_EMAIL_CHARS", "ab")

    r = app.post('/new_email?t=123123')
    assert r.status_code == 200
    assert r.json["email"].endswith("@testdomain.org")
    assert r.json["password"]
    email = r.json["email"]
    assert email in ["tmp.a@testdomain.org", "tmp.b@testdomain.org"]

    r2 = app.post('/new_email?t=123123')
    assert r2.status_code == 200
    assert r2.json["email"] != email
    assert r2.json["email"] in ["tmp.a@testdomain.org", "tmp.b@testdomain.org"]

    r3 = app.post('/new_email?t=123123')
    assert r3.status_code == 410


def test_new_user_usermod(make_ini_from_values):
    inipath = make_ini_from_values(
        name="test123",
        token="123123",
        prefix="",
        expiry="5w",
        domain="testdomain.org",
        webdomain="testdomain.org",
    )
    app = create_app_from_file(inipath)
    app.debug = True
    app = app.test_client()

    r = app.post('/new_email?t=00000')
    assert r.status_code == 403

    r = app.post('/new_email?t=123123&username=hello')
    assert r.status_code == 200

    assert r.json["email"] == "hello@testdomain.org"
    assert len(r.json["password"]) >= 12

    now = time.time()
    r = app.post('/new_email?t=123123&username=hello2&password=l123123123123')
    assert r.status_code == 200
    assert r.json["email"] == "hello2@testdomain.org"
    assert r.json["password"] == "l123123123123"
    assert int(r.json["expires"]) > (now + 4 * 24 * 60 * 60)
