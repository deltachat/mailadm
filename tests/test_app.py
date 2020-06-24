
import os
import pytest


def test_no_config(monkeypatch):
    monkeypatch.delenv("MAILADM_CFG", raising=False)

    def exists(path, _exists=os.path.exists):
        if "mailadm.cfg" in path:
            return False
        return _exists(path)

    monkeypatch.setattr(os.path, "exists", exists)
    with pytest.raises(RuntimeError):
        import mailadm.app  # noqa


def test_env(config, monkeypatch):
    monkeypatch.setenv("MAILADM_CFG", config.path)
    from mailadm.app import app
    assert app.mailadm_config.cfg.path == config.path
