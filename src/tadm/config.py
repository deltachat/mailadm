import iniconfig
import random
from .mail import MailController

# example tadm.config file, see test_config.py

class Config:
    def __init__(self, path):
        self.cfg = iniconfig.IniConfig(path)

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
        self.__dict__.update(dic)

    def make_email_address(self):
        num = random.randint(0, 10000000000000000)
        return "{}{}@{}".format(self.prefix, num, self.domain)

    def make_controller(self):
        return MailController(
            domain = self.domain,
            path_virtual_mailboxes = self.path_virtual_mailboxes,
            path_dovecot_users = self.path_dovecot_users,
            path_vmaildir = self.path_vmaildir,
        )
