import time
import pytest


TIMEOUT = 60


@pytest.mark.timeout(TIMEOUT)
class TestAdminGroup:
    def test_help(self, admingroup):
        num_msgs = len(admingroup.get_messages())
        admingroup.send_text("/help")
        while len(admingroup.get_messages()) < num_msgs + 2:  # this sometimes never completes
            time.sleep(0.1)
        reply = admingroup.get_messages()[num_msgs + 1]
        assert reply.text.startswith("/add-user addr password token")

    def test_list_tokens(self, admingroup):
        num_msgs = len(admingroup.get_messages())
        command = admingroup.send_text("/list-tokens")
        while len(admingroup.get_messages()) < num_msgs + 2:  # this sometimes never completes
            time.sleep(0.1)
        reply = admingroup.get_messages()[num_msgs + 1]
        assert reply.text.startswith("Existing tokens:")
        assert reply.quote == command

    def test_check_privileges(self, admingroup):
        direct = admingroup.botuser.create_chat(admingroup.admbot.get_config("addr"))
        direct.send_text("/list-tokens")
        num_msgs = len(direct.get_messages())
        while len(direct.get_messages()) == num_msgs:  # this sometimes never completes
            time.sleep(0.1)
        assert direct.get_messages()[1].text == "Sorry, I only take commands from the admin group."


class TestSupportGroup:
    @pytest.mark.timeout(TIMEOUT)
    def test_invite_bot_to_group(self, admingroup, supportuser):
        botcontact = supportuser.create_contact(admingroup.admbot.get_config("addr"))
        false_group = supportuser.create_group_chat("invite bot", [botcontact])
        num_msgs = len(false_group.get_messages())
        false_group.send_text("Welcome, bot!")
        while len(false_group.get_messages()) < num_msgs + 3:
            time.sleep(0.1)
        assert len(false_group.get_contacts()) == 1
        sorry_message = "Sorry, I'm a strictly non-group bot. You can talk to me 1:1."
        assert false_group.get_messages()[num_msgs + 1].text == sorry_message
        assert botcontact.get_profile_image()
