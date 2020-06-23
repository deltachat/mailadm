"""
Parsing the mailadm config file, and making sections available.

for a example mailadm.cfg file, see test_config.py
"""

import pkg_resources
import os
import sys
import pwd
import pathlib
import subprocess
import urllib

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

    def gen_sysconfig(self, dest):
        dest = pathlib.Path(dest)
        path = pathlib.Path(pkg_resources.resource_filename('mailadm', 'data/sysconfig'))
        assert path.exists()
        mailadm_homedir = pathlib.Path(pwd.getpwnam("mailadm").pw_dir)
        parts = urllib.parse.urlparse(self.sysconfig.web_endpoint)
        web_domain = parts.netloc.split(":", 1)[0]
        web_path = parts.path
        localhost_mailadm_port = 3961

        if not dest.exists():
            dest.mkdir()

        for template_fn in path.iterdir():
            if template_fn.name.startswith("."):
                continue
            content = template_fn.read_text()
            data = content.format(
                mailadm_homedir=mailadm_homedir,
                web_domain=web_domain,
                web_path=web_path,
                localhost_mailadm_port=localhost_mailadm_port,
                path_mailadm_db=self.sysconfig.path_mailadm_db,
                path_virtual_mailboxes=self.sysconfig.path_virtual_mailboxes,
                mail_domain=self.sysconfig.mail_domain,
                vmail_user=self.sysconfig.vmail_user,
                systemd="/etc/systemd/system",
                dovecot_conf_d="/etc/dovecot/conf.d",
                postfix_maincf="/etc/postfix/main.cf",
                mailadm_home="~mailadm",
                nginx_sites_enabled="/etc/nginx/sites-enabled",
                args = " ".join(sys.argv[1:]),
                input_vmail_user="vmail",
                input_web_endpoint="https://example.org/new_email",
                input_mail_domain="example.org",
            )
            yield dest.joinpath(template_fn.name), data

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
