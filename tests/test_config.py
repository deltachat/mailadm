import textwrap
import pytest

from tadm.config import Config

def test_simple(make_ini):
    inipath = make_ini("""
        [token:burner1]
        domain = testrun.org
        prefix = tmp_
        path_dovecot_users= /etc/dovecot/users
        path_virtual_mailboxes= /etc/postfix/virtual_mailboxes
        path_vmaildir = /home/vmail/testrun.org
        token = 1w_7wDioPeeXyZx96v3
    """)
    config = Config(inipath)
    mc = config.get_mail_config("1w_7wDioPeeXyZx96v3")
    assert mc.domain == "testrun.org"
    assert mc.prefix == "tmp_"
    assert mc.path_dovecot_users == "/etc/dovecot/users"
    assert mc.path_virtual_mailboxes == "/etc/postfix/virtual_mailboxes"
    assert mc.path_vmaildir == "/home/vmail/testrun.org"
