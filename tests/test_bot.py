import time
import pytest


TIMEOUT = 60


class TestAdminGroup:
    @pytest.mark.timeout(TIMEOUT)
    def test_help(self, admingroup):
        num_msgs = len(admingroup.get_messages())
        admingroup.send_text("/help")
        while len(admingroup.get_messages()) < num_msgs + 2:  # this sometimes never completes
            time.sleep(0.1)
        reply = admingroup.get_messages()[num_msgs + 1]
        assert reply.text.startswith("/add-user addr password token")

    @pytest.mark.timeout(TIMEOUT)
    def test_list_tokens(self, admingroup):
        num_msgs = len(admingroup.get_messages())
        admingroup.send_text("/list-tokens")  # command =
        while len(admingroup.get_messages()) < num_msgs + 2:  # this sometimes never completes
            time.sleep(0.1)
        reply = admingroup.get_messages()[num_msgs + 1]
        assert reply.text.startswith("Existing tokens:")
        # assert reply.quote == command  # wait for #53

    @pytest.mark.timeout(TIMEOUT)
    def test_check_privileges(self, admingroup):
        direct = admingroup.botuser.create_chat(admingroup.admbot.get_config("addr"))
        direct.send_text("/list-tokens")
        num_msgs = len(direct.get_messages())
        while len(direct.get_messages()) == num_msgs:  # this sometimes never completes
            time.sleep(0.1)
        assert direct.get_messages()[1].text == "Sorry, I only take commands from the admin group."
