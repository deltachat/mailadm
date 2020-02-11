
import pytest


@pytest.fixture
def inipath(tmpdir, make_ini_from_values):
    return make_ini_from_values(
        name="test123",
        token="123123",
        prefix="tmp_",
        expiry="1w",
        domain="testdomain.org",
        webdomain="testdomain.org",
        path_virtual_mailboxes=tmpdir.ensure("virtualmailboxes").strpath,
        path_dovecot_users=tmpdir.ensure("dovecot_users").strpath,
        path_vmaildir=tmpdir.ensure("vmaildir", dir=1).strpath,
    )


def test_no_config(monkeypatch):
    monkeypatch.delenv("MAILADM_CONFIG", raising=False)
    with pytest.raises(RuntimeError):
        import mailadm.app  # noqa


def test_env(inipath, monkeypatch):
    monkeypatch.setenv("MAILADM_CONFIG", inipath)
    from mailadm.app import app
    assert app.mailadm_config.cfg.path == inipath


def test_sysconfig_path():
    from mailadm.app import MAILADM_SYSCONFIG_PATH  # noqa
