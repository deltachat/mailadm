import time
from mailadm.web import create_app_from_file
import mailadm


def test_new_user_random(make_ini_from_values, monkeypatch):
    inipath = make_ini_from_values(
        name="test123",
        token="123123",
        prefix="tmp.",
        expiry="1w",
        mail_domain="example.org",
    )
    app = create_app_from_file(inipath)
    app.debug = True
    app = app.test_client()

    r = app.post('/?t=00000')
    assert r.status_code == 403
    r = app.post('/?t=123123&username=hello')
    assert r.status_code == 403

    monkeypatch.setattr(mailadm.config, "TMP_EMAIL_LEN", 1)
    monkeypatch.setattr(mailadm.config, "TMP_EMAIL_CHARS", "ab")

    r = app.post('/?t=123123')
    assert r.status_code == 200
    assert r.json["email"].endswith("@example.org")
    assert r.json["password"]
    email = r.json["email"]
    assert email in ["tmp.a@example.org", "tmp.b@example.org"]

    r2 = app.post('/?t=123123')
    assert r2.status_code == 200
    assert r2.json["email"] != email
    assert r2.json["email"] in ["tmp.a@example.org", "tmp.b@example.org"]

    r3 = app.post('/?t=123123')
    assert r3.status_code == 410


def test_new_user_usermod(make_ini_from_values):
    inipath = make_ini_from_values(
        name="test123",
        token="123123",
        prefix="",
        expiry="5w",
        mail_domain="example.org",
    )
    app = create_app_from_file(inipath)
    app.debug = True
    app = app.test_client()

    r = app.post('/?t=00000')
    assert r.status_code == 403

    r = app.post('/?t=123123&username=hello')
    assert r.status_code == 200

    assert r.json["email"] == "hello@example.org"
    assert len(r.json["password"]) >= 12

    now = time.time()
    r = app.post('/?t=123123&username=hello2&password=l123123123123')
    assert r.status_code == 200
    assert r.json["email"] == "hello2@example.org"
    assert r.json["password"] == "l123123123123"
    assert int(r.json["expires"]) > (now + 4 * 24 * 60 * 60)
