import os
import time
import datetime
import pytest


@pytest.fixture
def mycmd(cmd, make_db, tmpdir, monkeypatch):
    db = make_db(tmpdir.mkdir("mycmd"), init=False)
    monkeypatch.setenv("MAILADM_DB", str(db.path))
    cmd.db = db
    if os.environ["MAILCOW_TOKEN"] == "":
        raise KeyError("Please set mailcow API Key with the environment variable MAILCOW_TOKEN")
    cmd.run_ok(["init", "--mailcow-endpoint", "https://dc.develcow.de/api/v1/",
                "--mailcow-token", os.environ["MAILCOW_TOKEN"],
                "--mail-domain", "x.testrun.org",
                "--web-endpoint", "https://example.org/new_email"])
    return cmd


def test_bare(cmd):
    cmd.run_ok([], """
        *account creation*
    """)


class TestInitAndInstall:
    def test_init(self, cmd, monkeypatch, tmpdir):
        monkeypatch.setenv("MAILADM_DB", tmpdir.join("mailadm.db").strpath)
        cmd.run_ok(["init"])


class TestConfig:
    def test_config_simple(self, mycmd):
        mycmd.run_ok(["config"], """
            dbversion*
        """)


class TestQR:
    def test_gen_qr(self, mycmd, tmpdir, monkeypatch):
        mycmd.run_ok(["add-token", "oneweek", "--token=1w_Zeeg1RSOK4e3Nh0V",
                      "--prefix", "", "--expiry=1w"])
        mycmd.run_ok(["list-tokens"], """
            *oneweek*
        """)
        monkeypatch.chdir(tmpdir)
        mycmd.run_ok(["gen-qr", "oneweek"], """
            *dcaccount-x.testrun.org-oneweek.png*
        """)
        p = tmpdir.join("dcaccount-x.testrun.org-oneweek.png")
        assert p.exists()

    def test_gen_qr_no_token(self, mycmd, tmpdir, monkeypatch):
        mycmd.run_fail(["gen-qr", "notexistingtoken"], """
            *Error*not*
        """)


class TestTokens:
    def test_uninitialized(self, cmd):
        cmd.run_fail(["list-tokens"], """
            *MAILADM_DB not set*
        """)

    def test_tokens(self, mycmd):
        mycmd.run_ok(["add-token", "oneweek", "--token=1w_Zeeg1RSOK4e3Nh0V",
                      "--prefix", "", "--expiry=1w"])
        mycmd.run_ok(["list-tokens"], """
            *oneweek*
            *https://example.org*
            *DCACCOUNT*
        """)

    @pytest.mark.parametrize("i", range(3))
    def test_tokens_add(self, mycmd, i):
        mycmd.run_ok(["add-token", "test1", "--expiry=1d", "--prefix=tmpy."], """
            *DCACCOUNT*&n=test1
        """)
        out = mycmd.run_ok(["list-tokens"], """
            *maxuse*50*
            *usecount*
            *DCACCOUNT*&n=test1
        """)
        for line in out.splitlines():
            parts = line.split("=")
            if len(parts) >= 2 and parts[0].strip() == "token":
                token = parts[1].strip().replace("_", "")
                assert token.isalnum()
                break
        else:
            assert 0

        mycmd.run_ok(["del-token", "test1"], """
            *deleted*test1*
        """)
        out = mycmd.run_ok(["list-tokens"])
        assert "test1" not in out

    def test_tokens_add_maxuse(self, mycmd):
        mycmd.run_ok(["add-token", "test1", "--maxuse=10"], """
            *maxuse*10
            *DCACCOUNT*&n=test1
        """)
        mycmd.run_ok(["list-tokens"], """
            *maxuse*10*
            *DCACCOUNT*&n=test1
        """)
        mycmd.run_ok(["mod-token", "--maxuse=1000", "test1"])
        mycmd.run_ok(["list-tokens"], """
            *maxuse*1000*
            *DCACCOUNT*&n=test1
        """)


class TestUsers:
    def test_adduser_help(self, mycmd):
        mycmd.run_ok(["add-user", "-h"], """
            *add*user*
        """)

    def test_add_del_user(self, mycmd):
        mycmd.run_ok(["add-token", "test1", "--expiry=1d", "--prefix", ""])
        mycmd.run_ok(["add-user", "x@x.testrun.org"], """
            *added*x@x.testrun.org*
        """)
        mycmd.run_ok(["list-users"], """
            *x@x.testrun.org*test1*
        """)
        mycmd.run_fail(["add-user", "x@x.testrun.org"], """
            *failed to add*x@x.testrun.org*
        """)
        mycmd.run_ok(["del-user", "x@x.testrun.org"], """
            *deleted*x@x.testrun.org*
        """)

    def test_adduser_and_expire(self, mycmd, monkeypatch):
        mycmd.run_ok(["add-token", "test1", "--expiry=1d", "--prefix", ""])
        mycmd.run_ok(["add-user", "x@x.testrun.org"], """
            *added*x@x.testrun.org*
        """)

        to_expire = time.time() - datetime.timedelta(weeks=1).total_seconds() - 1

        # create an old account that should expire
        with monkeypatch.context() as m:
            m.setattr(time, "time", lambda: to_expire)
            mycmd.run_ok(["add-user", "y@x.testrun.org"], """
                *added*y@x.testrun.org*
            """)

        out = mycmd.run_ok(["list-users"])
        assert "y@x.testrun.org" in out

        mycmd.run_ok(["prune"])

        out = mycmd.run_ok(["list-users"])
        assert "x@x.testrun.org" in out
        assert "y@x.testrun.org" not in out

        mycmd.run_ok(["del-user", "x@x.testrun.org"])

    def test_two_tokens_users(self, mycmd):
        mycmd.run_ok(["add-token", "test1", "--expiry=1d", "--prefix=tmpy."])
        mycmd.run_ok(["add-token", "test2", "--expiry=1d", "--prefix=tmpx."])
        mycmd.run_fail(["add-user", "x@x.testrun.org"])
        mycmd.run_ok(["add-user", "tmpy.123@x.testrun.org"])
        mycmd.run_ok(["add-user", "tmpx.456@x.testrun.org"])
        mycmd.run_ok(["list-users"], """
            tmpy.123*test1*
            tmpx.456*test2*
        """)
        out = mycmd.run_ok(["list-users", "--token", "test1"])
        assert "tmpy.123" in out
        assert "tmpx.456" not in out
        out = mycmd.run_ok(["list-users", "--token", "test2"])
        assert "tmpy.123" not in out
        assert "tmpx.456" in out
        mycmd.run_ok(["del-user", "tmpy.123@x.testrun.org"])
        mycmd.run_ok(["del-user", "tmpx.456@x.testrun.org"])
