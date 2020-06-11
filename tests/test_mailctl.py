import pytest
import random
import time
import os
from mailadm.config import Config, parse_expiry_code


@pytest.fixture
def mail_controller_maker(make_ini_from_values):
    def make_mail_controller(name="test", expiry="never", dryrun=False):
        inipath = make_ini_from_values(name=name, expiry=expiry)
        config = Config(inipath)
        token_config = config.get_token_config_from_name(name)
        return token_config.make_controller()

    return make_mail_controller


def test_add_user(mail_controller_maker, capfd):
    mu = mail_controller_maker()
    with pytest.raises(ValueError):
        email = "tmp_{}@xyz.org".format(random.randint(0, 1023123123123))
        mu.add_email_account(email)
    capfd.readouterr()

    email = "tmp_{}@testrun.org".format(random.randint(0, 1023123123123))
    mu.add_email_account(email, password="123")
    cap = capfd.readouterr()
    print(cap.out)
    assert cap.out.strip().endswith("123")
    assert os.path.exists(mu.token_config.sysconfig.path_virtual_mailboxes + ".db")

    # the mail controller leaves creation of vmail directories to dovecot (the MDA)
    # assert os.path.exists(os.path.join(mu.token_config.path_vmaildir, email))


def test_add_user_auto_remove(mail_controller_maker, monkeypatch):
    mu = mail_controller_maker(expiry="1w")
    mu.add_email_account("tmp_123@testrun.org", password="123")

    # create a current account
    outdated = time.time() - parse_expiry_code(mu.token_config.expiry) - 1
    monkeypatch.setattr(time, "time", lambda: outdated)
    mu.add_email_account("tmp_old@testrun.org", password="123")
    monkeypatch.undo()
    mu.add_email_account("tmp_456@testrun.org", password="123")

    assert len(mu.find_email_accounts()) == 3

    # prune it in dryrun
    assert mu.prune_expired_accounts(dryrun=True) == ["tmp_old@testrun.org"]
    assert len(mu.find_email_accounts()) == 3

    # prune it for real
    assert mu.prune_expired_accounts(dryrun=False) == ["tmp_old@testrun.org"]

    # check there is no expired account left
    assert not mu.prune_expired_accounts(dryrun=False)

    assert len(mu.find_email_accounts()) == 2


def test_remove_user(mail_controller_maker, capfd):
    mu = mail_controller_maker()

    email = "tmp_{}@testrun.org".format(random.randint(0, 1023123123123))
    mu.add_email_account(email, password="123")
    cap = capfd.readouterr()
    print(cap.out)
    assert cap.out.strip().endswith("123")
    assert os.path.exists(mu.token_config.sysconfig.path_virtual_mailboxes + ".db")

    email2 = "tmp_{}@testrun.org".format(random.randint(0, 1023123123123))
    mu.add_email_account(email2, password="456")
    cap = capfd.readouterr()
    print(cap.out)
    assert cap.out.strip().endswith("456")

    email3 = "somebody@testrun.org"
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
    assert accounts[0].startswith("somebody@testrun.org")
