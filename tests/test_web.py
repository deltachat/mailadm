import base64
import hashlib
import pytest
import json
from tadm.web import create_app_from_file


@pytest.fixture(params=["static", "env"])
def app(request, tmpdir, monkeypatch, make_ini_from_values):
    inipath = make_ini_from_values(
                name = "test123",
                token = "123123",
                prefix = "tmp_",
                domain = "testdomain.org",
                webdomain = "testdomain.org",
                path_virtual_mailboxes=tmpdir.ensure("virtualmailboxes").strpath,
                path_dovecot_users=tmpdir.ensure("dovecot_users").strpath,
                path_vmaildir=tmpdir.ensure("vmaildir", dir=1).strpath,
    )
    app = create_app_from_file(inipath)
    app.debug = True
    return app.test_client()


def test_newuser_random(app):
    r = app.post('/new_email?t=00000')
    assert r.status_code == 403
    r = app.post('/new_email?t=123123')
    assert r.status_code == 200
    assert "tmp_" in r.json["email"]
    assert r.json["password"]
