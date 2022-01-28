import requests as r


class MailcowConnection:
    """Class to manage requests to the mailcow instance.

    :param config: the mailadm config
    """
    def __init__(self, config):
        self.config = config
        self.auth = {"X-API-Key": config.mailcow_token}

    def add_user_mailcow(self, addr, password, quota=1024):
        """HTTP Request to add a user to the mailcow instance.

        :param addr: the email address of the new account
        :param password: the password  of the new account
        :param quota: the maximum mailbox storage in MB
        """
        url = self.config.mailcow_endpoint + "add/mailbox"
        payload = {
            "local_part": addr.split("@")[0],
            "domain": addr.split("@")[1],
            "quota": quota,
            "password": password,
            "password2": password,
            "active": True,
            "force_pw_update": False,
            "tls_enforce_in": True,
            "tls_enforce_out": True,
        }
        result = r.post(url, json=payload, headers=self.auth)
        if result.json()[0]["type"] != "success":
            print(result.json())  # debug
        return result

    def del_user_mailcow(self, addr):
        """HTTP Request to delete a user from the mailcow instance.

        :param addr: the email account to be deleted
        """
        url = self.config.mailcow_endpoint + "delete/mailbox"
        return r.post(url, json=[addr], headers=self.auth)

    def get_users(self):
        """HTTP Request to get all mailcow users (not only mailadm-generated ones)."""
        url = self.config.mailcow_endpoint + "get/mailbox/all"
        return r.get(url, headers=self.auth)
