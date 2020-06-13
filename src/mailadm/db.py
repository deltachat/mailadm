import contextlib
import crypt
import base64
import random
import sqlite3
import time
import sys


TMP_EMAIL_CHARS = "2345789acdefghjkmnpqrstuvwxyz"
TMP_EMAIL_LEN = 5


class Connection:
    def __init__(self, sqlconn, sqlpath, config):
        self._sqlconn = sqlconn
        self._sqlpath = sqlpath
        self.config = config

    def log(self, msg):
        print(msg)

    def close(self):
        self._sqlconn.close()

    def commit(self):
        self._sqlconn.commit()

    def rollback(self):
        self._sqlconn.rollback()

    def get_token_list(self):
        q = "SELECT name from tokens"
        c = self._sqlconn.cursor()
        return [x[0] for x in c.execute(q).fetchall()]

    def add_token(self, name, token, expiry, prefix):
        q = "INSERT INTO tokens (name, token, prefix, expiry) VALUES (?, ?, ?, ?)"
        try:
            self._sqlconn.execute(q, (name, token, prefix, expiry))
        except sqlite3.IntegrityError as e:
            raise ValueError(e)
        self.log("added token {!r}".format(name))
        return TokenInfo(self.config, name=name, token=token,
                         prefix=prefix, expiry=expiry, usecount=0)

    def del_token(self, name):
        q = "DELETE FROM tokens WHERE name=?"
        c = self._sqlconn.cursor()
        c.execute(q, (name, ))
        if c.rowcount == 0:
            raise ValueError("token {!r} does not exist".format(name))
        self.log("deleted token {!r}".format(name))

    def get_tokeninfo_by_name(self, name):
        q = TokenInfo._select_token_columns + "WHERE name = ?"
        res = self._sqlconn.execute(q, (name,)).fetchone()
        if res is not None:
            return TokenInfo(self.config, *res)

    def get_tokeninfo_by_token(self, token):
        q = TokenInfo._select_token_columns + "WHERE token=?"
        res = self._sqlconn.execute(q, (token,)).fetchone()
        if res is not None:
            return TokenInfo(self.config, *res)

    def get_tokeninfo_by_addr(self, addr):
        if not addr.endswith(self.config.sysconfig.mail_domain):
            raise ValueError("addr {!r} does not use mail domain {!r}".format(
                             addr, self.config.sysconfig.mail_domain))
        q = TokenInfo._select_token_columns
        for res in self._sqlconn.execute(q).fetchall():
            token_info = TokenInfo(self.config, *res)
            if addr.startswith(token_info.prefix):
                return token_info

    def add_user(self, addr, hash_pw, date, ttl, token_name):
        self._sqlconn.execute("PRAGMA foreign_keys=on;")
        q = "INSERT INTO mailusers (addr, hash_pw, date, ttl, token_name) VALUES (?, ?, ?, ?, ?)"
        try:
            self._sqlconn.execute(q, (addr, hash_pw, date, ttl, token_name))
        except sqlite3.IntegrityError as e:
            raise ValueError("failed to add addr {!r}: {}".format(addr, e))
        self._sqlconn.execute("UPDATE tokens SET usecount = usecount + 1"
                              "  WHERE name=?", (token_name,))

    def del_user(self, addr):
        q = "DELETE FROM mailusers WHERE addr=?"
        c = self._sqlconn.cursor()
        c.execute(q, (addr, ))
        if c.rowcount == 0:
            raise ValueError("addr {!r} does not exist".format(addr))
        self.log("deleted user {!r}".format(addr))

    def get_user_by_addr(self, addr):
        q = UserInfo._select_user_columns + "WHERE addr = ?"
        args = self._sqlconn.execute(q, (addr, )).fetchone()
        return UserInfo(*args)

    def get_expired_users(self, sysdate):
        q = UserInfo._select_user_columns + "WHERE (date + ttl) < ?"
        users = []
        for args in self._sqlconn.execute(q, (sysdate, )).fetchall():
            users.append(UserInfo(*args))
        return users

    def get_user_list(self):
        q = UserInfo._select_user_columns
        return [UserInfo(*args) for args in self._sqlconn.execute(q).fetchall()]

    def add_email_account(self, token_info, addr=None, password=None, tries=1):
        for i in range(tries):
            try:
                return self._add_addr(token_info, addr=addr, password=password)
            except ValueError:
                if i + 1 >= tries:
                    raise

    def _add_addr(self, token_info, addr, password):
        sysconfig = self.config.sysconfig
        if addr is None:
            username = "{}{}".format(
                token_info.prefix,
                "".join(random.choice(TMP_EMAIL_CHARS) for i in range(TMP_EMAIL_LEN))
            )
            assert "@" not in username
            addr = "{}@{}".format(username, sysconfig.mail_domain)
        else:
            if not addr.endswith(sysconfig.mail_domain):
                raise ValueError("email {!r} is not on domain {!r}".format(
                                 addr, sysconfig.mail_domain))

        clear_pw, hash_pw = get_doveadm_pw(password=password)
        self.add_user(addr=addr, hash_pw=hash_pw, date=int(time.time()),
                      ttl=token_info.get_expiry_seconds(), token_name=token_info.name)
        user_info = self.get_user_by_addr(addr)
        self.log("added addr {!r} with token {!r}".format(addr, token_info.name))
        user_info.clear_pw = clear_pw
        return user_info


