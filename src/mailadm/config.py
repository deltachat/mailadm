"""
Parsing the mailadm config file, and making sections available.

for a example mailadm.config file, see test_config.py
"""

import os
import pwd
import pathlib
import subprocess

import iniconfig


from .db import DB


class InvalidConfig(ValueError):
    """ raised when something is invalid about the init config file. """


class Config:
    def __init__(self, path):
        self.path = path
        self.cfg = iniconfig.IniConfig(str(self.path))
        self.sysconfig = self._parse_sysconfig()
        dbpath = self.sysconfig.path_mailadm_db
        self.db = DB(dbpath, config=self)

    def log(self, *args):
        print(*args)

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
            return SysConfig(log=self.log, **dict(data))
        except KeyError as e:
            name = e.args[0]
            self._bailout("missing sysconfig key: {!r}".format(name))


class SysConfig:
    _names = (
        "path_mailadm_db",         # path to mailadm database (source of truth)
        "mail_domain",             # on which mail addresses are created
        "web_endpoint",            # how the web endpoint is externally visible
        "path_virtual_mailboxes",  # postfix virtual mailbox map
        "vmail_user",              # where dovecot virtual mail directory resides
    )

    def __init__(self, log, **kwargs):
        self.log = log
        for name in self._names:
            if name not in kwargs:
                raise KeyError(name)
            val = str(kwargs[name])
            if "$" in val:
                val = os.path.expandvars(val)
            if name.startswith("path_"):
                val = pathlib.Path(val)
            setattr(self, name, val)

    @property
    def path_vmaildir(self):
        entry = pwd.getpwnam(self.vmail_user)
        return pathlib.Path(entry[0])

    def gen_sysfiles(self, userlist, dryrun=False):
        postfix_lines = []
        for user_info in userlist:
            postfix_lines.append(user_info.addr + "   " + user_info.addr)

        postfix_data = "\n".join(postfix_lines)

        if dryrun:
            self.log("would write", self.path_virtual_mailboxes)
            return

        with open(self.path_virtual_mailboxes, "w") as f:
            f.write(postfix_data)
        subprocess.check_call(["postmap", self.path_virtual_mailboxes])
        self.log("wrote", self.path_virtual_mailboxes)
