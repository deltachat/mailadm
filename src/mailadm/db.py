import contextlib
import logging
import os
import sqlite3
import time
from pathlib import Path

from .conn import Connection


def get_db_path():
    db_path = os.environ.get("MAILADM_DB", "/mailadm/docker-data/mailadm.db")
    try:
        sqlite3.connect(db_path)
    except sqlite3.OperationalError:
        raise RuntimeError("mailadm.db not found: MAILADM_DB not set")
    return Path(db_path)


class DB:
    def __init__(self, path, autoinit=True, debug=False):
        self.path = path
        self.debug = debug
        self.ensure_tables()

    def _get_connection(self, write=False, transaction=False, closing=False):
        # we let the database serialize all writers at connection time
        # to play it very safe (we don't have massive amounts of writes).
        mode = "ro"
        if write:
            mode = "rw"
        if not self.path.exists():
            mode = "rwc"
        uri = "file:%s?mode=%s" % (self.path, mode)
        sqlconn = sqlite3.connect(
            uri,
            timeout=60,
            isolation_level=None if transaction else "DEFERRED",
            uri=True,
        )
        if self.debug:
            sqlconn.set_trace_callback(print)

        # Enable Write-Ahead Logging to avoid readers blocking writers and vice versa.
        if write:
            sqlconn.execute("PRAGMA journal_mode=wal")

        if transaction:
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
        conn = self._get_connection(closing=False, write=True, transaction=True)
        try:
            yield conn
        except Exception:
            conn.rollback()
            conn.close()
            raise
        else:
            conn.commit()
            conn.close()

    def write_connection(self, closing=True):
        return self._get_connection(closing=closing, write=True)

    def read_connection(self, closing=True):
        return self._get_connection(closing=closing, write=False)

    def init_config(self, mail_domain, web_endpoint, mailcow_endpoint, mailcow_token):
        with self.write_transaction() as conn:
            conn.set_config("mail_domain", mail_domain)
            conn.set_config("web_endpoint", web_endpoint)
            conn.set_config("mailcow_endpoint", mailcow_endpoint)
            conn.set_config("mailcow_token", mailcow_token)

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
            logging.info("DB: Creating tables %s", self.path)

            conn.execute(
                """
                CREATE TABLE tokens (
                    name TEXT PRIMARY KEY,
                    token TEXT NOT NULL UNIQUE,
                    expiry TEXT NOT NULL,
                    prefix TEXT,
                    maxuse INTEGER default 50,
                    usecount INTEGER default 0
                )
            """,
            )
            conn.execute(
                """
                CREATE TABLE users (
                    addr TEXT PRIMARY KEY,
                    date INTEGER,
                    ttl INTEGER,
                    token_name TEXT NOT NULL,
                    FOREIGN KEY (token_name) REFERENCES tokens (name)
                )
            """,
            )
            conn.execute(
                """
                CREATE TABLE config (
                    name TEXT PRIMARY KEY,
                    value TEXT
                )
            """,
            )
            conn.set_config("dbversion", self.CURRENT_DBVERSION)
