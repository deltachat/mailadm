import time
import pytest


TIMEOUT = 60


class TestAdminGroup:
    def test_help(self, admingroup):
        admingroup.send_text("/help")
        begin = time.time()
        while len(admingroup.get_messages()) < 7:
            time.sleep(0.1)
            if time.time() > begin + TIMEOUT:
                pytest.fail("Bot reply took more than %s seconds" % (TIMEOUT,))
        assert admingroup.get_messages()[6].text.startswith("/add-user addr password token")

    def test_list_tokens(self, admingroup):
        admingroup.send_text("/list-tokens")  # command =
        begin = time.time()
        while len(admingroup.get_messages()) < 7:  # this sometimes never completes
            time.sleep(0.1)
            if time.time() > begin + TIMEOUT:
                pytest.fail("Bot reply took more than %s seconds" % (TIMEOUT,))
        assert admingroup.get_messages()[6].text.startswith("Existing tokens:")
        # assert admingroup.get_messages()[6].quote == command  # wait for #53

    def test_check_privileges(self, admingroup):
        direct = admingroup.botuser.create_chat(admingroup.admbot.get_config("addr"))
        direct.send_text("/list-tokens")
        begin = time.time()
        while len(direct.get_messages()) < 2:  # this sometimes never completes
            time.sleep(0.1)
            if time.time() > begin + TIMEOUT + 10:  # this can take a bit longer, no problem
                pytest.fail("Bot reply took more than %s seconds" % (TIMEOUT + 10,))
        assert direct.get_messages()[1].text == "Sorry, I only take commands from the admin group."
