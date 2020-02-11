
import pytest
from _pytest.pytester import LineMatcher
from textwrap import dedent
import mailadm


@pytest.fixture(autouse=True)
def _change_sys_config(monkeypatch):
    monkeypatch.setattr(mailadm, "MAILADM_SYSCONFIG_PATH", "/tmp/not/existent/i/hope")


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
def make_ini(tmpdir):
    made = []

    def make(source):
        p = tmpdir.join("mailadm-{}.ini".format(len(made)))
        p.write(dedent(source))
        made.append(p)
        return p.strpath
    return make


@pytest.fixture
def make_ini_from_values(make_ini, tmpdir):
    def make_ini_from_values(
        name="oneweek",
        token="1w_Zeeg1RSOK4e3Nh0V",
        prefix="",
        expiry="1w",
        domain="xyz.abc",
        webdomain="web.domain",
        path_dovecot_users=None,
        path_virtual_mailboxes=None,
        path_vmaildir=None,
    ):
        path = tmpdir.mkdir(name)
        if path_dovecot_users is None:
            path_dovecot_users = path.ensure("path_dovecot_users")
        if path_virtual_mailboxes is None:
            path_virtual_mailboxes = path.ensure("path_virtual_mailboxes")
        if path_vmaildir is None:
            path_vmaildir = path.ensure("path_vmaildir", dir=1)

        return make_ini("""
            [token:{name}]
            token = {token}
            expiry = {expiry}
            path_virtual_mailboxes = {path_virtual_mailboxes}
            path_dovecot_users = {path_dovecot_users}
            path_vmaildir = {path_vmaildir}
            webdomain = {webdomain}
            domain = {domain}
            prefix = {prefix}
        """.format(**locals()))
    return make_ini_from_values