class DB:
    Connection = Connection

    def __init__(self, sqlpath, config):
        self.sqlpath = sqlpath
        self.config = config
        self.ensure_tables_exist()

    def _get_sqlconn(self, uri):
        return sqlite3.connect(
            uri, timeout=60, isolation_level=None, uri=True)

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

    def get_connection(self, write=False, closing=False):
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
        conn = self.Connection(sqlconn, self.sqlpath, config=self.config)
        if closing:
            conn = contextlib.closing(conn)
        return conn

    def ensure_tables_exist(self):
        if self.sqlpath.exists():
            return
        with contextlib.closing(self.get_connection(write=True)) as conn:
            print("DB: Creating schema", self.sqlpath)
            c = conn._sqlconn.cursor()
            c.execute("""
                CREATE TABLE tokens (
                    name TEXT PRIMARY KEY,
                    token TEXT NOT NULL UNIQUE,
                    expiry TEXT NOT NULL,
                    prefix TEXT,
                    usecount INTEGER default 0
                )
            """)
            c.execute("""
                CREATE TABLE mailusers (
                    addr TEXT PRIMARY KEY,
                    hash_pw TEXT NOT NULL,
                    date INTEGER,
                    ttl INTEGER,
                    token_name TEXT NOT NULL,
                    FOREIGN KEY (token_name) REFERENCES tokens (name)
                )
            """)
            conn.commit()


class TokenInfo:
    _select_token_columns = "SELECT name, token, expiry, prefix, usecount from tokens\n"

    def __init__(self, config, name, token, expiry, prefix, usecount):
        self.config = config
        self.name = name
        self.token = token
        self.expiry = expiry
        self.prefix = prefix
        self.usecount = usecount

    def get_maxdays(self):
        return parse_expiry_code(self.expiry) / (24 * 60 * 60)

    def get_expiry_seconds(self):
        return parse_expiry_code(self.expiry)

    def get_web_url(self):
        return ("{web}?t={token}&n={name}".format(
                web=self.config.sysconfig.web_endpoint, token=self.token, name=self.name))

    def get_qr_uri(self):
        return ("DCACCOUNT:" + self.get_web_url())


class UserInfo:
    _select_user_columns = "SELECT addr, hash_pw, date, ttl, token_name from mailusers\n"

    def __init__(self, addr, hash_pw, date, ttl, token_name):
        self.addr = addr
        self.hash_pw = hash_pw
        self.date = date
        self.ttl = ttl
        self.token_name = token_name


def get_doveadm_pw(password=None):
    if password is None:
        password = gen_password()
    hash_pw = crypt.crypt(password)
    return password, hash_pw


def gen_password():
    with open("/dev/urandom", "rb") as f:
        s = f.read(21)
    return base64.b64encode(s).decode("ascii")[:12]


def parse_expiry_code(code):
    if code == "never":
        return sys.maxsize

    if len(code) < 2:
        raise ValueError("expiry codes are at least 2 characters")
    val = int(code[:-1])
    c = code[-1]
    if c == "w":
        return val * 7 * 24 * 60 * 60
    elif c == "d":
        return val * 24 * 60 * 60
    elif c == "h":
        return val * 60 * 60