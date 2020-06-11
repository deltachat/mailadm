"""
Parsing the mailadm config file, and making sections available.

for a example mailadm.config file, see test_config.py
"""

import pathlib

import iniconfig
import random
import sys


from .db import DB


sysconfig_names = (
    "path_mailadm_db",         # path to mailadm database (source of truth)
    "mail_domain",             # on which mail addresses are created
    "web_endpoint",            # how the web endpoint is externally visible
    "path_dovecot_users",      # path to dovecot users file
    "path_virtual_mailboxes",  # postfix virtual mailbox alias file
    "path_vmaildir",           # where dovecot virtual mail directory resides
    "dovecot_uid",             # uid of the dovecot process
    "dovecot_gid",             # gid of the dovecot process
)

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

    def add_token(self, name, token, expiry, prefix):
        with self.db.write_connection() as conn:
            conn.add_token(name=name, token=token, expiry=expiry, prefix=prefix)

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

    def _bailout(self, message):
        raise InvalidConfig("{} in file {!r}".format(message, self.path))

    def _parse_sysconfig(self):
        data = self.cfg.sections.get("sysconfig")
        if data is None:
            self._bailout("no 'sysconfig' section")
        try:
            return SysConfig(**dict(data))
        except ValueError as e:
            name = e.args[0]
            self._bailout("invalid sysconfig key: {!r}".format(name))


class SysConfig:
    def __init__(self, **kw):
        for name, val in kw.items():
            if name not in sysconfig_names:
                raise ValueError(name)
            setattr(self, name, str(val))


class TokenConfig:
    def __init__(self, token_info, config):
        self.config = config
        self.info = token_info
        self.sysconfig = config.sysconfig

    def get_maxdays(self):
        return parse_expiry_code(self.expiry) / (24 * 60 * 60)

    def make_email_address(self):
        username = "{}{}".format(
            self.info.prefix,
            "".join(random.choice(TMP_EMAIL_CHARS) for i in range(TMP_EMAIL_LEN))
        )
        assert "@" not in username
        return "{}@{}".format(username, self.sysconfig.mail_domain)

    def make_controller(self):
        from .mailctl import MailController
        return MailController(token_config=self)

    def get_web_url(self):
        return ("{web}?t={token}&n={name}".format(
                web=self.sysconfig.web_endpoint, token=self.info.token, name=self.info.name))

    def get_qr_uri(self):
        return ("DCACCOUNT:" + self.get_web_url())


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
