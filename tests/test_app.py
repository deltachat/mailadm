
import pytest


def test_no_config():
    with pytest.raises(RuntimeError):
        import mailadm.app  # noqa


def test_env(config, monkeypatch):
    monkeypatch.setenv("MAILADM_CFG", config.path)
    from mailadm.app import app
    assert app.mailadm_config.cfg.path == config.path
