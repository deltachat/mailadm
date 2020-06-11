import contextlib
import sqlite3
import time


class Connection:
    def __init__(self, sqlconn, sqlpath):
        self._sqlconn = sqlconn
        self._sqlpath = sqlpath

    def close(self):
        self._sqlconn.close()

    def commit(self):
        self._sqlconn.commit()

    def rollback(self):
        self._sqlconn.rollback()

    def get_sysconfig(self):
        from mailadm.config import SysConfig

        q = "SELECT * from sysconfig"
        c = self._sqlconn.cursor()
        d = {}
        for row in c.execute(q).fetchall():
            d[row["name"]] = row["value"]
        return SysConfig(**d)

    def get_token_list(self):
        q = "SELECT name from tokens"
        c = self._sqlconn.cursor()
        return c.execute(q).fetchall()

    def add_token(self, name, token, expiry, prefix):
        q = "INSERT INTO tokens (name, token, prefix, expiry) VALUES (?, ?, ?, ?)"
        self._sqlconn.execute(q, (name, token, prefix, expiry))

    def get_tokeninfo_by_name(self, name):
        q = ("SELECT token, prefix, expiry, usecount from tokens"
             "    WHERE name = ?")
        res = self._sqlconn.execute(q, (name,)).fetchone()
        return TokenInfo(name=name, **res)

    def get_tokeninfo_by_token(self, token):
        q = ("SELECT name, token, prefix, expiry, usecount from tokens"
             "    WHERE token = ?")
        res = self._sqlconn.execute(q, (token,)).fetchone()
        return TokenInfo(**res)


def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d


class Storage:
    Connection = Connection

    def __init__(self, sqlpath):
        self.sqlpath = sqlpath
        self.ensure_tables_exist()

    def _get_sqlconn(self, uri):
        return sqlite3.connect(
            uri, timeout=60, isolation_level=None, uri=True)

    def get_connection(self, closing=True, write=False):
        # we let the database serialize all writers at connection time
        # to play it very safe (we don't have massive amounts of writes).
        mode = "ro"
        if write:
            mode = "rw"
        if not self.sqlpath.exists():
            mode = "rwc"
        uri = "file:%s?mode=%s" % (self.sqlpath, mode)
        sqlconn = self._get_sqlconn(uri)
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
        conn = self.Connection(sqlconn, self.sqlpath)
        sqlconn.row_factory = dict_factory
        if closing:
            return contextlib.closing(conn)
        return conn

    def ensure_tables_exist(self):
        if self.sqlpath.exists():
            return
        with self.get_connection(write=True) as conn:
            print("DB: Creating schema", self.sqlpath)
            c = conn._sqlconn.cursor()
            c.execute("""
                CREATE TABLE tokens (
                    name TEXT PRIMARY KEY,
                    token TEXT NOT NULL,
                    expiry TEXT NOT NULL,
                    prefix TEXT,
                    usecount INTEGER default 0
                )
            """)
            c.execute("""
                CREATE TABLE sysconfig (
                    name TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            """)
            conn.commit()


class TokenInfo:
    def __init__(self, name, token, expiry, prefix, usecount):
        self.name = name
        self.token = token
        self.expiry = expiry
        self.prefix = prefix
        self.usecount = usecount
