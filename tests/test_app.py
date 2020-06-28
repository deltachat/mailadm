
def test_env(db, monkeypatch):
    monkeypatch.setenv("MAILADM_DB", str(db.path))
    from mailadm.app import app
    assert app.db.path == db.path
