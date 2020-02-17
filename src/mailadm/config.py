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


class Config:
    def __init__(self, path):
        self.cfg = iniconfig.IniConfig(path)

    def get_mail_config_from_name(self, name):
        for mc in self.get_token_configs():
            if mc.name == name:
                return mc

    def get_mail_config_from_token(self, token):
        for mc in self.get_token_configs():
            if mc.token == token:
                return mc

    def get_mail_config_from_email(self, email):
        for mc in self.get_token_configs():
            if email.endswith("@" + mc.domain) and email.startswith(mc.prefix):
                return mc

    def get_token_configs(self):
        for section in self.cfg:
            if section.name.startswith("token:"):
                yield MailConfig(section.name[6:], dict(section.items()))


class MailConfig:
    def __init__(self, name, dic):
        self.name = name
        assert "expiry" in dic, dic
        assert "prefix" in dic, dic
        self.__dict__.update(dic)

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
        return "{}@{}".format(username, self.domain)

    def make_controller(self):
        from .mail import MailController
        return MailController(mail_config=self)


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
