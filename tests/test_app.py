
import pytest


def test_no_config(monkeypatch):
    monkeypatch.delenv("MAILADM_CONFIG", raising=False)
    with pytest.raises(RuntimeError):
        import mailadm.app  # noqa


def test_env(config, monkeypatch):
    monkeypatch.setenv("MAILADM_CONFIG", config.path)
    from mailadm.app import app
    assert app.mailadm_config.cfg.path == config.path


def test_sysconfig_path():
    from mailadm.app import MAILADM_SYSCONFIG_PATH  # noqa
