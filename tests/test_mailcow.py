from random import randint

import pytest
from mailadm.mailcow import MailcowError


class TestMailcow:
    def test_get_users(self, mailcow):
        mailcow.get_user_list()

    def test_add_del_user(self, mailcow, mailcow_domain):
        addr = "pytest.%s@%s" % (randint(0, 99999), mailcow_domain)
        mailcow.add_user_mailcow(addr, "asdf1234", "pytest")

        user = mailcow.get_user(addr)
        assert user.addr == addr
        assert user.token == "pytest"

        mailcow.del_user_mailcow(addr)
        assert mailcow.get_user(addr) is None

    def test_wrong_token(self, mailcow, mailcow_domain):
        mailcow.auth = {"X-API-Key": "asdf"}
        addr = "pytest.%s@%s" % (randint(0, 99999), mailcow_domain)
        with pytest.raises(MailcowError):
            mailcow.get_user_list()
        with pytest.raises(MailcowError):
            mailcow.add_user_mailcow(addr, "asdf1234", "pytest")
        with pytest.raises(MailcowError):
            mailcow.get_user(addr)
        with pytest.raises(MailcowError):
            mailcow.del_user_mailcow(addr)
