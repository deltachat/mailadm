from time import sleep


class TestAdminGroup:
    def create_admingroup(self, admbot, botuser, db):
        admchat = admbot.create_group_chat("admins", [], verified=True)
        with db.write_transaction() as conn:
            conn.set_config("admingrpid", admchat.id)
        qr = admchat.get_join_qr()
        chat = botuser.qr_join_chat(qr)
        while not chat.is_protected():
            sleep(0.1)
        return chat


    def test_help(self, admbot, botuser, db):
        admingroup = self.create_admingroup(admbot, botuser, db)
        admingroup.send_text("/help")
        while len(admingroup.get_messages()) < 7:
            sleep(0.1)
        raise ValueError(admingroup.get_messages()[6].text)


def test_setup_bot():
    pass


def test_reply():
    pass


def test_check_privileges():
    pass
