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

def test_remove_user(mailuser_maker, capfd):
    mu = mailuser_maker(domain="xyz.com")

    email = "tmp_{}@xyz.com".format(random.randint(0, 1023123123123))
    mu.add_email_account(email, password="123")
    cap = capfd.readouterr()
    print(cap.out)
    assert cap.out.strip().endswith("123")
    assert os.path.exists(mu.path_virtual_mailboxes + ".db")

    email2 = "tmp_{}@xyz.com".format(random.randint(0, 1023123123123))
    mu.add_email_account(email2, password="456")
    cap = capfd.readouterr()
    print(cap.out)
    assert cap.out.strip().endswith("456")

    email3 = "somebody@xyz.com"
    mu.add_email_account(email3, password="789")
    cap = capfd.readouterr()
    print(cap.out)
    assert cap.out.strip().endswith("789")

    accounts = mu.find_email_accounts(prefix="tmp_")
    assert len(accounts) == 2
    assert accounts[0].startswith("tmp_")
    assert accounts[1].startswith("tmp_")

    mu.remove_accounts(accounts)
    assert not mu.find_email_accounts(prefix="tmp_")
    accounts = mu.find_email_accounts()
    assert len(accounts) == 1
    assert accounts[0].startswith("somebody@xyz.com")

