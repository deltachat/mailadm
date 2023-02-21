import datetime
import os
import time
from random import randint

import pytest
from mailadm.mailcow import MailcowError


@pytest.fixture
def mycmd(cmd, make_db, tmpdir, monkeypatch, mailcow_domain, mailcow_endpoint):
    db = make_db(tmpdir.mkdir("mycmd"), init=False)
    monkeypatch.setenv("MAILADM_DB", str(db.path))
    monkeypatch.setenv("ADMBOT_DB", str(tmpdir.mkdir("admbot")) + "admbot.db")
    cmd.db = db
    if os.environ["MAILCOW_TOKEN"] == "":
        raise KeyError("Please set mailcow API Key with the environment variable MAILCOW_TOKEN")
    cmd.run_ok(
        [
            "init",
            "--mailcow-endpoint",
            mailcow_endpoint,
            "--mail-domain",
            mailcow_domain,
            "--web-endpoint",
            "https://example.org/new_email",
        ],
    )
    return cmd


def test_bare(cmd):
    cmd.run_ok(
        [],
        """
        *account creation*
    """,
    )


class TestInitAndInstall:
    def test_init(self, cmd, monkeypatch, tmpdir):
        monkeypatch.setenv("MAILADM_DB", tmpdir.join("mailadm.db").strpath)
        cmd.run_ok(
            [
                "init",
                "--mailcow-endpoint",
                "unfortunately-required",
                "--mailcow-token",
                "unfortunately-required",
            ],
        )


class TestConfig:
    def test_config_simple(self, mycmd):
        mycmd.run_ok(
            ["config"],
            """
            dbversion*
        """,
        )


class TestQR:
    def test_gen_qr(self, mycmd, tmpdir, monkeypatch, mailcow_domain):
        mycmd.run_ok(
            ["add-token", "oneweek", "--token=1w_Zeeg1RSOK4e3Nh0V", "--prefix", "", "--expiry=1w"],
        )
        mycmd.run_ok(
            ["list-tokens"],
            """
            *oneweek*
        """,
        )
        monkeypatch.chdir(tmpdir)
        os.system("mkdir docker-data")
        mycmd.run_ok(
            ["gen-qr", "oneweek"],
            """
            *dcaccount-*-oneweek.png*
        """,
        )
        p = tmpdir.join("docker-data/dcaccount-%s-oneweek.png" % (mailcow_domain,))
        assert p.exists()

    def test_gen_qr_no_token(self, mycmd):
        mycmd.run_fail(
            ["gen-qr", "notexistingtoken"],
            """
            *Error*not*
        """,
        )


class TestTokens:
    def test_uninitialized(self, cmd):
        cmd.run_fail(
            ["list-tokens"],
            """
            *MAILADM_DB not set*
        """,
        )

    def test_tokens(self, mycmd):
        mycmd.run_ok(
            ["add-token", "oneweek", "--token=1w_Zeeg1RSOK4e3Nh0V", "--prefix", "", "--expiry=1w"],
        )
        mycmd.run_ok(
            ["list-tokens"],
            """
            *oneweek*
            *https://example.org*
            *DCACCOUNT*
        """,
        )

    @pytest.mark.parametrize("i", range(3))
    def test_tokens_add(self, mycmd, i):
        mycmd.run_ok(
            ["add-token", "test1", "--expiry=1d", "--prefix=tmpy."],
            """
            *DCACCOUNT*&n=test1
        """,
        )
        out = mycmd.run_ok(
            ["list-tokens"],
            """
            *of 50 times*
            *DCACCOUNT*&n=test1
        """,
        )
        for line in out.splitlines():
            parts = line.split(":")
            if len(parts) >= 2 and parts[0].strip() == "token":
                token = parts[1].strip().replace("_", "")
                assert token.isalnum()
                break
        else:
            pytest.fail()

        mycmd.run_ok(
            ["del-token", "test1"],
            """
            *deleted*test1*
        """,
        )
        out = mycmd.run_ok(["list-tokens"])
        assert "test1" not in out

    def test_tokens_add_maxuse(self, mycmd):
        mycmd.run_ok(
            ["add-token", "test1", "--maxuse=10"],
            """
            *of 10 times*
            *DCACCOUNT*&n=test1
        """,
        )
        mycmd.run_ok(
            ["list-tokens"],
            """
            *of 10 times*
            *DCACCOUNT*&n=test1
        """,
        )
        mycmd.run_ok(["mod-token", "--maxuse=1000", "test1"])
        mycmd.run_ok(
            ["list-tokens"],
            """
            *of 1000 times*
            *DCACCOUNT*&n=test1
        """,
        )


