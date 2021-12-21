from .conn import Config


class MailcowConnection:
    """Class to manage requests to the mailcow instance.

    :param config: the mailadm config
    """
    def __init__(self, config: Config):
        self.config = config

    def add_user_mailcow(self, addr, password):
        """HTTP Request to add a user to the mailcow instance.

        :param addr: the email address of the new account
        :param password: the password  of the new account
        """

    def del_user_mailcow(self, addr):
        """HTTP Request to delete a user from the mailcow instance.

        :param addr: the email account to be deleted
        """
