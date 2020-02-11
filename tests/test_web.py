import pytest
from mailadm.web import create_app_from_file


def test_new_user_random(make_ini_from_values):
    inipath = make_ini_from_values(
        name="test123",
        token="123123",
        prefix="tmp_",
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

    r = app.post('/new_email?t=123123')
    assert r.status_code == 200
    assert "tmp_" in r.json["email"]
    assert r.json["email"].endswith("@testdomain.org")
    assert r.json["password"]


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
    assert r.json["password"]
