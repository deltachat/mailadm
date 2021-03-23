# -*- coding: utf-8 -*-
from deltabot import deltabot_hookimpl, DeltaBot, command
from deltabot.bot import Replies
from deltabot.commands import IncomingCommand
from .db import DB
from .conn import DBError
from deltachat import Chat, Contact, Message
from datetime import datetime, timezone, timedelta, date
from timeloop import Timeloop
import time
import matplotlib.pyplot as plt
import socket
import re
import os
import segno
import mailadm
import mailadm.db

version = '1.0.0'
db: DB
dbot: DeltaBot
tl = Timeloop()


# ======== Hooks ===============

@deltabot_hookimpl
def deltabot_init(bot: DeltaBot) -> None:
    global db, dbot
    dbot = bot
    db = get_mailadm_db()

    bot.commands.register(name="/show", func=cmd_show)
    bot.commands.register(name="/notify-expiration", func=notify_expiration)


@deltabot_hookimpl
def deltabot_start(chat: Chat) -> None:
    if  check_priv(dbot, chat):
        dbot.logger.warn("Found Admingroup")
    else:
        dbot.logger.warn("Creating an admin group")
        chat = dbot.account.create_group_chat("Admin group on {}".format(socket.gethostname()), contacts=[], verified=True)
        dbot.set("admgrpid",chat.id)
        qr = segno.make(chat.get_join_qr())
        print("\nPlease scan this qr code to join a verified admin group chat:\n\n")
        qr.terminal()
    

# ======== Commands ===============

def cmd_show(command: IncomingCommand, replies: Replies) -> None:
    """Shows last login dates for every user seen in the parsed log files
    Show active or inactive users in the last n hours
    """
    if check_priv(dbot, command.message.chat):
        usercount = 0
        textlist = """
            ❌ Wrong syntax!\n
            /show <all|active|inactive> <hours default=24>
            """
        text = command.payload
        args = command.payload.split(maxsplit=1)
        if len(args) == 1:
            subcommand = args[0]
            parameter = args[1] if len(args) == 2 else ''
            now = datetime.now().astimezone()
            startdate = now - timedelta(hours=24)
            outfile = ""
            if parameter:
                try:
                    parameter = int(parameter)
                except ValueError:
                    replies.add(text=textlist)
                    return
                startdate = now - timedelta(hours=parameter)
            if subcommand == "all":
                usercount, outfile = writetofile(2, startdate, now)
                textlist = """
                    Sending a List of all users\n Users counted: {}
                    """.format(usercount)
            if subcommand == "active":
                usercount, outfile = writetofile(1, startdate, now)
                textlist = """
                    Sending a List of users who have been seen since {} \n
                    Users counted: {}
                    """.format(startdate, usercount)
            if subcommand == "inactive":
                usercount, outfile = writetofile(0, startdate, now)
                textlist = """
                    Sending a List of users who have NOT been seen since {}\n
                    Users counted: {}
                    """.format(startdate,  usercount)
            replies.add(filename=outfile)
        replies.add(text=textlist)
        replies.add(filename=create_graph())
    else:
        replies.add("You are not authorzied!")
        

@command
@tl.job(interval=timedelta(hours=24))
def notify_expiration(bot: DeltaBot):
    """Send notifications to accounts which will expire soon.
    """
    sysdate = int(time.time())
    with db.read_connection() as conn:
        # get all users which will be expired in a week:
        expiring_users = conn.get_expired_users(sysdate + 604800)
    if not expiring_users:
        bot.logger.info("no one to notify")
        return
    for user_info in expiring_users:
        daysleft = int((user_info.date + user_info.ttl - sysdate) / 86400)
        chat = bot.get_chat(user_info.addr)
        if daysleft == 0:
            chat.send_text("""
                Your account will expire tomorrow - you should create
                a new account and tell your contacts your future
                address.
                """)
        elif daysleft == 6:
            d = date.fromtimestamp(sysdate + 604800).strftime("%B %d")
            chat.send_text("""
                Your account will expire on %s - you should create
                a new account and tell your contacts your future
                address.
                """ % d)
        elif daysleft > 0 and daysleft < 6:
            # Don't notify if daysleft is between 1 and 5
            continue
        bot.logger.info("Notified {} [{}]: {} days left".format(
                user_info.addr,
                user_info.token_name,
                str(daysleft)))


# ======== Utilities ===============

def get_mailadm_db():
    try:
        db_path = mailadm.db.get_db_path()
    except RuntimeError as e:
        print(str(e))

    try:
        db = mailadm.db.DB(db_path)
    except DBError as e:
        print(str(e))


def check_priv(bot: DeltaBot, chat: Chat) -> None:
    if chat.is_group() and int(dbot.get('admgrpid')) == chat.id:
            if chat.is_protected() and int(chat.num_contacts) >= 2:
                return True
    dbot.logger.error("recieved message from wrong or not protected chat.")
    dbot.logger.error("Sender: {}".format(chat.get_sender_contact().addr))
    dbot.logger.error("Chat: {}".format(chat.get_name()))
    dbot.logger.error("Message: {}".format(chat.message.text))
    return False


def create_graph():
    path = os.path.join(os.path.dirname(dbot.account.db_path), __name__)
    filename = os.path.join(path, 'plot.png') 
    dates, users = db.get_usercount()

    plt.plot(dates, users)
    plt.grid(linestyle='-')
    plt.xlabel("Date")
    plt.ylabel("Users")
    plt.savefig(filename)
    return filename


def writetofile(sign, startdate, now):
    usercount = 0
    path = os.path.join(os.path.dirname(dbot.account.db_path), __name__)
    filename = os.path.join(path, 'summary-{}.txt'.format(now))
    dbot.logger.info("saving file to: {}".format(filename))
    with open(filename, 'w') as file:
        if sign == 1: 
            file.write("Users who have been seen since {}".format(startdate))
        if sign == 0: 
            file.write("Users who have NOT been seen since {}".format(startdate))
        for user, timestamp in db.list_mailusers():
            if sign == 2:
                usercount = usercount + 1
                file.writelines("{0:25} {1} \n".format(user, timestamp[:-13]))
            if sign == 1 and startdate < datetime.fromisoformat(timestamp):
                usercount = usercount + 1
                file.writelines("{0:25} {1} \n".format(user, timestamp[:-13]))
            if sign == 0 and startdate > datetime.fromisoformat(timestamp):
                usercount = usercount + 1
                file.writelines("{0:25} {1} \n".format(user, timestamp[:-13]))
        db.store_usercount(now.strftime("%Y-%m-%d"), usercount)
    return usercount, filename
