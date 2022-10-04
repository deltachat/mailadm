import time
import pytest


TIMEOUT = 60


class TestAdminGroup:
    def test_help(self, admingroup):
        num_msgs = len(admingroup.get_messages())
        admingroup.send_text("/help")
        begin = time.time()
        while len(admingroup.get_messages()) < num_msgs + 2:  # this sometimes never completes
            time.sleep(0.1)
            if time.time() > begin + TIMEOUT:
                pytest.fail("Bot reply took more than %s seconds" % (TIMEOUT,))
        reply = admingroup.get_messages()[num_msgs + 1]
        assert reply.text.startswith("/add-user addr password token")

    def test_list_tokens(self, admingroup):
        num_msgs = len(admingroup.get_messages())
        admingroup.send_text("/list-tokens")  # command =
        begin = time.time()
        while len(admingroup.get_messages()) < num_msgs + 2:  # this sometimes never completes
            time.sleep(0.1)
            if time.time() > begin + TIMEOUT:
                pytest.fail("Bot reply took more than %s seconds" % (TIMEOUT,))
        reply = admingroup.get_messages()[num_msgs + 2]
        assert reply.text.startswith("Existing tokens:")
        # assert reply.quote == command  # wait for #53

    def test_check_privileges(self, admingroup):
        direct = admingroup.botuser.create_chat(admingroup.admbot.get_config("addr"))
        direct.send_text("/list-tokens")
        num_msgs = len(direct.get_messages())
        begin = time.time()
        while len(direct.get_messages()) == num_msgs:  # this sometimes never completes
            time.sleep(0.1)
            if time.time() > begin + TIMEOUT + 10:  # this can take a bit longer, no problem
                pytest.fail("Bot reply took more than %s seconds" % (TIMEOUT + 10,))
        assert direct.get_messages()[1].text == "Sorry, I only take commands from the admin group."
