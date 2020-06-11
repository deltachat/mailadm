"""
Parsing the mailadm config file, and making sections available.

for a example mailadm.config file, see test_config.py
"""

import iniconfig
import random
import sys


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

    def get_token_config_from_name(self, name):
        for mc in self.get_token_configs():
            if mc.name == name:
                return mc

    def get_token_config_from_token(self, token):
        for mc in self.get_token_configs():
            if mc.token == token:
                return mc

    def get_token_config_from_email(self, email):
        for mc in self.get_token_configs():
            if email.endswith("@" + self.sysconfig.mail_domain) and email.startswith(mc.prefix):
                return mc

    def get_token_configs(self):
        for section in self.cfg.sections:
            if section.startswith("token:"):
                kwargs = self._parse_token_section(section)
                yield TokenConfig(self.sysconfig, **kwargs)

    def _bailout(self, message):
        raise InvalidConfig("{} in file {!r}".format(message, self.path))

    def _parse_token_section(self, section):
        assert section.startswith("token:"), section
        kwargs = {'name': section[6:].strip()}

        def error(message):
            self._bailout("{} in section {!r}".format(message, kwargs['name']))

        for name, val in self.cfg.sections[section].items():
            if name == "expiry":
                try:
                    parse_expiry_code(val)
                except ValueError:
                    error("invalid expiry code {!r}".format(val))
            elif name == "prefix":
                pass
            elif name == "token":
                if len(val) < 15:
                    error("token too short {!r}".format(val))
            else:
                error("invalid name {!r}".format(val))
            kwargs[name] = val
        return kwargs

    def _parse_sysconfig(self):
        data = self.cfg.sections.get("sysconfig")
        if data is None:
            self._bailout("no 'sysconfig' section")
        try:
            return SysConfig(**dict(data))
        except TypeError as err:
            self._bailout("invalid sysconfig: {}".format(err))


class SysConfig:
    def __init__(self,
            path_mailadm_db,         # path to mailadm database (source of truth)
            mail_domain,             # on which mail addresses are created
            web_endpoint,            # how the web endpoint is externally visible
            path_dovecot_users,      # path to dovecot users file
            path_virtual_mailboxes,  # postfix virtual mailbox alias file
            path_vmaildir,           # where dovecot virtual mail directory resides
            dovecot_uid=1000,        # uid of the dovecot process
            dovecot_gid=1000,):      # gid of the dovecot process
        self.__dict__.update(locals())
        del self.self


class TokenConfig:
    def __init__(self, sysconfig, name, token, expiry, prefix):
        self.sysconfig = sysconfig
        self.name = name
        self.token = token
        self.expiry = expiry
        self.prefix = prefix

    def get_maxdays(self):
        return parse_expiry_code(self.expiry) / (24 * 60 * 60)

    def make_email_address(self, username=None):
        if username is None:
            username = "{}{}".format(
                self.prefix,
                "".join(random.choice(TMP_EMAIL_CHARS) for i in range(TMP_EMAIL_LEN))
            )
        elif self.prefix:
            raise ValueError("can not set username")
        assert "@" not in username
        return "{}@{}".format(username, self.sysconfig.mail_domain)

    def make_controller(self):
        from .mailctl import MailController
        return MailController(mail_config=self)

    def get_web_url(self):
        return ("{web}?t={token}&n={name}".format(
                web=self.sysconfig.web_endpoint, token=self.token, name=self.name))

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
