import base64
import hashlib
import pytest
import json
from tadm.web import create_app, create_app_from_file


@pytest.fixture(params=["static", "env"])
def app(request, tmpdir, monkeypatch):
    config = {"token_create_user": 42,
              "path_virtual_mailboxes": tmpdir.ensure("virtualmailboxes").strpath,
              "path_dovecot_users": tmpdir.ensure("dovecot_users").strpath
    }
    if request.param == "static":
        app = create_app(config)
    elif request.param == "env":
        p = tmpdir.join("app.config")
        p.write(json.dumps(config))
        app = create_app_from_file(p.strpath)
    app.debug = True
    return app.test_client()


def test_newuser_random(app):
    r = app.post('/newtmpuser', json={"token_create_user": 10})
    assert r.status_code == 403
    r = app.post('/newtmpuser', json={"token_create_user": 42})
    assert r.status_code == 200
    assert "tmp_" in r.json["email"]
    assert r.json["password"]

def test_newuser_selected(app):
    username = "test123"
    r = app.post('/newtmpuser', json=dict(token_create_user=42, username=username))
    assert r.status_code == 200
    r = app.post('/newtmpuser', json=dict(token_create_user=42, username=username))
    assert r.status_code == 409
