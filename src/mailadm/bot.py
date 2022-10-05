import sys
import sqlite3
import time

import deltachat
from deltachat import account_hookimpl
from mailadm.db import DB, get_db_path
from mailadm.commands import add_user, add_token, list_tokens, qr_from_token
import os
from threading import Event


class SetupPlugin:
    def __init__(self, admingrpid):
        self.member_added = Event()
        self.admingrpid = admingrpid
        self.message_sent = Event()

    @account_hookimpl
    def ac_member_added(self, chat: deltachat.Chat, contact, actor, message):
        if chat.id == self.admingrpid:
            if chat.num_contacts() == 2:
                self.member_added.set()

    @account_hookimpl
    def ac_message_delivered(self, message: deltachat.Message):
        if not message.is_system_message():
            self.message_sent.set()


class AdmBot:
    def __init__(self, db: DB, account: deltachat.Account):
        self.db = db
        self.account = account
        with self.db.read_connection() as conn:
            config = conn.config
            self.admingrpid = config.admingrpid

    @account_hookimpl
    def ac_incoming_message(self, message: deltachat.Message):
        arguments = message.text.split(" ")
        print("process_incoming command:", arguments)
        if not self.check_privileges(message):
            message.create_chat()
            message.chat.send_text("Sorry, I only take commands from the admin group.")
            return

        if arguments[0] == "/help":
            text = ("/add-user addr password token\n"
                    "/add-token name expiry maxuse (prefix)\n"
                    "/gen-qr token\n"
                    "/list-users (token)\n"
                    "/list-tokens")
            message.chat.send_text(text)

        elif arguments[0] == "/add-token":
            if len(arguments) == 4:
                arguments.append("")  # add empty prefix
            text = add_token(self.db, name=arguments[1], expiry=arguments[2], maxuse=arguments[3],
                             prefix=arguments[4], token=None).get("message")
            message.chat.send_text(text)
            fn = qr_from_token(self.db, arguments[1])["filename"]
            message.chat.send_image(fn)

        elif arguments[0] == "/gen-qr":
            fn = qr_from_token(self.db, tokenname=arguments[1]).get("filename")
            message.chat.send_image(fn)

        elif arguments[0] == "/add-user":
            arguments = message.text.split(" ")
            result = add_user(self.db, addr=arguments[1], password=arguments[2], token=arguments[3])
            if result.get("status") == "success":
                user = result.get("message")
                text = "successfully created %s with password %s" % (user.addr, user.password)
            else:
                text = result.get("message")
            message.chat.send_text(text)

        elif arguments[0] == "/list-users":
            token = arguments[1] if len(arguments) > 1 else None
            with self.db.read_connection() as conn:
                users = conn.get_user_list(token=token)
            lines = ["%s [%s]" % (user.addr, user.token_name) for user in users]
            text = "\n".join(lines)
            message.chat.send_text(text)

        elif arguments[0] == "/list-tokens":
            message.chat.send_text(list_tokens(self.db))

    def check_privileges(self, command: deltachat.Message):
        """
        Checks whether the incoming message was in the admin group.
        """
        if command.chat.is_group() and self.admingrpid == str(command.chat.id):
            if command.chat.is_protected() \
                    and command.is_encrypted() \
                    and int(command.chat.num_contacts()) >= 2:
                if command.get_sender_contact() in command.chat.get_contacts():
                    return True
                else:
                    print("%s is not allowed to give commands to mailadm." %
                          (command.get_sender_contact(),))
            else:
                print("admin chat is broken. Try `mailadm setup-bot`. Group ID:", self.admingrpid)
                raise ValueError
        else:
            return False


def get_admbot_db_path():
    db_path = os.environ.get("ADMBOT_DB", "/mailadm/docker-data/admbot.db")
    try:
        sqlite3.connect(db_path)
    except sqlite3.OperationalError:
        raise RuntimeError("admbot.db not found: ADMBOT_DB not set")
    return db_path


def run_bot(mailadm_db, admbot_db_path):
    ac = deltachat.Account(admbot_db_path)
    if not ac.is_configured():
        print("if you want to talk to mailadm with Delta Chat, please run: mailadm setup-bot",
              file=sys.stderr)
    conn = mailadm_db.read_connection(closing=False)
    while "admingrpid" not in [item[0] for item in conn.get_config_items()]:
        time.sleep(1)
    else:
        conn.close()
        ac = deltachat.Account(get_admbot_db_path())
        ac.run_account(account_plugins=[AdmBot(mailadm_db, ac)], show_ffi=True)
    return ac


def main(account):
    account.wait_shutdown()
    print("shutting down bot.", file=sys.stderr)


if __name__ == "__main__":
    mailadm_db = DB(get_db_path())
    admbot_db_path = get_admbot_db_path()
    main(mailadm_db, admbot_db_path)
