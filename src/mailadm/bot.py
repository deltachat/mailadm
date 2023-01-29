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
            self.mail_domain = config.mail_domain

    @account_hookimpl
    def ac_incoming_message(self, message: deltachat.Message):
        """This method is called on every incoming message and decides what to do with it."""
        logging.info("new message from %s: %s", message.get_sender_contact().addr, message.text)
        if self.is_admin_group_message(message):
            if message.text.startswith("/"):
                logging.info("%s seems to be a command.", message.text)
                self.handle_command(message)
            else:
                logging.debug("ignoring message, it's just admins discussing in the admin group")
        elif self.is_support_group(message.chat):
            if message.quote:
                if message.quote.get_sender_contact().addr == self.account.get_config("addr"):
                    self.forward_reply_to_support_user(message)
            elif message.text.startswith("/"):
                logging.info("ignoring command, it wasn't given in the admin group")
                message.chat.send_text("Sorry, I only take commands in the admin group.")
            else:
                logging.debug("ignoring message, it's just admins discussing in a support group")
        else:
            chat = message.create_chat()
            if chat.is_protected() and not message.is_encrypted():
                sender = message.get_sender_contact().addr
                logging.warning("The bot doesn't trust %s, please re-add them to the group", sender)
                recovergroup = self.account.create_group_chat("Admin Group Recovery",
                                                              contacts=message.chat.get_contacts())
                recovergroup.send_text("I didn't see %s being added to the admin group - can "
                                       "someone who verified them re-add them to it? Until then, I "
                                       "can't write to the admin group." % (sender,))
            elif chat.is_group():
                logging.info("%s added me to a group, I'm leaving it.",
                             message.get_sender_contact().addr)
                chat.send_text("Sorry, you can not contact me in groups. Please use a 1:1 chat.")
                chat.remove_contact(self.account.get_self_contact())   # leave group
            elif message.text[0:5] == "/help":
                chat.send_text("You can use this chat to talk to the admins.")
            elif message.text[0] == "/":
                logging.info("ignoring command, it wasn't given in the admin group")
                chat.send_text("Sorry, I only take commands in the admin group.")
            else:
                logging.info("forwarding the message to a support group.")
                self.forward_to_support_group(message)

    def is_support_group(self, chat: deltachat.Chat):
        """Checks whether the group was created by the bot."""
        if chat.is_group():
            return chat.get_messages()[0].get_sender_contact() == self.account.get_self_contact()

    def forward_to_support_group(self, message: deltachat.Message):
        """forward a support request to a support group; create one if it doesn't exist yet."""
        support_user = message.get_sender_contact().addr
        admins = self.admingroup.get_contacts()
        admins.remove(self.account.get_self_contact())
        group_name = support_user + " support group"
        for chat in self.account.get_chats():
            if chat.get_name() == group_name:
                support_group = chat
                break
        else:
            logging.info("creating new support group: '%s'", group_name)
            support_group = self.account.create_group_chat(group_name, admins)
            support_group.set_profile_image("assets/avatar.jpg")
        message.set_override_sender_name(support_user)
        support_group.send_msg(message)

    def forward_reply_to_support_user(self, message: deltachat.Message):
        """an admin replied in a support group; forward their reply to the user."""
        try:
            recipient = message.quote.override_sender_name
        except AttributeError:
            logging.debug("ignoring message in support group, no one to forward it to")
        logging.info("I'm forwarding the admin reply to the support user %s.", recipient)
        chat = self.account.create_chat(recipient)
        chat.send_msg(message)

    def is_admin_group_message(self, command: deltachat.Message):
        """Checks whether the incoming message was in the admin group."""
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
                # warning is handled in ac_incoming_message
                return False
            else:
                logging.info("The admin group is broken. Try `mailadm setup-bot`. Group ID: %s",
                      str(self.admingrpid))
                return False
        else:
            return False

    def handle_command(self, message: deltachat.Message):
        """execute the command and reply to the admin."""
        arguments = message.text.split(" ")
        image_path = None

        if arguments[0] == "/add-token":
            text, image_path = self.add_token(arguments)

        elif arguments[0] == "/gen-qr":
            text, image_path = self.gen_qr(arguments)

        elif arguments[0] == "/add-user":
            text = self.add_user(arguments)

        elif arguments[0] == "/list-users":
            text = self.list_users(arguments)

        elif arguments[0] == "/list-tokens":
            text = list_tokens(self.db)

        else:
            text = ("/add-user addr password token\n"
                    "/add-token name expiry maxuse (prefix)\n"
                    "/gen-qr token\n"
                    "/list-users (token)\n"
                    "/list-tokens")

        if image_path:
            msg = deltachat.Message.new_empty(self.account, "image")
            mime_type = mimetypes.guess_type(image_path)[0]
            msg.set_file(image_path, mime_type)
        else:
            msg = deltachat.Message.new_empty(self.account, "text")
        msg.set_text(text)
        msg.quote = message
        sent_id = dclib.dc_send_msg(self.account._dc_context, self.admingroup.id, msg._dc_msg)
        assert sent_id == msg.id

    def add_token(self, arguments: [str]):
        """add a token via bot command"""
        if len(arguments) == 4:
            arguments.append("")  # add empty prefix
        if len(arguments) < 4:
            result = {"status": "error",
                      "message": "Sorry, you need to tell me more precisely what you want. For "
                                 "example:\n\n/add-token oneweek 1w 50\n\nThis would create a token"
                                 " which creates up to 50 accounts which each are valid for one "
                                 "week."}
        else:
            result = add_token(self.db, name=arguments[1], expiry=arguments[2], maxuse=arguments[3],
                               prefix=arguments[4], token=None)
        if result["status"] == "error":
            return "ERROR: " + result.get("message"), None
        text = result.get("message")
        fn = qr_from_token(self.db, arguments[1])["filename"]
        return text, fn

    def gen_qr(self, arguments: [str]):
        """generate a QR code via bot command"""
        if len(arguments) != 2:
            return "Sorry, which token do you want a QR code for?", None
        else:
            return "", qr_from_token(self.db, tokenname=arguments[1]).get("filename")

    def add_user(self, arguments: [str]):
        """add a user via bot command"""
        if len(arguments) < 4:
            try:
                with self.db.read_connection() as conn:
                    token_name = conn.get_token_list()[0]
            except IndexError:
                return "You need to create a token with /add-token first."
            result = {"status": "error",
                      "message": "Sorry, you need to tell me more precisely what you want. For "
                                 "example:\n\n/add-user test@%s p4$$w0rd %s\n\nThis would "
                                 "create a user with the '%s' token and the password "
                                 "'p4$$w0rd'." % (self.mail_domain, token_name, token_name)}
        else:
            result = add_user(self.db, addr=arguments[1], password=arguments[2],
                              token=arguments[3])
        if result.get("status") == "success":
            user = result.get("message")
            return "successfully created %s with password %s" % (user.addr, user.password)
        else:
            return result.get("message")

    def list_users(self, arguments: [str]):
        """list users per bot command"""
        token = arguments[1] if len(arguments) > 1 else None
        with self.db.read_connection() as conn:
            users = conn.get_user_list(token=token)
        lines = ["%s [%s]" % (user.addr, user.token_name) for user in users]
        return "\n".join(lines)


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
        ac.set_config("show_emails", "2")
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
