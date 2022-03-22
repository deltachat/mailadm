from random import randint


class TestMailcow:
    def test_get_users(self, mailcow):
        mailcow.get_user_list()

    def test_add_del_user(self, mailcow):
        addr = "pytest.%s@x.testrun.org" % (randint(0, 999),)
        mailcow.add_user_mailcow(addr, "asdf1234")

        user = mailcow.get_user(addr)
        assert user.addr == addr

        mailcow.del_user_mailcow(addr)
        assert mailcow.get_user(addr) is None
