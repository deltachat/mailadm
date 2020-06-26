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


# if MAILADM_CFG is not set this location is consulted
MAILADM_ETC_CONFIG = "/etc/mailadm/mailadm.cfg"


class InvalidConfig(ValueError):
    """ raised when something is invalid about the init config file. """


class Config:
    def __init__(self, path):
        self.path = path
        self.cfg = iniconfig.IniConfig(str(self.path))
        self.sysconfig = self._parse_sysconfig()
        self.db = DB(self.sysconfig.path_mailadm_db, config=self)

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
        return pathlib.Path(entry.pw_dir)

    @property
    def path_mailadm_db(self):
        entry = pwd.getpwnam("mailadm")
        return pathlib.Path(entry.pw_dir).joinpath("mailadm.db")

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


def get_cfg():
    config_fn = os.environ.get("MAILADM_CFG")
    if config_fn is None:
        config_fn = MAILADM_ETC_CONFIG
        if not os.path.exists(config_fn):
            raise RuntimeError("mailadm.cfg not found: MAILADM_CFG not set "
                               "and {!r} does not exist".format(config_fn))
    else:
        if not os.path.exists(config_fn):
            raise RuntimeError("MAILADM_CFG does not exist: '{!r}'".format(config_fn))
    return config_fn


def gen_sysconfig(mailadm_etc, web_endpoint, mail_domain,
                  mailadm_info, vmail_info, localhost_web_port):
    path = pathlib.Path(pkg_resources.resource_filename('mailadm', 'data/sysconfig'))
    assert path.exists()
    mailadm_homedir = pathlib.Path(mailadm_info.pw_dir)
    parts = urllib.parse.urlparse(web_endpoint)
    web_domain = parts.netloc.split(":", 1)[0]
    web_path = parts.path

    targets = [
        "/etc/dovecot/conf.d/auth-mailadm.conf.ext",
        "/etc/dovecot/conf.d/dovecot-sql.conf.ext",
        "/etc/mailadm/mailadm.cfg",
        "/etc/systemd/system/mailadm-web.service",
        "/etc/systemd/system/mailadm-prune.service",
    ]

    for target in targets:
        bn = os.path.basename(target)
        template_fn = path.joinpath(bn)
        content = template_fn.read_text()
        data = content.format(
            mailadm_homedir=mailadm_homedir,
            web_domain=web_domain,
            web_path=web_path,
            web_endpoint=web_endpoint,
            localhost_web_port=localhost_web_port,
            mailadm_cfg=os.path.join(mailadm_etc, "mailadm.cfg"),
            mailadm_user=mailadm_info.pw_name,
            path_mailadm_db=mailadm_homedir.joinpath("mailadm.db"),
            path_virtual_mailboxes=mailadm_homedir.joinpath("virtual_mailboxes"),
            mail_domain=mail_domain,
            vmail_user=vmail_info.pw_name,
            vmail_homedir=vmail_info.pw_dir,
            systemd="/etc/systemd/system",
            dovecot_conf_d="/etc/dovecot/conf.d",
            postfix_maincf="/etc/postfix/main.cf",
            mailadm_home=mailadm_homedir,
            nginx_sites_enabled="/etc/nginx/sites-enabled",
            args=" ".join(sys.argv[1:]),
        )
        yield pathlib.Path(target), data, 0o644
