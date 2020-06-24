import os
import time
import datetime
import pytest


@pytest.fixture(params=["file", "env"])
def mycmd(request, cmd, config, tmpdir, monkeypatch):
    if request.param == "file":
        cmd._rootargs.extend(["--config", str(config.path)])
    elif request.param == "env":
        monkeypatch.setenv("MAILADM_CFG", str(config.path))
    else:
        assert 0

    cmd._config = config
    return cmd


def test_help(cmd):
    cmd.run_ok([], """
        *account creation*
    """)
    cmd.run_fail(["list-tokens"], """
        Error*not*found*
    """)


def test_gen_sysconfig(mycmd, tmpdir):
    with tmpdir.as_cwd():
        out = mycmd.run_ok(["gen-sysconfig"], "")
        print(out)

    names = os.listdir(tmpdir.join("sysconfig").strpath)
    assert len(names) == 7


def test_gen_sysconfig_no_vmail(mycmd, tmpdir):
    with tmpdir.as_cwd():
        mycmd.run_fail(["gen-sysconfig", "--vmail-user", "l1kj23l"])


def test_gen_sysconfig_no_mailadm(mycmd, tmpdir):
    with tmpdir.as_cwd():
        mycmd.run_fail(["gen-sysconfig", "--mailadm-user", "l1kj23l"])


class TestQR:
    def test_gen_qr(self, mycmd, tmpdir, monkeypatch):
        mycmd.run_ok(["add-token", "oneweek", "--token=1w_Zeeg1RSOK4e3Nh0V",
                      "--prefix", "", "--expiry=1w"])
        mycmd.run_ok(["list-tokens"], """
            *oneweek*
        """)
        monkeypatch.chdir(tmpdir)
        mycmd.run_ok(["gen-qr", "oneweek"], """
            *dcaccount-testrun.org-oneweek.png*
        """)
        p = tmpdir.join("dcaccount-testrun.org-oneweek.png")
        assert p.exists()

    def test_gen_qr_no_token(self, mycmd, tmpdir, monkeypatch):
        mycmd.run_fail(["gen-qr", "notexistingtoken"], """
            *Error*not*
        """)


class TestTokens:
    def test_tokens(self, mycmd):
        mycmd.run_ok(["add-token", "oneweek", "--token=1w_Zeeg1RSOK4e3Nh0V",
                      "--prefix", "", "--expiry=1w"])
        mycmd.run_ok(["list-tokens"], """
            *oneweek*
            *https://testrun.org*
            *DCACCOUNT*
        """)

    def test_tokens_add(self, mycmd):
        mycmd.run_ok(["add-token", "test1", "--expiry=1d", "--prefix=tmpy."], """
            *DCACCOUNT*&n=test1
        """)
        mycmd.run_ok(["list-tokens"], """
            *maxuse*50*
            *usecount*
            *DCACCOUNT*&n=test1
        """)
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


class TestUsers:
    def test_adduser_help(self, mycmd):
        mycmd.run_ok(["add-user", "-h"], """
            *add*user*
        """)

    def test_add_user_sysfiles(self, mycmd):
        mycmd.run_ok(["add-token", "test1", "--expiry=1d", "--prefix", ""])
        mycmd.run_ok(["add-user", "x@testrun.org"], """
            *added*x@testrun.org*
        """)
        path = mycmd._config.sysconfig.path_virtual_mailboxes
        assert "x@testrun.org" in open(path).read()

    def test_add_del_user(self, mycmd):
        mycmd.run_ok(["add-token", "test1", "--expiry=1d", "--prefix", ""])
        mycmd.run_ok(["add-user", "x@testrun.org"], """
            *added*x@testrun.org*
        """)
        mycmd.run_ok(["list-users"], """
            *x@testrun.org*test1*
        """)
        mycmd.run_fail(["add-user", "x@testrun.org"], """
            *failed to add*x@testrun.org*
        """)
        mycmd.run_ok(["del-user", "x@testrun.org"], """
            *deleted*x@testrun.org*
        """)

    def test_adduser_and_expire(self, mycmd, monkeypatch):
        mycmd.run_ok(["add-token", "test1", "--expiry=1d", "--prefix", ""])
        mycmd.run_ok(["add-user", "x@testrun.org"], """
            *added*x@testrun.org*
        """)

        to_expire = time.time() - datetime.timedelta(weeks=1).total_seconds() - 1

        # create an old account that should expire
        with monkeypatch.context() as m:
            m.setattr(time, "time", lambda: to_expire)
            mycmd.run_ok(["add-user", "y@testrun.org"], """
                *added*y@testrun.org*
            """)

        out = mycmd.run_ok(["list-users"])
        assert "y@testrun.org" in out

        mycmd.run_ok(["prune"])

        out = mycmd.run_ok(["list-users"])
        assert "x@testrun.org" in out
        assert "y@testrun.org" not in out

    def test_two_tokens_users(self, mycmd):
        mycmd.run_ok(["add-token", "test1", "--expiry=1d", "--prefix=tmpy."])
        mycmd.run_ok(["add-token", "test2", "--expiry=1d", "--prefix=tmpx."])
        mycmd.run_fail(["add-user", "x@testrun.org"])
        mycmd.run_ok(["add-user", "tmpy.123@testrun.org"])
        mycmd.run_ok(["add-user", "tmpx.456@testrun.org"])
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
