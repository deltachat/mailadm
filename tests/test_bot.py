import time
from random import randint

import deltachat
import pytest
from deltachat.capi import lib as dclib

TIMEOUT = 30


@pytest.mark.timeout(TIMEOUT)
class TestAdminGroup:
    def test_help(self, admingroup):
        admingroup.send_text("/help")
        while "/add-user" not in admingroup.get_messages()[len(admingroup.get_messages()) - 1].text:
            print(admingroup.get_messages()[len(admingroup.get_messages()) - 1].text)
            time.sleep(1)
        reply = admingroup.get_messages()[len(admingroup.get_messages()) - 1]
        assert reply.text.startswith("/add-user addr password token")

    def test_list_tokens(self, admingroup):
        command = admingroup.send_text("/list-tokens")
        while "Existing" not in admingroup.get_messages()[len(admingroup.get_messages()) - 1].text:
            print(admingroup.get_messages()[len(admingroup.get_messages()) - 1].text)
            time.sleep(1)
        reply = admingroup.get_messages()[len(admingroup.get_messages()) - 1]
        assert reply.text.startswith("Existing tokens:")
        assert reply.quote == command

    def test_wrong_number_of_arguments(self, admingroup):
        command = admingroup.send_text("/add-token pytest")
        while "Sorry" not in admingroup.get_messages()[len(admingroup.get_messages()) - 1].text:
            print(admingroup.get_messages()[len(admingroup.get_messages()) - 1].text)
            time.sleep(1)
        reply = admingroup.get_messages()[len(admingroup.get_messages()) - 1]
        assert reply.quote == command
        print(reply.text)

    @pytest.mark.skip("This test works in real life, but not under test conditions somehow")
    def test_check_privileges(self, admingroup):
        direct = admingroup.botadmin.create_chat(admingroup.admbot.get_config("addr"))
        direct.send_text("/list-tokens")
        while "Sorry, I" not in direct.get_messages()[-1].text:
            print(direct.get_messages()[-1].text)
            time.sleep(0.1)
        assert direct.get_messages()[-1].text == "Sorry, I only take commands from the admin group."

    def test_adduser_input(self, admingroup, mailcow_domain, db):
        with db.write_transaction() as wconn:
            wconn.add_token("weirdinput", "1w_7wDioPeeXyZx96v3", "1s", "weirdinput.")
        input_1 = "weirdinput.%s@test1@%s" % (randint(0, 99999), mailcow_domain)
        admingroup.send_text("/add-user %s abcd1234 weirdinput" % (input_1,))
        input_2 = "weirdinput.%s@test2@a%s" % (randint(0, 99999), mailcow_domain)
        admingroup.send_text("/add-user %s abcd1234 weirdinput" % (input_2,))
        input_3 = "weirdinput.%s@%s@test3@%s" % (randint(0, 99999), mailcow_domain, mailcow_domain)
        admingroup.send_text("/add-user %s abcd1234 weirdinput" % (input_3,))
        input_4 = "weirdinput.%s@%s@test4@a%s" % (randint(0, 99999), mailcow_domain, mailcow_domain)
        admingroup.send_text("/add-user %s abcd1234 weirdinput" % (input_4,))
        # wait until all messages were processed
        with db.read_connection() as conn:
            while "failed to add e-mail account " + input_4 not in admingroup.get_messages()[-1].text:
                print(admingroup.get_messages()[-1].text)
                users = conn.get_user_list()
                for user in users:
                    if user.token_name == "WARNING: does not exist in mailcow":
                        print("---")
                        for user2 in users:
                            print(user2.addr, user2.token_name)
                        print("---")
                        for msg in admingroup.get_messages():
                            print(msg.text)
                        print("---")
                        pytest.fail()
                time.sleep(0.1)


