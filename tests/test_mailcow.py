import pytest
from random import randint
from mailadm.mailcow import MailcowConnection


class TestMailcow:
    @pytest.fixture
    def mailcow(self, db):
        with db.read_connection() as conn:
            return MailcowConnection(conn.config)

    def test_get_users(self, mailcow):
        mailcow.get_user()

    def test_add_del_user(self, mailcow):
        addr = "pytest.%s@x.testrun.org" % (randint(0, 999),)
        mailcow.add_user_mailcow(addr, "asdf1234")

        json = mailcow.get_user(addr=addr).json()
        assert json["username"] == addr

        mailcow.del_user_mailcow(addr)
        json = mailcow.get_user().json()
        for entry in json:
            assert entry.get("username") != json
