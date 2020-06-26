
import pytest


def test_env(config, monkeypatch):
    monkeypatch.setenv("MAILADM_CFG", config.path)
    from mailadm.app import app
    assert app.mailadm_config.cfg.path == config.path
