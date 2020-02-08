import iniconfig
import random
from .mail import MailController

# example tadm.config file, see test_config.py

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
        assert dic["expiry"] in ["1w", "never"], dic["expiry"]
        assert "prefix" in dic, dic
        self.__dict__.update(dic)

    def make_email_address(self):
        num = random.randint(0, 10000000000000000)
        return "{}{}@{}".format(self.prefix, num, self.domain)

    def make_controller(self):
        return MailController(mail_config = self)
