import time
import sqlite3
import mailadm.util
from .mailcow import MailcowConnection, MailcowError


class DBError(Exception):
    """ error during an operation on the database. """


class TokenExhausted(DBError):
    """ A token has reached its max-use limit. """


class UserNotFound(DBError):
    """ user not found in database. """


class Connection:
    def __init__(self, sqlconn, path, write):
        self._sqlconn = sqlconn
        self.path_mailadm_db = path
        self._write = write

    def log(self, msg):
        print(msg)

    def close(self):
        self._sqlconn.close()

    def commit(self):
        self._sqlconn.commit()

    def rollback(self):
        self._sqlconn.rollback()

    def execute(self, query, params=()):
        cur = self.cursor()
        try:
            cur.execute(query, params)
        except sqlite3.IntegrityError as e:
            raise DBError(e)
        return cur

    def cursor(self):
        return self._sqlconn.cursor()

    #
    # configuration and meta information
    #
    def get_dbversion(self):
        q = "SELECT value from config WHERE name='dbversion'"
        c = self._sqlconn.cursor()
        try:
            return int(c.execute(q).fetchone()[0])
        except sqlite3.OperationalError:
            return None

    @property
    def config(self):
        items = self.get_config_items()
        if items:
            d = dict(items)
            # remove deprecated config keys
            try:
                del d["vmail_user"]
            except KeyError:
                pass
            try:
                del d["path_virtual_mailboxes"]
            except KeyError:
                pass
            return Config(**d)

    def is_initialized(self):
        items = self.get_config_items()
        return len(items) > 1

    def get_config_items(self):
        q = "SELECT name, value from config"
        c = self._sqlconn.cursor()
        try:
            return c.execute(q).fetchall()
        except sqlite3.OperationalError:
            return None

    def set_config(self, name, value):
        ok = ["dbversion", "mail_domain", "web_endpoint", "mailcow_endpoint", "mailcow_token",
              "admingrpid"]
        assert name in ok, name
        q = "INSERT OR REPLACE INTO config (name, value) VALUES (?, ?)"
        self.cursor().execute(q, (name, value)).fetchone()
        return value

    #
    # token management
    #

    def get_token_list(self):
        q = "SELECT name from tokens"
        return [x[0] for x in self.execute(q).fetchall()]

    def add_token(self, name, token, expiry, prefix, maxuse=50):
        q = "INSERT INTO tokens (name, token, prefix, expiry, maxuse) VALUES (?, ?, ?, ?, ?)"
        self.execute(q, (name, token, prefix, expiry, maxuse))
        self.log("added token {!r}".format(name))
        return self.get_tokeninfo_by_name(name)

    def mod_token(self, name, expiry=None, prefix=None, maxuse=None):
        token_info = self.get_tokeninfo_by_name(name)
        expiry = expiry if expiry is not None else token_info.expiry
        maxuse = maxuse if maxuse is not None else token_info.maxuse
        prefix = prefix if prefix is not None else token_info.prefix
        q = "REPLACE INTO tokens (name, token, prefix, expiry, maxuse) VALUES (?, ?, ?, ?, ?)"
        self.execute(q, (name, token_info.token, prefix, expiry, maxuse))
        self.log("modified token {!r}".format(name))
        return self.get_tokeninfo_by_name(name)

    def del_token(self, name):
        q = "DELETE FROM tokens WHERE name=?"
        c = self.cursor()
        c.execute(q, (name, ))
        if c.rowcount == 0:
            raise ValueError("token {!r} does not exist".format(name))
        self.log("deleted token {!r}".format(name))

    def get_tokeninfo_by_name(self, name):
        q = TokenInfo._select_token_columns + "WHERE name = ?"
        res = self.execute(q, (name,)).fetchone()
        if res is not None:
            return TokenInfo(self.config, *res)

    def get_tokeninfo_by_token(self, token):
        q = TokenInfo._select_token_columns + "WHERE token=?"
        res = self.execute(q, (token,)).fetchone()
        if res is not None:
            return TokenInfo(self.config, *res)

    def get_tokeninfo_by_addr(self, addr):
        if not addr.endswith(self.config.mail_domain):
            raise ValueError("addr {!r} does not use mail domain {!r}".format(
                             addr, self.config.mail_domain))
        q = TokenInfo._select_token_columns
        for res in self.execute(q).fetchall():
            token_info = TokenInfo(self.config, *res)
            if addr.startswith(token_info.prefix):
                return token_info

    #
    # user management
    #

    def add_email_account_tries(self, token_info, addr=None, password=None, tries=1):
        """Try to add an email account."""
        for i in range(tries):
            try:
                return self.add_email_account(token_info, addr=addr, password=password)
            except (MailcowError, DBError):
                if i + 1 >= tries:
                    raise

    def add_email_account(self, token_info, addr=None, password=None):
        """Add an email account to the mailcow server & mailadm

        :param token_info: the token which authorizes the new user creation
        :param addr: email address for the new account; randomly generated if omitted
        :param password: password for the new account; randomly generated if omitted
        :return: a UserInfo object with the database information about the new user, plus password
        """
        token_info.check_exhausted()
        if password is None:
            password = mailadm.util.gen_password()
        if addr is None:
            rand_part = mailadm.util.get_human_readable_id()
            username = "{}{}".format(token_info.prefix, rand_part)
            addr = "{}@{}".format(username, self.config.mail_domain)
        else:
            if not addr.endswith(self.config.mail_domain):
                raise ValueError("email {!r} is not on domain {!r}".format(
                    addr, self.config.mail_domain))

        # first check that mailcow doesn't have a user with that name already:
        if self.get_mailcow_connection().get_user(addr):
            raise MailcowError("account does already exist")

        self.add_user_db(addr=addr, date=int(time.time()),
                         ttl=token_info.get_expiry_seconds(), token_name=token_info.name)

        self.log("added addr {!r} with token {!r}".format(addr, token_info.name))

        user_info = self.get_user_by_addr(addr)
        user_info.password = password

        # seems that everything is fine so far, so let's invoke mailcow:
        self.get_mailcow_connection().add_user_mailcow(addr, password, token_info.name)

        return user_info

    def delete_email_account(self, addr):
        """Delete an email account from the mailcow server & mailadm.

        :param addr: the email address of the account which is to be deleted.
        """
        self.get_mailcow_connection().del_user_mailcow(addr)
        self.del_user_db(addr)

    def add_user_db(self, addr, date, ttl, token_name):
        self.execute("PRAGMA foreign_keys=on;")

        q = """INSERT INTO users (addr, date, ttl, token_name)
               VALUES (?, ?, ?, ?)"""
        self.execute(q, (addr, date, ttl, token_name))
        self.execute("UPDATE tokens SET usecount = usecount + 1"
                     "  WHERE name=?", (token_name,))

    def del_user_db(self, addr):
        q = "DELETE FROM users WHERE addr=?"
        c = self.execute(q, (addr, ))
        if c.rowcount == 0:
            raise UserNotFound("addr {!r} does not exist".format(addr))
        self.log("deleted user {!r}".format(addr))

    def get_user_by_addr(self, addr):
        q = UserInfo._select_user_columns + "WHERE addr = ?"
        args = self._sqlconn.execute(q, (addr, )).fetchone()
        return UserInfo(*args)

    def get_expired_users(self, sysdate):
        q = UserInfo._select_user_columns + "WHERE (date + ttl) < ?"
        users = []
        for args in self._sqlconn.execute(q, (sysdate, )).fetchall():
            users.append(UserInfo(*args))
        return users

    def get_users_to_warn(self, sysdate: int) -> [{}]:
        allusers = self.get_user_list()
        users_to_warn = []
        for user in allusers:
            if user.token_name == "created in mailcow":
                continue
            year = 31536000
            month = 2592000
            week = 604800
            day = 86400
            warnmsg = "Your account will expire in {}."
            timeleft = ""
            if user.ttl >= year:
                if user.warned == 0 and user.date + user.ttl < sysdate + month:
                    timeleft = "30 days"
                elif user.warned == 1 and user.date + user.ttl < sysdate + week:
                    timeleft = "7 days"
                elif user.warned == 2 and user.date + user.ttl < sysdate + day:
                    timeleft = "1 day"
            elif user.ttl >= month:
                if user.warned == 0 and user.date + user.ttl < sysdate + week:
                    timeleft = "7 days"
                elif user.warned == 1 and user.date + user.ttl < sysdate + day:
                    timeleft = "1 day"
            elif user.ttl >= week:
                if user.warned == 0 and user.date + user.ttl < sysdate + day:
                    timeleft = "1 day"
            else:
                if user.warned == 0 and user.date + user.ttl < sysdate + user.ttl / 4:
                    if user.ttl > day:
                        timeleft = str(int(user.ttl / 4 / 60 / 60)) + " hours"
                    else:
                        timeleft = str(int(user.ttl / 4 / 60)) + " minutes"
            if timeleft != "":
                users_to_warn.append({"user": user, "message": warnmsg.format(timeleft)})
        return users_to_warn

    def remember_warning(self, user):
        self.execute("UPDATE users SET warned = warned + 1 WHERE addr=?", (user.addr,))

    def get_user_list(self, token=None):
        q = UserInfo._select_user_columns
        args = []
        if token is not None:
            q += "WHERE token_name=?"
            args.append(token)
        dbusers = [UserInfo(*args) for args in self._sqlconn.execute(q, args).fetchall()]
        try:
            mcusers = self.get_mailcow_connection().get_user_list()
            if not token:
                for mcuser in mcusers:
                    if mcuser.addr not in [dbuser.addr for dbuser in dbusers]:
                        dbusers.append(UserInfo(mcuser.addr, 0, 0, "created in mailcow"))
            for dbuser in dbusers:
                if dbuser.addr not in [mcuser.addr for mcuser in mcusers]:
                    dbuser.token_name = "WARNING: does not exist in mailcow"
        except MailcowError as e:
            self.log("Can't check mailcow users: " + str(e))
        return dbusers

    def get_mailcow_connection(self) -> MailcowConnection:
        return MailcowConnection(self.config.mailcow_endpoint, self.config.mailcow_token)


