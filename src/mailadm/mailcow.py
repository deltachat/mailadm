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
        if type(result.json()) != list or result.json()[0].get("type") != "success":
            raise MailcowError(result.json())

    def del_user_mailcow(self, addr):
        """HTTP Request to delete a user from the mailcow instance.

        :param addr: the email account to be deleted
        """
        url = self.config.mailcow_endpoint + "delete/mailbox"
        result = r.post(url, json=[addr], headers=self.auth)
        json = result.json()
        if not isinstance(json, list) or json[0].get("type" != "success"):
            raise MailcowError(json)

    def get_user(self, addr):
        """HTTP Request to get a specific mailcow user (not only mailadm-generated ones)."""
        url = self.config.mailcow_endpoint + "get/mailbox/" + addr
        result = r.get(url, headers=self.auth)
        json = result.json()
        if json == {}:
            return None
        if type(json) == dict:
            if json.get("type") == "error":
                raise MailcowError(json)
        return MailcowUser(json)

    def get_user_list(self):
        """HTTP Request to get all mailcow users (not only mailadm-generated ones)."""
        url = self.config.mailcow_endpoint + "get/mailbox/all"
        result = r.get(url, headers=self.auth)
        json = result.json()
        if json == {}:
            return []
        if type(json) == dict:
            if json.get("type") == "error":
                raise MailcowError(json)
        return [MailcowUser(user) for user in json]


class MailcowUser(object):
    def __init__(self, json):
        self.addr = json.get("username")
        self.quota = json.get("quota")


class MailcowError(Exception):
    """This is thrown if a Mailcow operation fails."""
