import mimetypes
import sys
import sqlite3
import time

import deltachat
from deltachat import account_hookimpl
from deltachat.capi import lib as dclib
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
            self.admingrpid = int(config.admingrpid)
            self.admingroup = account.get_chat_by_id(self.admingrpid)

    @account_hookimpl
    def ac_incoming_message(self, message: deltachat.Message):
        arguments = message.text.split(" ")
        print("process_incoming message:", message.text)
        if not self.is_admin_group_message(message):
            chat = message.create_chat()
            if chat.is_group():
                if message.get_sender_contact() not in self.admingroup.get_contacts():
                    print("%s added me to a group, I'm leaving it." %
                          (message.get_sender_contact().addr,))
                    chat.send_text("Sorry, you can not contact me in a group chat. Please use a 1:1"
                                   " chat.")
                    chat.remove_contact(self.account.get_self_contact())   # leave group
                elif message.quote:  # reply to user
                    if message.quote.get_sender_contact().addr == self.account.get_config("addr"):
                        recipient = chat.get_name()
                        print("I'm forwarding the admin reply to the support user %s." %
                              (recipient,))
                        chat = self.account.create_chat(recipient)
                        chat.send_msg(message)
                else:
                    print("ignoring message, it's just admins discussing in a support group.")
            elif message.text[0] == "/":
                print("command was not supplied in a group, let alone the admin group.")
                chat.send_text("Sorry, I only take commands from the admin group.")
            else:
                print("forwarding the message to a support group.")
                name = message.get_sender_contact().addr
                admins = self.admingroup.get_contacts()
                admins.remove(self.account.get_self_contact())
                for chat in self.account.get_chats():
                    if chat.get_name() == name:
                        if chat.is_group():
                            supportgroup = chat
                            break
                else:
                    print("creating new support group:", name)
                    supportgroup = self.account.create_group_chat(name, admins, True)
                message.set_override_sender_name(message.get_sender_contact().addr)
                supportgroup.send_msg(message)
            return
        print(message.text, "seems to be a valid message.")

        if arguments[0] == "/help":
            text = ("/add-user addr password token\n"
                    "/add-token name expiry maxuse (prefix)\n"
                    "/gen-qr token\n"
                    "/list-users (token)\n"
                    "/list-tokens")
            self.reply(text, message)

        elif arguments[0] == "/add-token":
            if len(arguments) == 4:
                arguments.append("")  # add empty prefix
            result = add_token(self.db, name=arguments[1], expiry=arguments[2], maxuse=arguments[3],
                             prefix=arguments[4], token=None)
            if result["status"] == "error":
                return self.reply("ERROR: " + result.get("message"), message)
            text = result.get("message")
            fn = qr_from_token(self.db, arguments[1])["filename"]
            self.reply(text, message, img_fn=fn)

        elif arguments[0] == "/gen-qr":
            fn = qr_from_token(self.db, tokenname=arguments[1]).get("filename")
            self.reply("", message, img_fn=fn)

        elif arguments[0] == "/add-user":
            arguments = message.text.split(" ")
            result = add_user(self.db, addr=arguments[1], password=arguments[2], token=arguments[3])
            if result.get("status") == "success":
                user = result.get("message")
                text = "successfully created %s with password %s" % (user.addr, user.password)
            else:
                text = result.get("message")
            self.reply(text, message)

        elif arguments[0] == "/list-users":
            token = arguments[1] if len(arguments) > 1 else None
            with self.db.read_connection() as conn:
                users = conn.get_user_list(token=token)
            lines = ["%s [%s]" % (user.addr, user.token_name) for user in users]
            text = "\n".join(lines)
            self.reply(text, message)

        elif arguments[0] == "/list-tokens":
            self.reply(list_tokens(self.db), message)

    def is_admin_group_message(self, command: deltachat.Message):
        """
        Checks whether the incoming message was in the admin group.
        """
        if command.chat.is_group() and self.admingrpid == command.chat.id:
            if command.chat.is_protected() \
                    and command.is_encrypted() \
                    and int(command.chat.num_contacts()) >= 2:
                if command.get_sender_contact() in command.chat.get_contacts():
                    return True
                else:
                    print("%s is not allowed to give commands to mailadm." %
                          (command.get_sender_contact(),))
            else:
                print("The admin group is broken. Try `mailadm setup-bot`. Group ID:",
                      str(self.admingrpid))
                raise ValueError
        else:
            return False

    def reply(self, text: str, reply_to: deltachat.Message, img_fn=None):
        """The bot replies to command in the admin group

        :param text: text of the reply
        :param reply_to: the message object which triggered the reply
        :param img_fn: if an image is to be sent, its filename
        """
        if img_fn:
            msg = deltachat.Message.new_empty(self.account, "image")
            mime_type = mimetypes.guess_type(img_fn)[0]
            msg.set_file(img_fn, mime_type)
        else:
            msg = deltachat.Message.new_empty(self.account, "text")
        msg.set_text(text)
        msg.quote = reply_to
        sent_id = dclib.dc_send_msg(self.account._dc_context, self.admingroup.id, msg._dc_msg)
        assert sent_id == msg.id


def get_admbot_db_path(db_path=None):
    if not db_path:
        db_path = os.environ.get("ADMBOT_DB", "/mailadm/docker-data/admbot.db")
    try:
        sqlite3.connect(db_path)
    except sqlite3.OperationalError:
        raise RuntimeError("admbot.db not found: ADMBOT_DB not set")
    return db_path


def main(mailadm_db, admbot_db_path):
    ac = deltachat.Account(admbot_db_path)
    if not ac.is_configured():
        print("if you want to talk to mailadm with Delta Chat, please run: mailadm setup-bot",
              file=sys.stderr)
    conn = mailadm_db.read_connection(closing=False)
    while "admingrpid" not in [item[0] for item in conn.get_config_items()]:
        time.sleep(1)
    else:
        displayname = conn.config.mail_domain + " administration"
        conn.close()
        ac.set_avatar("assets/avatar.jpg")
        ac.run_account(account_plugins=[AdmBot(mailadm_db, ac)], show_ffi=True)
        ac.set_config("displayname", displayname)
    ac.wait_shutdown()
    print("shutting down bot.", file=sys.stderr)


if __name__ == "__main__":
    mailadm_db = DB(get_db_path())
    admbot_db_path = get_admbot_db_path()
    main(mailadm_db, admbot_db_path)
