
import pathlib
import shutil
import pwd
import time
import sqlite3
from pathlib import Path
from .util import get_doveadm_pw, parse_expiry_code
import mailadm.util


class DBError(Exception):
    """ error during an operation on the database. """


class TokenExhausted(DBError):
    """ A token has reached its max-use limit. """


class UserNotFound(DBError):
    """ user not found in database. """


class Connection:
    def __init__(self, sqlconn, path, write):
        self._sqlconn = sqlconn
        self.path_mailadm_db = path
        self._write = write

    def log(self, msg):
        print(msg)

    def close(self):
        self._sqlconn.close()

    def commit(self):
        self._sqlconn.commit()

    def rollback(self):
        self._sqlconn.rollback()

    def execute(self, query, params=()):
        cur = self.cursor()
        try:
            cur.execute(query, params)
        except sqlite3.IntegrityError as e:
            raise DBError(e)
        return cur

    def cursor(self):
        return self._sqlconn.cursor()

    #
    # configuration and meta information
    #
    def get_dbversion(self):
        q = "SELECT value from config WHERE name='dbversion'"
        c = self._sqlconn.cursor()
        try:
            return c.execute(q).fetchone()
        except sqlite3.OperationalError:
            return None

    @property
    def config(self):
        items = self.get_config_items()
        if items:
            d = dict(items)
            d["path_virtual_mailboxes"] = self.path_mailadm_db.parent.joinpath("virtual_mailboxes")
            return Config(**d)

    def is_initialized(self):
        items = self.get_config_items()
        return len(items) > 1

    def get_config_items(self):
        q = "SELECT name, value from config"
        c = self._sqlconn.cursor()
        try:
            return c.execute(q).fetchall()
        except sqlite3.OperationalError:
            return None

    def set_config(self, name, value):
        ok = ["dbversion", "mail_domain", "web_endpoint", "vmail_user", "path_virtual_mailboxes"]
        assert name in ok, name
        q = "INSERT OR REPLACE INTO config (name, value) VALUES (?, ?)"
        self.cursor().execute(q, (name, value)).fetchone()
        return value

    def gen_sysfiles(self, dryrun=False):
        """ generate system files needed by postfix/dovecot for
        recognizing the current users."""
        import subprocess

        if not self._write or self._sqlconn.total_changes == 0:
            raise ValueError("need to be part of write-transaction for proper locking")
        pf_data = "\n".join((user_info.addr + "    " + user_info.addr)
                            for user_info in self.get_user_list())

        if dryrun:
            self.log("would write", self.path_virtual_mailboxes)
            return

        mapfn = self.config.path_virtual_mailboxes
        mapfn.write_text(pf_data)

        subprocess.check_call(["postmap", str(mapfn)])
        self.log("wrote {} len={} bytes".format(mapfn, len(pf_data)))

    #
    # token management
    #

    def get_token_list(self):
        q = "SELECT name from tokens"
        return [x[0] for x in self.execute(q).fetchall()]

    def add_token(self, name, token, expiry, prefix, maxuse=50):
        q = "INSERT INTO tokens (name, token, prefix, expiry, maxuse) VALUES (?, ?, ?, ?, ?)"
        self.execute(q, (name, token, prefix, expiry, maxuse))
        self.log("added token {!r}".format(name))
        return self.get_tokeninfo_by_name(name)

    def del_token(self, name):
        q = "DELETE FROM tokens WHERE name=?"
        c = self.cursor()
        c.execute(q, (name, ))
        if c.rowcount == 0:
            raise ValueError("token {!r} does not exist".format(name))
        self.log("deleted token {!r}".format(name))

    def get_tokeninfo_by_name(self, name):
        q = TokenInfo._select_token_columns + "WHERE name = ?"
        res = self.execute(q, (name,)).fetchone()
        if res is not None:
            return TokenInfo(self.config, *res)

    def get_tokeninfo_by_token(self, token):
        q = TokenInfo._select_token_columns + "WHERE token=?"
        res = self.execute(q, (token,)).fetchone()
        if res is not None:
            return TokenInfo(self.config, *res)

    def get_tokeninfo_by_addr(self, addr):
        if not addr.endswith(self.config.mail_domain):
            raise ValueError("addr {!r} does not use mail domain {!r}".format(
                             addr, self.config.mail_domain))
        q = TokenInfo._select_token_columns
        for res in self.execute(q).fetchall():
            token_info = TokenInfo(self.config, *res)
            if addr.startswith(token_info.prefix):
                return token_info

    #
    # user management
    #

    def add_user(self, addr, hash_pw, date, ttl, token_name):
        self.execute("PRAGMA foreign_keys=on;")

        token = self.get_tokeninfo_by_name(token_name)
        if token and token.usecount >= token.maxuse:
            raise TokenExhausted("token {} is exhausted".format(token_name))

        homedir = self.config.path_vmaildir.joinpath(addr)
        q = """INSERT INTO users (addr, hash_pw, homedir, date, ttl, token_name)
               VALUES (?, ?, ?, ?, ?, ?)"""
        self.execute(q, (addr, hash_pw, str(homedir), date, ttl, token_name))
        self.execute("UPDATE tokens SET usecount = usecount + 1"
                     "  WHERE name=?", (token_name,))

    def del_user(self, addr):
        q = "DELETE FROM users WHERE addr=?"
        c = self.execute(q, (addr, ))
        if c.rowcount == 0:
            raise UserNotFound("addr {!r} does not exist".format(addr))
        path = self.config.get_vmail_user_dir(addr)
        if path.exists():
            shutil.rmtree(str(path))
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

    def get_user_list(self, token=None):
        q = UserInfo._select_user_columns
        args = []
        if token is not None:
            q += "WHERE token_name=?"
            args.append(token)
        return [UserInfo(*args) for args in self._sqlconn.execute(q, args).fetchall()]

    def add_email_account(self, token_info, addr=None, password=None, tries=1):
        for i in range(tries):
            try:
                return self._add_addr(token_info, addr=addr, password=password)
            except (ValueError, DBError):
                if i + 1 >= tries:
                    raise

    def _add_addr(self, token_info, addr, password):
        config = self.config
        if addr is None:
            rand_part = mailadm.util.get_human_readable_id()
            username = "{}{}".format(token_info.prefix, rand_part)
            addr = "{}@{}".format(username, config.mail_domain)
        else:
            if not addr.endswith(config.mail_domain):
                raise ValueError("email {!r} is not on domain {!r}".format(
                                 addr, config.mail_domain))

        clear_pw, hash_pw = get_doveadm_pw(password=password)
        self.add_user(addr=addr, hash_pw=hash_pw, date=int(time.time()),
                      ttl=token_info.get_expiry_seconds(), token_name=token_info.name)
        user_info = self.get_user_by_addr(addr)
        self.log("added addr {!r} with token {!r}".format(addr, token_info.name))
        user_info.clear_pw = clear_pw
        return user_info


