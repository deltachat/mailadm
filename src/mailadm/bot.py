from deltachat import account_hookimpl, run_cmdline
from mailadm.db import DB
from mailadm.commands import add_user, add_token, list_tokens
import os


class AdmBot:
    def __init__(self):
        self.db = DB(os.getenv("MAILADM_DB"))
        with self.db.read_connection() as conn:
            config = conn.config()
            self.admingrpid = config.admingrpid

    @account_hookimpl
    def ac_incoming_message(self, command):
        print("process_incoming message:", command)
        if command.text.strip() == "/help":
            command.create_chat()
            text = ("/add-token name expiry prefix token maxuse"
                    "/add-user addr password token"
                    "/list-tokens")
            command.chat.send_text(text)

        elif command.text.strip() == "/add-token":
            if self.check_privileges(command):
                command.create_chat()
                arguments = command.text.split(" ")
                text = add_token(arguments[0], arguments[1], arguments[2], arguments[3], arguments[4])
                command.chat.send_text(text)

        elif command.text.strip() == "/add-user":
            if self.check_privileges(command):
                command.create_chat()
                arguments = command.text.split(" ")
                text = add_user(arguments[0], arguments[1], arguments[2])
                command.chat.send_text(text)

        elif command.text.strip() == "/list-tokens":
            if self.check_privileges(command):
                command.create_chat()
                command.chat.send_text(list_tokens())

        else:
            # unconditionally accept the chat
            command.create_chat()
            addr = command.get_sender_contact().addr
            if command.is_system_message():
                command.chat.send_text("echoing system message from {}:\n{}".format(addr, command))
            else:
                text = command.text
                command.chat.send_text("echoing from {}:\n{}".format(addr, text))

    def check_privileges(self, command):
        """
        Checks whether the incoming message was in the admin group.
        """
        if command.chat.is_group() and self.admingrpid == command.chat.id:
            if command.chat.is_protected() and command.chat.is_encrypted() and int(command.chat.num_contacts) >= 2:
                if command.message.get_sender_contact() in command.chat.get_contacts():
                    return True
                else:
                    print("%s is not allowed to give commands to mailadm." % (command.message.get_sender_contact(),))
            else:
                print("admin chat is broken. Group ID:" + self.admingrpid)
                raise Exception
        else:
            # reply "This command needs to be sent to the admin group"
            return False


def main(argv=None):
    run_cmdline(argv=argv, account_plugins=[AdmBot()])


if __name__ == "__main__":
    main()
