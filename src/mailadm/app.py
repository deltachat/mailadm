"""
help gunicorn and other WSGI servers to instantiate a web instance of mailadm
"""
import sys
import os

from .web import create_app_from_db_path
import time
import threading
from .db import get_db_path, DB
from mailadm.commands import prune
from mailadm.bot import main as run_bot
from mailadm.bot import get_admbot_db_path


def prune_loop():
    try:
        db = DB(get_db_path())
        while 1:
            for logmsg in prune(db).get("message"):
                # the file=sys.stderr seems to be necessary so the output is shown in `docker logs`
                print(logmsg, file=sys.stderr)
            time.sleep(600)
    finally:
        print("prune thread died, killing everything now", file=sys.stderr)
        os._exit(1)


def init_threads():
    prunethread = threading.Thread(target=prune_loop, daemon=True, name="prune")
    prunethread.start()
    botthread = threading.Thread(target=run_bot, args=(DB(get_db_path()), get_admbot_db_path()),
                                 daemon=True, name="bot")
    botthread.start()


app = create_app_from_db_path()
