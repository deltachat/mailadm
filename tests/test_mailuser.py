import pytest
import random
import sys
import os
from tadm.mailuser import MailUser


@pytest.fixture
def mailuser_maker(tmpdir):
    path_virtual_mailboxes = tmpdir.ensure("postfix_virtual_mailboxes").strpath
    path_dovecot_users = tmpdir.ensure("dovecot_users").strpath


    def make_mailuser(domain="testrun.org", dryrun=False):
        mu = MailUser(domain=domain, dryrun=dryrun,
                      path_virtual_mailboxes=path_virtual_mailboxes,
                      path_dovecot_users=path_dovecot_users)
        return mu
    return make_mailuser


def test_add_user_dry(mailuser_maker, capfd):
    mu = mailuser_maker(domain="xyz.com")
    with pytest.raises(ValueError):
        email = "tmp_{}@testrun.org".format(random.randint(0, 1023123123123))
        mu.add_email_account(email)
    capfd.readouterr()

    email = "tmp_{}@xyz.com".format(random.randint(0, 1023123123123))
    mu.add_email_account(email, password="123")
    cap = capfd.readouterr()
    print(cap.out)
    assert cap.out.strip().endswith("123")
    assert os.path.exists(mu.path_virtual_mailboxes + ".db")
