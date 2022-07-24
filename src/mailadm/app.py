"""
help gunicorn and other WSGI servers to instantiate a web instance of mailadm
"""
import sys
import os

from .web import create_app_from_db_path
import time
import threading
from .db import get_db_path, DB
from .mailcow import MailcowError
from .conn import DBError


def prune():
    print("prune thread started", file=sys.stderr)
    db = DB(get_db_path())
    while 1:
        sysdate = int(time.time())
        with db.write_transaction() as conn:
            expired_users = conn.get_expired_users(sysdate)
            if not expired_users:
                print("nothing to prune", file=sys.stderr)
            else:
                for user_info in expired_users:
                    try:
                        conn.delete_email_account(user_info.addr)
                    except (DBError, MailcowError) as e:
                        print("failed to delete e-mail account {}: {}".format(user_info.addr, e),
                              file=sys.stderr)
                        continue
                    print("pruned {} (token {!r})".format(user_info.addr, user_info.token_name),
                          file=sys.stderr)
        time.sleep(10)


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
    prunethread = threading.Thread(target=prune, daemon=True, name="prune")
    prunethread.start()
    watcherthread = threading.Thread(target=watcher, daemon=True, name="watcher")
    watcherthread.start()


app = create_app_from_db_path()
