import pytest
import random
import sys
import time
import os
from tadm.mail import MailController
from tadm.config import Config


@pytest.fixture
def mail_controller_maker(make_ini_from_values):
    def make_mail_controller(name="test", domain="testrun.org", expiry="never", dryrun=False):
        inipath = make_ini_from_values(name=name, expiry=expiry, domain=domain)
        config = Config(inipath)
        mail_config = config.get_mail_config_from_name(name)
        return mail_config.make_controller()

    return make_mail_controller


def test_add_user(mail_controller_maker, capfd):
    mu = mail_controller_maker(domain="xyz.com")
    with pytest.raises(ValueError):
        email = "tmp_{}@testrun.org".format(random.randint(0, 1023123123123))
        mu.add_email_account(email)
    capfd.readouterr()

    email = "tmp_{}@xyz.com".format(random.randint(0, 1023123123123))
    mu.add_email_account(email, password="123")
    cap = capfd.readouterr()
    print(cap.out)
    assert cap.out.strip().endswith("123")
    assert os.path.exists(mu.mail_config.path_virtual_mailboxes + ".db")
    assert os.path.exists(os.path.join(mu.mail_config.path_vmaildir, email))


def test_add_user_auto_remove(mail_controller_maker, monkeypatch):
    mu = mail_controller_maker(domain="xyz.com", expiry="1w")
    mu.add_email_account("tmp_123@xyz.com", password="123")

    # create a current account
    now = time.time()
    monkeypatch.setattr(time, "time", lambda: 10.0)
    mu.add_email_account("tmp_old@xyz.com", password="123")
    monkeypatch.undo()

    accounts = mu.prune_expired_accounts(dryrun=True)
    assert accounts == ["tmp_old@xyz.com"]

    accounts = mu.prune_expired_accounts(dryrun=False)
    assert accounts == ["tmp_old@xyz.com"]

    assert not mu.prune_expired_accounts(dryrun=False)


def test_remove_user(mail_controller_maker, capfd):
    mu = mail_controller_maker(domain="xyz.com")

    email = "tmp_{}@xyz.com".format(random.randint(0, 1023123123123))
    mu.add_email_account(email, password="123")
    cap = capfd.readouterr()
    print(cap.out)
    assert cap.out.strip().endswith("123")
    assert os.path.exists(mu.mail_config.path_virtual_mailboxes + ".db")

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

    dirs = mu.remove_accounts(accounts)
    assert not mu.find_email_accounts(prefix="tmp_")
    assert len(dirs) == 2
    for email, path in dirs:
        assert "vmail" in path
    accounts = mu.find_email_accounts()
    assert len(accounts) == 1
    assert accounts[0].startswith("somebody@xyz.com")
