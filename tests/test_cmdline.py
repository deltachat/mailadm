import time
import datetime
import pytest


@pytest.fixture(params=["file", "env"])
def mycmd(request, cmd, make_ini_from_values, tmpdir, monkeypatch):
    p = make_ini_from_values(
        name="oneweek",
        token="1w_Zeeg1RSOK4e3Nh0V",
        prefix="",
        expiry="1w",
    )
    if request.param == "file":
        cmd._rootargs.extend(["--config", p])
    elif request.param == "env":
        monkeypatch.setenv("MAILADM_CONFIG", str(p))
    else:
        assert 0

    return cmd


def test_help(cmd):
    cmd.run_ok([], """
        *account creation*
    """)


def test_tokens(mycmd, make_ini):
    mycmd.run_ok(["list-tokens"], """
        *oneweek*
        *https://testrun.org*
        *DCACCOUNT*
    """)


def test_gen_qr(mycmd, make_ini, tmpdir, monkeypatch):
    mycmd.run_ok(["list-tokens"])
    monkeypatch.chdir(tmpdir)
    mycmd.run_ok(["gen-qr", "oneweek"], """
        *dcaccount-testrun.org-oneweek.png*
    """)
    p = tmpdir.join("dcaccount-testrun.org-oneweek.png")
    assert p.exists()


def test_tokens_usermod(cmd, make_ini_from_values):
    p = make_ini_from_values(
        name="forever",
        token="1w_Zeeg1RSOK4e3Nh0V",
        prefix="",
        expiry="10000d",
    )
    cmd._rootargs.extend(["--config", p])
    cmd.run_ok(["list-tokens"], """
        *DCACCOUNT*&n=forever
    """)


def test_adduser_help(mycmd):
    mycmd.run_ok(["add-user", "-h"], """
        *add*user*
    """)


def test_adduser(mycmd):
    mycmd.run_ok(["add-user", "x@testrun.org"], """
        *added*x@testrun.org*
    """)
    mycmd.run_fail(["add-user", "x@testrun.org"], """
        *failed to add*x@testrun.org*
    """)


def test_adduser_and_expire(mycmd, monkeypatch):
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

    mycmd.run_ok(["prune"])