class TokenInfo:
    _select_token_columns = "SELECT name, token, expiry, prefix, maxuse, usecount from tokens\n"

    def __init__(self, config, name, token, expiry, prefix, maxuse, usecount):
        self.config = config
        self.name = name
        self.token = token
        self.expiry = expiry
        self.prefix = prefix
        self.maxuse = maxuse
        self.usecount = usecount

    def get_maxdays(self):
        return parse_expiry_code(self.expiry) / (24 * 60 * 60)

    def get_expiry_seconds(self):
        return parse_expiry_code(self.expiry)

    def get_web_url(self):
        return ("{web}?t={token}&n={name}".format(
                web=self.config.web_endpoint, token=self.token, name=self.name))

    def get_qr_uri(self):
        return ("DCACCOUNT:" + self.get_web_url())


class UserInfo:
    _select_user_columns = "SELECT addr, hash_pw, homedir, date, ttl, token_name from users\n"

    def __init__(self, addr, hash_pw, homedir, date, ttl, token_name):
        self.addr = addr
        self.hash_pw = hash_pw
        self.homedir = Path(homedir)
        self.date = date
        self.ttl = ttl
        self.token_name = token_name


class Config:
    def __init__(self, mail_domain, web_endpoint, path_virtual_mailboxes, vmail_user, dbversion):
        self.mail_domain = mail_domain
        self.web_endpoint = web_endpoint
        self.path_virtual_mailboxes = Path(path_virtual_mailboxes)
        self.vmail_user = vmail_user
        self.dbversion = dbversion

    @property
    def path_vmaildir(self):
        entry = pwd.getpwnam(self.vmail_user)
        return pathlib.Path(entry.pw_dir)

    def get_vmail_user_dir(self, user):
        return self.path_vmaildir.joinpath(self.mail_domain, user)
