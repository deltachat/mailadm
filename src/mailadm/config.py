"""
Parsing the mailadm config file, and making sections available.

for a example mailadm.config file, see test_config.py
"""

import time
import pathlib
import sqlite3

import iniconfig
import random
import sys


from .db import DB


# character set for creating random email accounts
# we don't use "0o 1l b6" chars to minimize misunderstandings
# when speaking/hearing/writing/reading the password


class InvalidConfig(ValueError):
    """ raised when something is invalid about the init config file. """


class Config:
    def __init__(self, path):
        self.path = path
        self.cfg = iniconfig.IniConfig(path)
        self.sysconfig = self._parse_sysconfig()
        dbpath = pathlib.Path(self.sysconfig.path_mailadm_db)
        self.db = DB(dbpath, config=self)

    def log(self, msg):
        print(msg)

    def write_transaction(self):
        return self.db.write_transaction()

    def read_connection(self):
        return self.db.read_connection()

    def _bailout(self, message):
        raise InvalidConfig("{} in file {!r}".format(message, self.path))

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


