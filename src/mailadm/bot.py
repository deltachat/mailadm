import mimetypes
import sys
import sqlite3
import time
import logging

import deltachat
from deltachat import account_hookimpl
from deltachat.capi import lib as dclib
from mailadm.db import DB, get_db_path
from mailadm.commands import add_user, add_token, list_tokens, qr_from_token, prune
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
        logging.info("process_incoming_message: %s", message.text)
        if not self.is_admin_group_message(message):
            chat = message.create_chat()
            if chat.id == self.admingrpid:
                return  # the reply is handled by is_admin_group_message() already
            elif chat.is_group():
                if message.get_sender_contact() not in self.admingroup.get_contacts():
                    logging.info("%s added me to a group, I'm leaving it.",
                                 message.get_sender_contact().addr)
                    chat.send_text("Sorry, you can not contact me in a group chat. Please use a 1:1"
                                   " chat.")
                    chat.remove_contact(self.account.get_self_contact())   # leave group
                elif message.quote:  # reply to user
                    if message.quote.get_sender_contact().addr == self.account.get_config("addr"):
                        recipient = message.quote.override_sender_name
                        logging.info("I'm forwarding the admin reply to the support user %s.",
                                     recipient)
                        chat = self.account.create_chat(recipient)
                        chat.send_msg(message)
                else:
                    logging.info("ignoring message, it's just admins discussing in a support group")
            elif message.text[0] == "/":
                logging.info("command was not supplied in a group, let alone the admin group.")
                chat.send_text("Sorry, I only take commands from the admin group.")
            else:
                logging.info("forwarding the message to a support group.")
                support_user = message.get_sender_contact().addr
                admins = self.admingroup.get_contacts()
                admins.remove(self.account.get_self_contact())
                group_name = support_user + " support group"
                for chat in self.account.get_chats():
                    if chat.get_name() == group_name:
                        supportgroup = chat
                        break
                else:
                    logging.info("creating new support group: '%s'", group_name)
                    supportgroup = self.account.create_group_chat(group_name, admins)
                    supportgroup.set_profile_image("assets/avatar.jpg")
                message.set_override_sender_name(support_user)
                supportgroup.send_msg(message)
            return
        logging.info("%s seems to be a valid message.", message.text)

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
                    logging.info("%s is not allowed to give commands to mailadm.",
                          command.get_sender_contact())
            elif command.chat.is_protected() and not command.is_encrypted():
                sender = command.get_sender_contact().addr
                logging.warning("The bot doesn't trust %s, please re-add them to admin group" %
                                (sender,))
                self.reply("I didn't see %s being added to this group - can someone who verified "
                           "them re-add them?" % (sender,), reply_to=command)
                return False
            else:
                logging.info("The admin group is broken. Try `mailadm setup-bot`. Group ID: %s",
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
    try:
        ac = deltachat.Account(admbot_db_path)
        with mailadm_db.read_connection() as conn:
            if "admingrpid" not in [item[0] for item in conn.get_config_items()]:
                # the file=sys.stderr seems to be necessary so the output is shown in `docker logs`
                print("To complete the mailadm setup, please run: mailadm setup-bot",
                      file=sys.stderr)
                os._exit(1)
            displayname = conn.config.mail_domain + " administration"
        ac.set_avatar("assets/avatar.jpg")
        ac.run_account(account_plugins=[AdmBot(mailadm_db, ac)], show_ffi=True)
        ac.set_config("mvbox_move", "1")
        ac.set_config("displayname", displayname)
        while 1:
            for logmsg in prune(mailadm_db).get("message"):
                logging.info("%s", logmsg)
            for second in range(0, 600):
                if not ac._event_thread.is_alive():
                    logging.error("dc core event thread died, exiting now")
                    os._exit(1)
                time.sleep(1)
    except Exception:
        logging.exception("bot received an unexpected error, exiting now")
        os._exit(1)


if __name__ == "__main__":
    mailadm_db = DB(get_db_path())
    admbot_db_path = get_admbot_db_path()
    main(mailadm_db, admbot_db_path)
