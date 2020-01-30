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
    assert config.get_mail_config_from_token("1qwljkewe") is None
    mc = config.get_mail_config_from_token("1w_7wDioPeeXyZx96v3")
    assert mc.domain == "testrun.org"
    assert mc.prefix == "tmp_"
    assert mc.path_dovecot_users == "/etc/dovecot/users"
    assert mc.path_virtual_mailboxes == "/etc/postfix/virtual_mailboxes"
    assert mc.path_vmaildir == "/home/vmail/testrun.org"


def test_email_check(make_ini):
    inipath = make_ini("""
        [token:burner1]
        domain = testrun.org
        prefix = tmp_
        path_dovecot_users= /etc/dovecot/users
        path_virtual_mailboxes= /etc/postfix/virtual_mailboxes
        path_vmaildir = /home/vmail/testrun.org
        token = 1w_7wDioPeeXyZx96v3

        [token:burner2]
        domain = testrun.org
        prefix =
        path_dovecot_users= /etc/dovecot/users
        path_virtual_mailboxes= /etc/postfix/virtual_mailboxes
        path_vmaildir = /home/vmail/testrun.org
        token = 1w_7wDioPeeXyZx96v3
    """)
    config = Config(inipath)
    assert config.get_mail_config_from_email("xyz@testrun.o123") is None
    mc = config.get_mail_config_from_email("xyz@testrun.org")
    assert mc.name == "burner2"

    mc = config.get_mail_config_from_email("tmp_xyz@testrun.org")
    assert mc.name == "burner1"
