# content of echo_and_quit.py

from deltachat import account_hookimpl, run_cmdline
from db import DB
import mailadm.db
import cmdline
import os


class AdmBot:
    def __init__(self):
        self.db = DB(os.getenv("MAILADM_DB"))
        with self.db.read_connection() as conn:
            config = conn.config()
            self.admingrpid = config.admingrpid

    @account_hookimpl
    def ac_incoming_message(self, command):
        print("process_incoming message", command)
        if command.text.strip() == "/help":
            command.create_chat()
            text = "/add_token name expiry prefix token maxuse\n/add_user addr password token"
            command.chat.send_text(text)

        elif command.text.strip() == "/add-token":
            chat = command.message.chat
            if chat.is_group() and int(self.admingrpid) == chat.id:
                if chat.is_protected() and int(chat.num_contacts) >= 2:
                    command.create_chat()
                    arguments = command.text.split(" ")
                    text = cmdline.add_token(arguments[0], arguments[1], arguments[2], arguments[3], arguments[4])
                    command.chat.send_text(text)

        elif command.text.strip() == "/add-user":
            chat = command.message.chat
            if chat.is_group() and int(self.admingrpid) == chat.id:
                if chat.is_protected() and int(chat.num_contacts) >= 2:
                    command.create_chat()
                    arguments = command.text.split(" ")
                    text = cmdline.add_token(arguments[0], arguments[1], arguments[2])
                    command.chat.send_text(text)
        else:
            # unconditionally accept the chat
            command.create_chat()
            addr = command.get_sender_contact().addr
            if command.is_system_message():
                command.chat.send_text("echoing system message from {}:\n{}".format(addr, command))
            else:
                text = command.text
                command.chat.send_text("echoing from {}:\n{}".format(addr, text))

    @account_hookimpl
    def ac_message_delivered(self, message):
        print("ac_message_delivered", message)


def main(argv=None):
    run_cmdline(argv=argv, account_plugins=[AdmBot()])


if __name__ == "__main__":
    main()