@pytest.mark.timeout(TIMEOUT * 2)
class TestSupportGroup:
    def test_support_group_relaying(self, admingroup, supportuser):
        class SupportGroupUserPlugin:
            def __init__(self, account, supportuser):
                self.account = account
                self.account.add_account_plugin(deltachat.events.FFIEventLogger(self.account))
                self.supportuser = supportuser

            @deltachat.account_hookimpl
            def ac_incoming_message(self, message: deltachat.Message):
                message.create_chat()

                assert len(message.chat.get_contacts()) == 2
                assert message.override_sender_name == self.supportuser.get_config("addr")

                if message.text == "Can I ask you a support question?":
                    message.chat.send_text("I hope the user can't read this")
                    print("\n  botadmin to supportgroup: I hope the user can't read this\n")
                    reply = deltachat.Message.new_empty(self.account, "text")
                    reply.set_text("Yes of course you can ask us :)")
                    reply.quote = message
                    message.chat.send_msg(reply)
                    print("\n  botadmin to supportgroup: Yes of course you can ask us :)\n")
                else:
                    print("\n  botadmin received:", message.text, "\n")

        supportchat = supportuser.create_chat(admingroup.admbot.get_config("addr"))
        question = "Can I ask you a support question?"
        supportchat.send_text(question)
        print("\n  supportuser to supportchat: Can I ask you a support question?\n")
        admin = admingroup.botadmin
        admin.add_account_plugin(SupportGroupUserPlugin(admin, supportuser))
        while len(admin.get_chats()) < 2:
            time.sleep(0.1)
        # AcceptChatPlugin will send 2 messages to the support group now
        support_group_name = supportuser.get_config("addr") + " support group"
        for chat in admin.get_chats():
            print(chat.get_name() + str(chat.id))
        supportgroup = next(
            filter(lambda chat: chat.get_name() == support_group_name, admin.get_chats()),
        )
        while "Yes of" not in supportchat.get_messages()[len(supportchat.get_messages()) - 1].text:
            print(supportchat.get_messages()[len(supportchat.get_messages()) - 1].text)
            time.sleep(1)
        botreply = supportchat.get_messages()[1]
        assert botreply.text == "Yes of course you can ask us :)"
        supportchat.send_text("Okay, I will think of something :)")
        print("\n  supportuser to supportchat: Okay, I will think of something :)\n")
        while "Okay," not in supportgroup.get_messages()[len(supportgroup.get_messages()) - 1].text:
            print(supportchat.get_messages()[len(supportchat.get_messages()) - 1].text)
            time.sleep(1)
        assert "I hope the user can't read this" not in [
            msg.text for msg in supportchat.get_messages()
        ]

    def test_invite_bot_to_group(self, admingroup, supportuser):
        botcontact = supportuser.create_contact(admingroup.admbot.get_config("addr"))
        false_group = supportuser.create_group_chat("invite bot", [botcontact])
        false_group.send_text("Welcome, bot!")
        while "left by %s" % (botcontact.addr,) not in false_group.get_messages()[-1].text:
            print(false_group.get_messages()[-1].text)
            time.sleep(0.1)
        assert len(false_group.get_contacts()) == 1
        sorry_message = "Sorry, you can not contact me in groups. Please use a 1:1 chat."
        assert false_group.get_messages()[-2].text == sorry_message

    def test_bot_receives_system_message(self, admingroup):
        def get_group_chats(account):
            group_chats = []
            for chat in ac.get_chats():
                if chat.is_group():
                    group_chats.append(chat)
            return group_chats

        ac = admingroup.admbot
        num_chats = len(get_group_chats(ac))
        # put system message in admbot's INBOX
        dev_msg = deltachat.Message.new_empty(ac, "text")
        dev_msg.set_text("This shouldn't create a support group")
        dclib.dc_add_device_msg(ac._dc_context, bytes("test_device_msg", "ascii"), dev_msg._dc_msg)
        # assert that admbot didn't create a support group
        assert num_chats == len(get_group_chats(ac))

    def test_did_bot_create_support_group(self, admingroup, supportuser):
        # send first message to support user to test that it isn't seen as support group later
        bot = admingroup.admbot
        supportchat_bot_side = bot.create_chat(supportuser.get_config("addr"))
        supportchat_bot_side.send_text("Your account will expire soon!")

        # create support group
        supportchat = supportuser.create_chat(admingroup.admbot.get_config("addr"))
        question = "Can I ask you a support question?"
        supportchat.send_text(question)
        support_group_name = supportuser.get_config("addr") + " support group"

        # wait for supportgroup to be created
        while 1:
            try:
                supportgroup = next(
                    filter(lambda chat: chat.get_name() == support_group_name, bot.get_chats()),
                )
                print(supportgroup.get_messages()[0].get_sender_contact().addr)
            except (StopIteration, IndexError):
                time.sleep(0.1)
            else:
                break
        print(bot.get_self_contact().addr)

        assert admingroup.botplugin.is_support_group(supportgroup)
        assert not admingroup.botplugin.is_support_group(admingroup)
        assert not admingroup.botplugin.is_support_group(supportchat_bot_side)

    def test_support_user_help(self, admingroup, supportuser):
        supchat = supportuser.create_chat(admingroup.admbot.get_config("addr"))
        supchat.send_text("/help")
        while "use this chat to talk to the admins." not in supchat.get_messages()[-1].text:
            time.sleep(0.1)
        supchat.send_text("/list-tokens")
        while "Sorry, I" not in supchat.get_messages()[-1].text:
            print(supchat.get_messages()[-1].text)
            time.sleep(0.1)
        assert supchat.get_messages()[-1].text == "Sorry, I only take commands in the admin group."
