import os
from random import randint
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
        cmd.run_ok(["init", "--mailcow-endpoint", "unfortunately-required",
                    "--mailcow-token", "unfortunately-required"])


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
            *of 50 times*
            *DCACCOUNT*&n=test1
        """)
        for line in out.splitlines():
            parts = line.split(":")
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
            *of 10 times*
            *DCACCOUNT*&n=test1
        """)
        mycmd.run_ok(["list-tokens"], """
            *of 10 times*
            *DCACCOUNT*&n=test1
        """)
        mycmd.run_ok(["mod-token", "--maxuse=1000", "test1"])
        mycmd.run_ok(["list-tokens"], """
            *of 1000 times*
            *DCACCOUNT*&n=test1
        """)


class TestUsers:
    def test_adduser_help(self, mycmd):
        mycmd.run_ok(["add-user", "-h"], """
            *add*user*
        """)

    def test_add_del_user(self, mycmd):
        mycmd.run_ok(["add-token", "test1", "--expiry=1d", "--prefix", "pytest."])
        addr = "pytest.%s@x.testrun.org" % (randint(0, 999),)
        mycmd.run_ok(["add-user", addr], """
            *added*pytest*@x.testrun.org*
        """)
        mycmd.run_ok(["list-users"], """
            *pytest*@x.testrun.org*test1*
        """)
        mycmd.run_fail(["add-user", addr], """
            *failed to add*pytest* account does already exist*
        """)
        mycmd.run_ok(["del-user", addr], """
            *deleted*pytest*@x.testrun.org*
        """)

    def test_adduser_and_expire(self, mycmd, monkeypatch):
        mycmd.run_ok(["add-token", "test1", "--expiry=1d", "--prefix", "pytest."])
        addr = "pytest.%s@x.testrun.org" % (randint(0, 499),)
        mycmd.run_ok(["add-user", addr], """
            *added*pytest*@x.testrun.org*
        """)

        to_expire = time.time() - datetime.timedelta(weeks=1).total_seconds() - 1

        # create an old account that should expire
        with monkeypatch.context() as m:
            m.setattr(time, "time", lambda: to_expire)
            addr2 = "pytest.%s@x.testrun.org" % (randint(500, 999),)
            mycmd.run_ok(["add-user", addr2], """
                *added*pytest*@x.testrun.org*
            """)

        out = mycmd.run_ok(["list-users"])
        assert addr2 in out

        mycmd.run_ok(["prune"])

        out = mycmd.run_ok(["list-users"])
        assert addr in out
        assert addr2 not in out

        mycmd.run_ok(["del-user", addr])

    def test_two_tokens_users(self, mycmd):
        mycmd.run_ok(["add-token", "test1", "--expiry=1d", "--prefix=tmpy."])
        mycmd.run_ok(["add-token", "test2", "--expiry=1d", "--prefix=tmpx."])
        mycmd.run_fail(["add-user", "x@x.testrun.org"])
        addr = "tmpy.%s@x.testrun.org" % (randint(0, 499),)
        addr2 = "tmpx.%s@x.testrun.org" % (randint(500, 999),)
        mycmd.run_ok(["add-user", addr])
        mycmd.run_ok(["add-user", addr2])
        mycmd.run_ok(["list-users"], """
            tmpy.*test1*
            tmpx.*test2*
        """)
        out = mycmd.run_ok(["list-users", "--token", "test1"])
        assert addr in out
        assert addr2 not in out
        out = mycmd.run_ok(["list-users", "--token", "test2"])
        assert addr not in out
        assert addr2 in out
        mycmd.run_ok(["del-user", addr])
        mycmd.run_ok(["del-user", addr2])
