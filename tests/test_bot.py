import time
import pytest


class TestAdminGroup:
    def create_admingroup(self, admbot, botuser, db):
        admchat = admbot.create_group_chat("admins", [], verified=True)
        with db.write_transaction() as conn:
            conn.set_config("admingrpid", admchat.id)
        qr = admchat.get_join_qr()
        chat = botuser.qr_join_chat(qr)
        while not chat.is_protected():
            time.sleep(0.1)
        return chat

    def test_help(self, admbot, botuser, db):
        admingroup = self.create_admingroup(admbot, botuser, db)
        admingroup.send_text("/help")
        begin = time.time()
        while len(admingroup.get_messages()) < 7:
            time.sleep(0.1)
            if time.time() > begin + 20:
                pytest.fail("Bot reply took more than 20 seconds")
        assert admingroup.get_messages()[6].text.startswith("/add-user addr password token")

    def test_list_tokens(self, admbot, botuser, db):
        admingroup = self.create_admingroup(admbot, botuser, db)
        command = admingroup.send_text("/list-tokens")
        begin = time.time()
        while len(admingroup.get_messages()) < 7:  # this sometimes never completes
            time.sleep(0.1)
            if time.time() > begin + 20:
                pytest.fail("Bot reply took more than 20 seconds")
        assert admingroup.get_messages()[6].text.startswith("Existing tokens:")
        #assert admingroup.get_messages()[6].quote == command  # wait for #53

    def test_check_privileges(self, admbot, botuser, db):
        self.create_admingroup(admbot, botuser, db)
        direct = botuser.create_chat(admbot.get_config("addr"))
        direct.send_text("/list-tokens")
        begin = time.time()
        while len(direct.get_messages()) < 2:  # this sometimes never completes
            time.sleep(0.1)
            if time.time() > begin + 20:
                pytest.fail("Bot reply took more than 20 seconds")
        assert direct.get_messages()[1].text == "Sorry, I only take commands from the admin group."
