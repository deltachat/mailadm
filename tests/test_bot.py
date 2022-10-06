import time
import pytest
import deltachat


TIMEOUT = 90


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
        direct = admingroup.botadmin.create_chat(admingroup.admbot.get_config("addr"))
        direct.send_text("/list-tokens")
        num_msgs = len(direct.get_messages())
        while len(direct.get_messages()) == num_msgs:  # this sometimes never completes
            time.sleep(0.1)
        assert direct.get_messages()[1].text == "Sorry, I only take commands from the admin group."


class SupportGroupUserPlugin:
    def __init__(self, account, botaddr):
        self.account = account
        self.account.add_account_plugin(deltachat.events.FFIEventLogger(self.account))
        self.botaddr = botaddr

    @deltachat.account_hookimpl
    def ac_incoming_message(self, message: deltachat.Message):
        message.create_chat()

        assert message.chat.is_protected()
        assert len(message.chat.get_contacts()) == 2
        assert message.text == "Can I ask you a support question?"
        assert message.get_sender_contact().addr == self.botaddr

        message.chat.send_text("I hope the user can't read this")
        print("sent secret message")
        reply = deltachat.Message.new_empty(self.account, "text")
        reply.set_text("Yes of course you can ask us :)")
        reply.quote = message
        message.chat.send_msg(reply)
        print("sent public message")


@pytest.mark.timeout(TIMEOUT)
class TestSupportGroup:
    def test_support_group_relaying(self, admingroup, supportuser):
        supportchat = supportuser.create_chat(admingroup.admbot.get_config("addr"))
        question = "Can I ask you a support question?"
        supportchat.send_text(question)
        admin = admingroup.botadmin
        botaddr = admingroup.admbot.get_config("addr")
        admin.add_account_plugin(SupportGroupUserPlugin(admin, botaddr))
        while len(admin.get_chats()) < 2:
            time.sleep(0.1)
        # AcceptChatPlugin will send 2 messages to the support group now
        support_group_name = supportuser.get_config("addr")
        supportgroup = next(filter(lambda chat: chat.get_name() == support_group_name,
                                   admin.get_chats()))
        while len(supportchat.get_messages()) < 2:
            time.sleep(0.1)
        botreply = supportchat.get_messages()[1]
        assert botreply.text == "Yes of course you can ask us :)"
        supportchat.send_text("Okay, I will think of something :)")
        while len(supportgroup.get_messages()) < 4:
            time.sleep(0.1)
        assert "I hope the user can't read this" not in \
               [msg.text for msg in supportchat.get_messages()]

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
