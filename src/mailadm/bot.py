# -*- coding: utf-8 -*-
from simplebot.hookspec import deltabot_hookimpl
from simplebot import DeltaBot
from simplebot.bot import Replies
from simplebot.commands import IncomingCommand
from .db import DB
from deltachat import Chat, Contact, Message
from datetime import datetime, timezone, timedelta
import matplotlib.pyplot as plt
from matplotlib.dates import drange
import socket
import re
import os
import segno
import mailadm
import mailadm.db

version = '1.0.0'
db: DB
dbot: DeltaBot


# ======== Hooks ===============

@deltabot_hookimpl
def deltabot_init(bot: DeltaBot) -> None:
    global db, dbot
    dbot = bot
    db = get_mailadm_db()

    bot.commands.register(name="/info", func=cmd_info)
    bot.commands.register(name="/show", func=cmd_show)


@deltabot_hookimpl
def deltabot_start(bot: DeltaBot, chat = Chat) -> None:
    ## to be deleted
    groups = []
    groups = db.get_groups()
    if groups: 
        for g in groups:
            if g['topic'] == 'Admin group on {}'.format(socket.gethostname()) and g['id'] == int(dbot.get('admgrpid')):
                dbot.logger.info("found Admin group")
            else:
                dbot.logger.warn("no admin group found. removing groups. gid:" + str(g['id']))
                db.remove_group(g['id'])         
    else:
        dbot.logger.warn("no groups found. Creating an admin group")
        chat = dbot.account.create_group_chat("Admin group on {}".format(socket.gethostname()), contacts=[], verified=True)
        db.upsert_group(chat.id, chat.get_name())
        dbot.set("admgrpid",chat.id)
        qr = segno.make(chat.get_join_qr())
        print("\nPlease scan this qr code to join a verified group chat with the bot:\n\n")
        qr.terminal()


# ======== Commands ===============

def cmd_info(command: IncomingCommand, replies: Replies) -> None:
    """Shows info
    """
    if check_priv(command.message, dbot):
        replies.add(text='?? Userbot active on: {} '.format(socket.gethostname()))
        replies.add(text='Available commands:\n/info - show this info \n/refresh - scan logs \n/show <all|active|inactive> <hours default=24>\nshow active or inactive users in the last n hours')


def cmd_show(command: IncomingCommand, replies: Replies) -> None:
    """Shows last login dates for every user seen
    Show active or inactive users in the last n hours
    """
    if check_priv(command.message, dbot):
        usercount = 0
        textlist = "❌ Wrong syntax!\n/show <all|active|inactive> <hours default=24>"
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
                except ValueError as e:
                    replies.add(text="❌ Wrong Syntax!\nParameter must be a number\n/show <all|active|inactive> <hours default=24>")
                    return
                startdate = now - timedelta(hours=parameter)
            if subcommand == "all":
                usercount, outfile = writetofile(2, startdate, now)
                textlist = "Sending a List of all users\n Users counted: {}".format(usercount)
            if subcommand == "active":
                usercount, outfile = writetofile(1, startdate, now)
                textlist = "Sending a List of users who have been seen since {} \n Users counted: {}".format(startdate, usercount)
            if subcommand == "inactive":
                usercount, outfile = writetofile(0, startdate, now)
                textlist = "Sending a List of users who have NOT been seen since {}\n Users counted: {}".format(startdate,  usercount)
            replies.add(filename=outfile)
        replies.add(text=textlist)
        replies.add(filename=create_graph())
    else:
        replies.add("You are not authorzied!")
        

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


def check_priv(message: Message, bot: DeltaBot) -> None:
    groups = db.get_groups()
    if message.chat.is_group():
        for g in groups:
            if g['id'] == message.chat.id:
                dbot.logger.info("recieved message from a registered group")
                if message.chat.is_protected():
                    return True
    dbot.logger.error("recieved message from not registered group, not protected group or 1on1.")
    dbot.logger.error("Sender: {} Chat: {}".format(message.get_sender_contact().addr, message.chat.get_name()))
    return False


def create_graph():
    path = os.path.join(os.path.dirname(dbot.account.db_path), __name__) # Will this work?
    filename = os.path.join(path, 'plot.png') 
    dates, users = []
    dates, users = db.list_usercount()

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