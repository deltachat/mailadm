import pytest


@pytest.fixture(params=["file", "env"])
def mycmd(request, cmd, make_ini_from_values, tmpdir, monkeypatch):
    path = tmpdir.join("paths")
    p = make_ini_from_values(
        name = "burner1",
        token = "1w_Zeeg1RSOK4e3Nh0V",
        domain = "xyz.abc",
        webdomain = "web.domain",
        path_dovecot_users = path.ensure("path_dovecot_users"),
        path_virtual_mailboxes = path.ensure("path_virtual_mailboxes"),
        path_vmaildir = path.ensure("path_vmaildir", dir=1),
    )
    if request.param == "file":
        cmd._rootargs.extend(["--config", p])
    elif request.param == "env":
        monkeypatch.setenv("TADM_CONFIG", p)
    else:
        assert 0

    return cmd


def test_help(cmd):
    cmd.run_ok([], """
        *testrun management*
    """)

def test_tokens(mycmd, make_ini):
    mycmd.run_ok(["tokens"], """
        *burner1*
        *https://web.domain/new_email?t=1w_Zeeg1RSOK4e3Nh0V*
    """)

def test_adduser(mycmd):
    mycmd.run_ok(["add", "-h"], """
        *add*e-mail*user*
    """)
