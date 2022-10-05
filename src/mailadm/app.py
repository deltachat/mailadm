"""
help gunicorn and other WSGI servers to instantiate a web instance of mailadm
"""
import sys
import os
import deltachat
from .web import create_app_from_db_path
import time
import threading
from .db import get_db_path, DB
from mailadm.commands import prune, warn_expiring_users
from mailadm.bot import main as bot_loop
from mailadm.bot import get_admbot_db_path, run_bot


def prune_loop(ac: deltachat.Account):
    db = DB(get_db_path())
    # how to shut down admbot account in the end?
    while 1:
        warn_expiring_users(db, ac)
        for logmsg in prune(db).get("message"):
            # the file=sys.stderr seems to be necessary so the output is shown in `docker logs`
            print(logmsg, file=sys.stderr)
        time.sleep(600)


def watcher():
    running = 2
    while running == 2:
        running = 0
        threads = threading.enumerate()
        if "prune" in [t.getName() for t in threads]:
            running += 1
        else:
            print("prune thread died, killing everything now", file=sys.stderr)
        if "bot" in [t.getName() for t in threads]:
            running += 1
        else:
            print("bot thread died, killing everything now", file=sys.stderr)
    else:
        os._exit(1)


def init_threads():
    ac = run_bot(DB(get_db_path()), get_admbot_db_path())
    prunethread = threading.Thread(target=prune_loop, args=(ac,), daemon=True, name="prune")
    prunethread.start()
    botthread = threading.Thread(target=bot_loop, args=(ac,), daemon=True, name="bot")
    botthread.start()
    watcherthread = threading.Thread(target=watcher, daemon=True, name="watcher")
    watcherthread.start()


app = create_app_from_db_path()
