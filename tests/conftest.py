import collections
import grp
import os
import pwd
import time
from pathlib import Path
from random import randint

import deltachat
import mailadm.bot
import mailadm.db
import pytest
from _pytest.pytester import LineMatcher


@pytest.fixture(autouse=True)
def _nocfg(monkeypatch):
    # tests can still set this env var but we want to isolate tests by default
    monkeypatch.delenv("MAILADM_DB", raising=False)

    def getpwnam(name):
        raise KeyError(name)

    monkeypatch.setattr(pwd, "getpwnam", getpwnam)


class ClickRunner:
    def __init__(self, main):
        from click.testing import CliRunner

        self.runner = CliRunner()
        self._main = main
        self._rootargs = []

    def set_basedir(self, account_dir):
        self._rootargs.insert(0, "--basedir")
        self._rootargs.insert(1, account_dir)

    def run_ok(self, args, fnl=None, input=None):
        __tracebackhide__ = True
        argv = self._rootargs + args
        # we use our nextbackup helper to cache account creation
        # unless --no-test-cache is specified
        res = self.runner.invoke(self._main, argv, catch_exceptions=False, input=input)
        if res.exit_code != 0:
            print(res.output)
            raise Exception("cmd exited with %d: %s" % (res.exit_code, argv))
        return _perform_match(res.output, fnl)

    def run_fail(self, args, fnl=None, input=None, code=None):
        __tracebackhide__ = True
        argv = self._rootargs + args
        res = self.runner.invoke(self._main, argv, catch_exceptions=False, input=input)
        if res.exit_code == 0 or (code is not None and res.exit_code != code):
            print(res.output)
            raise Exception(
                "got exit code {!r}, expected {!r}, output: {}".format(
                    res.exit_code,
                    code,
                    res.output,
                ),
            )
        return _perform_match(res.output, fnl)


def _perform_match(output, fnl):
    __tracebackhide__ = True
    if fnl:
        lm = LineMatcher(output.splitlines())
        lines = [x.strip() for x in fnl.strip().splitlines()]
        try:
            lm.fnmatch_lines(lines)
        except Exception:
            print(output)
            raise
    return output


@pytest.fixture
def cmd():
    """invoke a command line subcommand."""
    from mailadm.cmdline import mailadm_main

    return ClickRunner(mailadm_main)


@pytest.fixture
def db(tmpdir, make_db):
    path = tmpdir.ensure("base", dir=1)
    return make_db(path)


def prepare_account(addr, mailcow, db_path):
    password = mailcow.auth["X-API-Key"]
    mailcow.add_user_mailcow(addr, password, "admbot")
    ac = deltachat.Account(str(db_path))
    ac.run_account(addr, password)
    return ac


@pytest.fixture()
def admingroup(admbot, botadmin, db):
    admchat = admbot.create_group_chat("admins", [], verified=True)
    with db.write_transaction() as conn:
        conn.set_config("admingrpid", admchat.id)
    botplugin = mailadm.bot.AdmBot(db, admbot)
    admbot.add_account_plugin(botplugin)
    qr = admchat.get_join_qr()
    chat = botadmin.qr_join_chat(qr)
    while "added by" not in chat.get_messages()[len(chat.get_messages()) - 1].text:
        print(chat.get_messages()[len(chat.get_messages()) - 1].text)
        time.sleep(1)
    chat.admbot = admbot
    chat.botadmin = botadmin
    chat.botplugin = botplugin
    return chat


@pytest.fixture()
def admbot(mailcow, db, tmpdir, mailcow_domain):
    addr = "pytest-admbot-%s@%s" % (randint(0, 99999), mailcow_domain)
    tmpdir = Path(str(tmpdir))
    admbot_db_path = str(mailadm.bot.get_admbot_db_path(db_path=tmpdir.joinpath("admbot.db")))
    ac = prepare_account(addr, mailcow, admbot_db_path)
    ac._evlogger = ac.add_account_plugin(deltachat.events.FFIEventLogger(ac))
    ac.run_account(show_ffi=True)
    yield ac
    ac.shutdown()
    ac.wait_shutdown()
    mailcow.del_user_mailcow(addr)


@pytest.fixture
def botadmin(mailcow, db, tmpdir, mailcow_domain):
    addr = "pytest-admin-%s@%s" % (randint(0, 99999), mailcow_domain)
    tmpdir = Path(str(tmpdir))
    db_path = mailadm.bot.get_admbot_db_path(tmpdir.joinpath("botadmin.db"))
    ac = prepare_account(addr, mailcow, db_path)
    yield ac
    ac.shutdown()
    ac.wait_shutdown()
    mailcow.del_user_mailcow(addr)


@pytest.fixture
def supportuser(mailcow, db, tmpdir, mailcow_domain):
    addr = "pytest-supportuser-%s@%s" % (randint(0, 99999), mailcow_domain)
    tmpdir = Path(str(tmpdir))
    db_path = mailadm.bot.get_admbot_db_path(tmpdir.joinpath("supportuser.db"))
    ac = prepare_account(addr, mailcow, db_path)
    yield ac
    ac.shutdown()
    ac.wait_shutdown()
    mailcow.del_user_mailcow(addr)


@pytest.fixture
def mailcow_endpoint():
    if not os.environ.get("MAILCOW_ENDPOINT"):
        if os.environ.get("MAILCOW_TOKEN"):
            return "https://dc.develcow.de/api/v1/"
        pytest.skip("Please set the mailcow API URL with the environment variable MAILCOW_ENDPOINT")
    return os.environ.get("MAILCOW_ENDPOINT")


@pytest.fixture
def mailcow_auth():
    if not os.environ.get("MAILCOW_TOKEN"):
        pytest.skip("Please set a mailcow API Key with the environment variable MAILCOW_TOKEN")
    return {"X-API-Key": os.environ.get("MAILCOW_TOKEN")}


@pytest.fixture
def mailcow_domain():
    return os.environ.get("MAIL_DOMAIN", "x.testrun.org")


@pytest.fixture
def mailcow(db):
    with db.read_connection() as conn:
        return conn.get_mailcow_connection()


@pytest.fixture
def make_db(monkeypatch, mailcow_auth, mailcow_endpoint, mailcow_domain):
    def make_db(basedir, init=True):
        basedir = Path(str(basedir))
        db_path = basedir.joinpath("mailadm.db")
        db = mailadm.db.DB(db_path, debug=True)
        if init:
            db.init_config(
                mail_domain=mailcow_domain,
                web_endpoint="https://example.org/new_email",
                mailcow_endpoint=mailcow_endpoint,
                mailcow_token=mailcow_auth.get("X-API-Key"),
            )

        # re-route all queries for sysfiles to the tmpdir
        ttype = collections.namedtuple("pwentry", ["pw_name", "pw_dir", "pw_uid", "pw_gid"])

        def getpwnam(name):
            if name == "vmail":
                p = basedir.joinpath("path_vmaildir")
                if not p.exists():
                    p.mkdir()
            elif name == "mailadm":
                p = basedir
            else:
                raise KeyError("don't know user {!r}".format(name))
            return ttype(name, p, 10000, 10000)  # uid/gid should play no role for testing

        monkeypatch.setattr(pwd, "getpwnam", getpwnam)

        gtype = collections.namedtuple("grpentry", ["gr_name", "gr_mem"])

        def getgrnam(name):
            if name == "vmail":
                gr_mem = ["mailadm"]
            else:
                gr_mem = []
            return gtype(name, gr_mem)

        monkeypatch.setattr(grp, "getgrnam", getgrnam)

        return db

    return make_db
