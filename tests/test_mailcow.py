from random import randint

import pytest
from mailadm.mailcow import MailcowError


class TestMailcow:
    def test_get_users(self, mailcow):
        mailcow.get_user_list()

    def test_add_del_user(self, mailcow):
        addr = "pytest.%s@x.testrun.org" % (randint(0, 999),)
        mailcow.add_user_mailcow(addr, "asdf1234", "pytest")

        user = mailcow.get_user(addr)
        assert user.addr == addr
        assert "token:pytest" in user.tags

        mailcow.del_user_mailcow(addr)
        assert mailcow.get_user(addr) is None

    def test_wrong_token(self, mailcow):
        mailcow.auth = {"X-API-Key": "asdf"}
        addr = "pytest.%s@x.testrun.org" % (randint(0, 999),)
        with pytest.raises(MailcowError):
            mailcow.get_user_list()
        with pytest.raises(MailcowError):
            mailcow.add_user_mailcow(addr, "asdf1234", "pytest")
        with pytest.raises(MailcowError):
            mailcow.get_user(addr)
        with pytest.raises(MailcowError):
            mailcow.del_user_mailcow(addr)
