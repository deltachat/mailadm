
import os
import pwd
import contextlib
import sqlite3
import time
from pathlib import Path

from .conn import Connection


def get_db_path(mailadm_user="mailadm"):
    db_path = os.environ.get("MAILADM_DB")
    if db_path is None:
        try:
            entry = pwd.getpwnam(mailadm_user)
        except KeyError:
            raise RuntimeError("mailadm.db not found: MAILADM_DB not set "
                               "and {!r} user does not exist".format(mailadm_user))
        db_path = os.path.join(entry.pw_dir, "mailadm.db")
    return Path(db_path)


class DB:
    def __init__(self, path, autoinit=True):
        self.path = path
        self.ensure_tables()

    def get_connection(self, write=False, closing=False):
        # we let the database serialize all writers at connection time
        # to play it very safe (we don't have massive amounts of writes).
        mode = "ro"
        if write:
            mode = "rw"
        if not self.path.exists():
            mode = "rwc"
        uri = "file:%s?mode=%s" % (self.path, mode)
        sqlconn = sqlite3.connect(uri, timeout=60, isolation_level=None, uri=True)

        if write:
            start_time = time.time()
            while 1:
                try:
                    sqlconn.execute("begin immediate")
                    break
                except sqlite3.OperationalError:
                    # another thread may be writing, give it a chance to finish
                    time.sleep(0.1)
                    if time.time() - start_time > 5:
                        # if it takes this long, something is wrong
                        raise
        conn = Connection(sqlconn, self.path, write=write)
        if closing:
            conn = contextlib.closing(conn)
        return conn

    @contextlib.contextmanager
    def write_transaction(self):
        conn = self.get_connection(closing=False, write=True)
        try:
            yield conn
        except Exception:
            conn.rollback()
            conn.close()
            raise
        else:
            conn.commit()
            conn.close()

    def read_connection(self, closing=True):
        return self.get_connection(closing=closing, write=False)

    def init_config(self, mail_domain, web_endpoint, vmail_user):
        with self.write_transaction() as conn:
            conn.set_config("mail_domain", mail_domain)
            conn.set_config("web_endpoint", web_endpoint)
            conn.set_config("vmail_user", vmail_user)

    def is_initialized(self):
        with self.read_connection() as conn:
            return conn.is_initialized()

    def get_config(self):
        with self.read_connection() as conn:
            return conn.config

    CURRENT_DBVERSION = 1

    def ensure_tables(self):
        with self.read_connection() as conn:
            if conn.get_dbversion():
                return
        with self.write_transaction() as conn:
            print("DB: Creating tables", self.path)

            conn.execute("""
                CREATE TABLE tokens (
                    name TEXT PRIMARY KEY,
                    token TEXT NOT NULL UNIQUE,
                    expiry TEXT NOT NULL,
                    prefix TEXT,
                    maxuse INTEGER default 50,
                    usecount INTEGER default 0
                )
            """)
            conn.execute("""
                CREATE TABLE users (
                    addr TEXT PRIMARY KEY,
                    hash_pw TEXT NOT NULL,
                    homedir TEXT NOT NULL,
                    date INTEGER,
                    ttl INTEGER,
                    token_name TEXT NOT NULL,
                    FOREIGN KEY (token_name) REFERENCES tokens (name)
                )
            """)
            conn.execute("""
                CREATE TABLE config (
                    name TEXT PRIMARY KEY,
                    value TEXT
                )
            """)
            conn.set_config("dbversion", self.CURRENT_DBVERSION)