class TestUsers:
    def test_adduser_help(self, mycmd):
        mycmd.run_ok(
            ["add-user", "-h"],
            """
            *add*user*
        """,
        )

    def test_add_del_user(self, mycmd, mailcow_domain):
        mycmd.run_ok(["add-token", "test1", "--expiry=1d", "--prefix", "pytest."])
        addr = "pytest.%s@%s" % (randint(0, 99999), mailcow_domain)
        mycmd.run_ok(
            ["add-user", addr],
            """
            *Created*pytest*@*
        """,
        )
        mycmd.run_ok(
            ["list-users"],
            """
            *{addr}*
        """.format(
                addr=addr,
            ),
        )
        mycmd.run_fail(
            ["add-user", addr],
            """
            *failed to add*pytest* account does already exist*
        """,
        )
        mycmd.run_ok(
            ["del-user", addr],
            """
            *deleted*pytest*@*
        """,
        )
        mycmd.run_ok(
            ["add-user", addr, "--dryrun"],
            """
            *Would create pytest*@*
        """,
        )
        mycmd.run_fail(
            ["del-user", addr],
            """
            *failed to delete*pytest*@*does not exist*
        """,
        )

    def test_adduser_and_expire(self, mycmd, monkeypatch, mailcow_domain):
        mycmd.run_ok(["add-token", "test1", "--expiry=1d", "--prefix", "pytest."])
        addr = "pytest.%s@%s" % (randint(0, 49999), mailcow_domain)
        mycmd.run_ok(
            ["add-user", addr],
            """
            *Created*pytest*@*
        """,
        )

        to_expire = time.time() - datetime.timedelta(weeks=1).total_seconds() - 1

        # create an old account that should expire
        with monkeypatch.context() as m:
            m.setattr(time, "time", lambda: to_expire)
            addr2 = "pytest.%s@%s" % (randint(50000, 99999), mailcow_domain)
            mycmd.run_ok(
                ["add-user", addr2],
                """
                *Created*pytest*@*
            """,
            )

        out = mycmd.run_ok(["list-users"])
        assert addr2 in out

        mycmd.run_ok(["prune"])

        out = mycmd.run_ok(["list-users"])
        assert addr in out
        assert addr2 not in out

        mycmd.run_ok(["del-user", addr])

    def test_two_tokens_users(self, mycmd, mailcow_domain):
        mycmd.run_ok(["add-token", "test1", "--expiry=1d", "--prefix=tmpy."])
        mycmd.run_ok(["add-token", "test2", "--expiry=1d", "--prefix=tmpx."])
        mycmd.run_fail(["add-user", "x@" + mailcow_domain])
        addr = "tmpy.%s@%s" % (randint(0, 49999), mailcow_domain)
        addr2 = "tmpx.%s@%s" % (randint(50000, 99999), mailcow_domain)
        mycmd.run_ok(["add-user", addr])
        mycmd.run_ok(["add-user", addr2])
        mycmd.run_ok(
            ["list-users"],
            """
            tmpy.*test1*
            tmpx.*test2*
        """,
        )
        out = mycmd.run_ok(["list-users", "--token", "test1"])
        assert addr in out
        assert addr2 not in out
        out = mycmd.run_ok(["list-users", "--token", "test2"])
        assert addr not in out
        assert addr2 in out
        mycmd.run_ok(["del-user", addr])
        mycmd.run_ok(["del-user", addr2])


class TestSetupBot:
    def test_account_already_exists(self, mycmd, mailcow, mailcow_domain):
        print(os.environ.items())
        delete_later = True
        try:
            mailcow.add_user_mailcow("mailadm@" + mailcow_domain, "asdf1234", "pytest")
        except MailcowError as e:
            if "object_exists" in str(e):
                delete_later = False
        mycmd.run_fail(
            ["setup-bot"],
            """
            *mailadm@* already exists; delete the account in mailcow or specify*
        """,
        )
        if delete_later:
            mailcow.del_user_mailcow("mailadm@" + mailcow_domain)

    def test_specify_addr_not_password(self, mycmd):
        mycmd.run_fail(
            ["setup-bot", "--email", "bot@example.org"],
            """
            *You need to provide --password if you want to use an existing account*
        """,
        )

    def test_specify_password_not_addr(self, mycmd):
        mycmd.run_fail(
            ["setup-bot", "--password", "asdf"],
            """
            *Please also provide --email to use an email account for the mailadm*
        """,
        )

    def test_wrong_credentials(self, mycmd):
        mycmd.run_fail(
            ["setup-bot", "--email", "bot@testrun.org", "--password", "asdf"],
            """
            *Cannot login as "bot@testrun.org". Please check if the email address and the password*
        """,
        )
