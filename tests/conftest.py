
import pwd
import grp
import collections
from pathlib import Path

import pytest
from _pytest.pytester import LineMatcher

import mailadm.db


@pytest.fixture(autouse=True)
def _nocfg(monkeypatch, tmpdir):
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
        res = self.runner.invoke(self._main, argv, catch_exceptions=False,
                                 input=input)
        if res.exit_code != 0:
            print(res.output)
            raise Exception("cmd exited with %d: %s" % (res.exit_code, argv))
        return _perform_match(res.output, fnl)

    def run_fail(self, args, fnl=None, input=None, code=None):
        __tracebackhide__ = True
        argv = self._rootargs + args
        res = self.runner.invoke(self._main, argv, catch_exceptions=False,
                                 input=input)
        if res.exit_code == 0 or (code is not None and res.exit_code != code):
            print(res.output)
            raise Exception("got exit code {!r}, expected {!r}, output: {}".format(
                res.exit_code, code, res.output))
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
    """ invoke a command line subcommand. """
    from mailadm.cmdline import mailadm_main

    return ClickRunner(mailadm_main)


@pytest.fixture
def db(tmpdir, make_db):
    path = tmpdir.ensure("base", dir=1)
    return make_db(path)


@pytest.fixture
def make_db(monkeypatch):
    def make_db(basedir, init=True):
        basedir = Path(str(basedir))
        db_path = basedir.joinpath("mailadm.db")
        db = mailadm.db.DB(db_path)
        if init:
            db.init_config(
                mail_domain="example.org",
                web_endpoint="https://example.org/new_email",
                vmail_user="vmail",
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
