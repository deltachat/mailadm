"""
Parsing the mailadm config file, and making sections available.

for a example mailadm.config file, see test_config.py
"""

import time
import pathlib
import crypt
import base64
import sqlite3

import iniconfig
import random
import sys


from .db import DB


# character set for creating random email accounts
# we don't use "0o 1l b6" chars to minimize misunderstandings
# when speaking/hearing/writing/reading the password

TMP_EMAIL_CHARS = "2345789acdefghjkmnpqrstuvwxyz"
TMP_EMAIL_LEN = 5


class InvalidConfig(ValueError):
    """ raised when something is invalid about the init config file. """


class Config:
    def __init__(self, path):
        self.path = path
        self.cfg = iniconfig.IniConfig(path)
        self.sysconfig = self._parse_sysconfig()
        dbpath = pathlib.Path(self.sysconfig.path_mailadm_db)
        self.db = DB(dbpath)

    def log(self, msg):
        print(msg)

    def add_token(self, name, token, expiry, prefix):
        with self.db.write_connection() as conn:
            try:
                ti = conn.add_token(name=name, token=token, expiry=expiry, prefix=prefix)
            except sqlite3.IntegrityError as e:
                raise ValueError(e)
            self.log("added token {!r}".format(name))
            return ti

    def del_token(self, name):
        with self.db.write_connection() as conn:
            conn.del_token(name=name)
            conn.commit()
            self.log("deleted token {!r}".format(name))
            return

    def del_user(self, addr):
        with self.db.write_connection() as conn:
            conn.del_user(addr=addr)
            conn.commit()
            self.log("deleted addr {!r}".format(addr))
            return

    def get_token_list(self):
        with self.db.read_connection() as conn:
            return conn.get_token_list()

    def get_user_list(self):
        with self.db.read_connection() as conn:
            return conn.get_user_list()

    def get_tokenconfig_by_token(self, token):
        with self.db.read_connection() as conn:
            token_info = conn.get_tokeninfo_by_token(token)
            if token_info is not None:
                return TokenConfig(token_info, self)

    def get_tokenconfig_by_name(self, name):
        with self.db.read_connection() as conn:
            token_info = conn.get_tokeninfo_by_name(name)
            if token_info is not None:
                return TokenConfig(token_info, self)

    def get_tokenconfig_by_addr(self, addr):
        if not addr.endswith(self.sysconfig.mail_domain):
            raise ValueError("addr {!r} does not use mail domain {!r}".format(
                             addr, self.sysconfig.mail_domain))
        with self.db.read_connection() as conn:
            token_info = conn.get_tokeninfo_by_addr(addr)
            if token_info is not None:
                return TokenConfig(token_info, self)

    def get_expired_users(self, sysdate):
        with self.db.read_connection() as conn:
            return conn.get_expired_users(sysdate)

    def _bailout(self, message):
        raise InvalidConfig("{} in file {!r}".format(message, self.path))

    def make_controller(self):
        from .mailctl import MailController
        return MailController(config=self)

    def _parse_sysconfig(self):
        data = self.cfg.sections.get("sysconfig")
        if data is None:
            self._bailout("no 'sysconfig' section")
        try:
            return SysConfig(**dict(data))
        except KeyError as e:
            name = e.args[0]
            self._bailout("missing sysconfig key: {!r}".format(name))


class SysConfig:
    _names = (
        "path_mailadm_db",         # path to mailadm database (source of truth)
        "mail_domain",             # on which mail addresses are created
        "web_endpoint",            # how the web endpoint is externally visible
        "path_dovecot_users",      # path to dovecot users file
        "path_virtual_mailboxes",  # postfix virtual mailbox alias file
        "path_vmaildir",           # where dovecot virtual mail directory resides
        "dovecot_uid",             # uid of the dovecot process
        "dovecot_gid",             # gid of the dovecot process
    )

    def __init__(self, **kwargs):
        for name in self._names:
            if name not in kwargs:
                raise KeyError(name)
            setattr(self, name, kwargs[name])


class TokenConfig:
    def __init__(self, token_info, config):
        self.config = config
        self.info = token_info
        self.sysconfig = config.sysconfig

    def log(self, msg):
        print(msg)

    def get_maxdays(self):
        return parse_expiry_code(self.expiry) / (24 * 60 * 60)

    def get_expiry_seconds(self):
        return parse_expiry_code(self.info.expiry)

    def add_email_account(self, addr=None, password=None, gen_sysfiles=False, tries=1):
        for i in range(tries):
            try:
                return self._add_addr(addr=addr, password=password, gen_sysfiles=gen_sysfiles)
            except ValueError:
                if i + 1 >= tries:
                    raise

    def _add_addr(self, addr, password, gen_sysfiles):
        if addr is None:
            username = "{}{}".format(
                self.info.prefix,
                "".join(random.choice(TMP_EMAIL_CHARS) for i in range(TMP_EMAIL_LEN))
            )
            assert "@" not in username
            addr = "{}@{}".format(username, self.sysconfig.mail_domain)
        else:
            if not addr.endswith(self.sysconfig.mail_domain):
                raise ValueError("email {!r} is not on domain {!r}".format(
                                 addr, self.sysconfig.mail_domain))

        clear_pw, hash_pw = get_doveadm_pw(password=password)
        with self.config.db.write_connection() as conn:
            conn.add_user(addr=addr, hash_pw=hash_pw, date=int(time.time()),
                          ttl=self.get_expiry_seconds(), token_name=self.info.name)
            user_info = conn.get_user_by_addr(addr)
            if gen_sysfiles:
                self.config.make_controller().gen_sysfiles(conn)
            conn.commit()
        self.log("added addr {!r} with token {!r}".format(addr, self.info.name))
        user_info.clear_pw = clear_pw
        return user_info

    def get_web_url(self):
        return ("{web}?t={token}&n={name}".format(
                web=self.sysconfig.web_endpoint, token=self.info.token, name=self.info.name))

    def get_qr_uri(self):
        return ("DCACCOUNT:" + self.get_web_url())


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
