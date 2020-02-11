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
        domain="xyz.abc",
        webdomain="web.domain",
    )
    if request.param == "file":
        cmd._rootargs.extend(["--config", p])
    elif request.param == "env":
        monkeypatch.setenv("MAILADM_CONFIG", p)
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
        *https://web.domain/new_email?t=1w_Zeeg1RSOK4e3Nh0V*
        *DCACCOUNT*
    """)


def test_tokens_usermod(cmd, make_ini_from_values):
    p = make_ini_from_values(
        name="forever",
        token="1w_Zeeg1RSOK4e3Nh0V",
        prefix="",
        expiry="10000d",
        domain="xyz.abc",
        webdomain="web.domain",
    )
    cmd._rootargs.extend(["--config", p])
    cmd.run_ok(["list-tokens"], """
        *DCACCOUNT*usermod&maxdays=10000*
    """)


def test_adduser_help(mycmd):
    mycmd.run_ok(["add-local-user", "-h"], """
        *add*user*
    """)


def test_adduser(mycmd):
    mycmd.run_ok(["add-local-user", "x@xyz.abc"], """
        *added*x@xyz.abc*
    """)
    mycmd.run_fail(["add-local-user", "x@xyz.abc"], """
        *failed to add*x@xyz.abc*
    """)


def test_adduser_and_expire(mycmd, monkeypatch):
    mycmd.run_ok(["add-local-user", "x@xyz.abc"], """
        *added*x@xyz.abc*
    """)

    to_expire = time.time() - datetime.timedelta(weeks=1).total_seconds() - 1

    # create an old account that should expire
    with monkeypatch.context() as m:
        m.setattr(time, "time", lambda: to_expire)
        mycmd.run_ok(["add-local-user", "y@xyz.abc"], """
            *added*y@xyz.abc*
        """)

    mycmd.run_ok(["prune-expired", "-n"])
