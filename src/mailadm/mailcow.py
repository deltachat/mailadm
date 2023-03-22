from urllib.parse import quote

import requests as r

HTTP_TIMEOUT = 5


class MailcowConnection:
    """Class to manage requests to the mailcow instance.

    :param mailcow_endpoint: the URL to the mailcow API
    :param mailcow_token: the access token to the mailcow API
    """

    def __init__(self, mailcow_endpoint, mailcow_token):
        self.mailcow_endpoint = mailcow_endpoint
        self.auth = {"X-API-Key": mailcow_token}

    def add_user_mailcow(self, addr, password, token, quota=0):
        """HTTP Request to add a user to the mailcow instance.

        :param addr: the email address of the new account
        :param password: the password  of the new account
        :param token: the mailadm token used for account creation
        :param quota: the maximum mailbox storage in MB. default: unlimited
        """
        url = self.mailcow_endpoint + "add/mailbox"
        payload = {
            "local_part": addr.split("@")[0],
            "domain": addr.split("@")[1],
            "quota": quota,
            "password": password,
            "password2": password,
            "active": True,
            "force_pw_update": False,
            "tls_enforce_in": False,
            "tls_enforce_out": False,
            "tags": ["mailadm:" + token],
        }
        result = r.post(url, json=payload, headers=self.auth, timeout=HTTP_TIMEOUT)
        if type(result.json()) != list or result.json()[0].get("type") != "success":
            raise MailcowError(result.json())

    def del_user_mailcow(self, addr):
        """HTTP Request to delete a user from the mailcow instance.

        :param addr: the email account to be deleted
        """
        url = self.mailcow_endpoint + "delete/mailbox"
        result = r.post(url, json=[addr], headers=self.auth, timeout=HTTP_TIMEOUT)
        json = result.json()
        if not isinstance(json, list) or json[0].get("type" != "success"):
            raise MailcowError(json)

    def get_user(self, addr):
        """HTTP Request to get a specific mailcow user (not only mailadm-generated ones)."""
        url = self.mailcow_endpoint + "get/mailbox/" + quote(addr, safe="")
        result = r.get(url, headers=self.auth, timeout=HTTP_TIMEOUT)
        json = result.json()
        if json == {}:
            return None
        if type(json) == dict:
            if json.get("type") == "error":
                raise MailcowError(json)
            return MailcowUser(json)
        # some mailcow versions return all users, even if you only ask for a specific one:
        if type(json) == list:
            for user in [MailcowUser(user) for user in json]:
                if user.addr == addr:
                    return user

    def get_user_list(self):
        """HTTP Request to get all mailcow users (not only mailadm-generated ones)."""
        url = self.mailcow_endpoint + "get/mailbox/all"

        # Using larger timeout here than for other requests,
        # because some mailcow instances may have a large number of users.
        result = r.get(url, headers=self.auth, timeout=30)
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
        self.last_login = json.get("last_imap_login")
        for tag in json.get("tags", []):
            if "mailadm:" in tag:
                self.token = tag.removeprefix("mailadm:")
                break


class MailcowError(Exception):
    """This is thrown if a Mailcow operation fails."""