class TokenInfo:
    _select_token_columns = "SELECT name, token, expiry, prefix, maxuse, usecount from tokens\n"

    def __init__(self, config, name, token, expiry, prefix, maxuse, usecount):
        self.config = config
        self.name = name
        self.token = token
        self.expiry = expiry
        self.prefix = prefix
        self.maxuse = maxuse
        self.usecount = usecount

    def get_maxdays(self):
        return mailadm.util.parse_expiry_code(self.expiry) / (24 * 60 * 60)

    def get_expiry_seconds(self):
        return mailadm.util.parse_expiry_code(self.expiry)

    def get_web_url(self):
        return ("{web}?t={token}&n={name}".format(
                web=self.config.web_endpoint, token=self.token, name=self.name))

    def get_qr_uri(self):
        return "DCACCOUNT:" + self.get_web_url()

    def check_exhausted(self):
        """Check if a token can still create email accounts."""
        if self.usecount >= self.maxuse:
            raise TokenExhausted


class UserInfo:
    _select_user_columns = "SELECT addr, date, ttl, token_name, warned from users\n"

    def __init__(self, addr, date, ttl, token_name, warned=0):
        self.addr = addr
        self.date = date
        self.ttl = ttl
        self.token_name = token_name
        self.warned = warned


class Config:
    """The mailadm config.

    :param mail_domain: the domain of the mailserver
    :param web_endpoint: the web endpoint of mailadm's web interface
    :param dbversion: the version of the mailadm database schema
    :param mailcow_endpoint: the URL to the mailcow API
    :param mailcow_token: the token to authenticate with the mailcow API
    :param admingrpid: the ID of the admin group
    """
    def __init__(self, mail_domain, web_endpoint, dbversion, mailcow_endpoint,
                 mailcow_token, admingrpid=None):
        self.mail_domain = mail_domain
        self.web_endpoint = web_endpoint
        self.dbversion = dbversion
        self.mailcow_endpoint = mailcow_endpoint
        self.mailcow_token = mailcow_token
        self.admingrpid = admingrpid
