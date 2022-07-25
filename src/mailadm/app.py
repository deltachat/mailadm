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


def prune_loop():
    print("prune thread started", file=sys.stderr)
    db = DB(get_db_path())
    while 1:
        for logmsg in prune(db).get("message"):
            print(logmsg, file=sys.stderr)
        time.sleep(600)


def watcher():
    print("watcher thread started", file=sys.stderr)
    running = 1
    while running == 1:
        running = 0
        threads = threading.enumerate()
        if "prune" in [t.getName() for t in threads]:
            running += 1
        else:
            print("prune thread died, killing everything now", file=sys.stderr)
    else:
        os._exit(1)


def init_threads():
    prunethread = threading.Thread(target=prune_loop, daemon=True, name="prune")
    prunethread.start()
    watcherthread = threading.Thread(target=watcher, daemon=True, name="watcher")
    watcherthread.start()


app = create_app_from_db_path()
