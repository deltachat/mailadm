"""
User object for modifying virtual_mailbox and dovecot-users
"""

from __future__ import print_function

import os
import base64
import subprocess
import time
import contextlib
from .config import parse_expiry_code


class MailController:
    """ Mail MTA read/write methods for adding/removing users. """
    def __init__(self, mail_config, dryrun=False):
        self.mail_config = mail_config
        self.dryrun = dryrun

    def log(self, *args):
        print(*args)

    @contextlib.contextmanager
    def modify_lines(self, path, pm=False):
        path = str(path)
        self.log("reading", path)
        with open(path) as f:
            content = f.read().rstrip()

        lines = content.split("\n")
        old_lines = lines[:]
        yield lines
        if old_lines == lines:
            self.log("no changes", path)
            return
        content = "\n".join(lines) + "\n"
        self.write_fn(path, content)

        if pm:
            self.postmap(path)

    def write_fn(self, path, content):
        if self.dryrun:
            self.log("would write", path)
            return
        tmp_path = path + "_tmp"
        with open(tmp_path, "w") as f:
            f.write(content)
        self.log("writing", path)
        os.rename(tmp_path, path)

    def find_email_accounts(self, prefix=None):
        path = str(self.mail_config.path_virtual_mailboxes)
        return [line for line in open(path)
                    if line.strip() and (prefix is None or line.startswith(prefix))]

    def remove_accounts(self, account_lines):
        """ remove accounts and return directories which were used by
        these accounts. Note that the returned directories do not neccessarily
        exist as they are only created from the MDA when it delivers mail """
        to_remove = set(map(str.strip, account_lines))
        with self.modify_lines(self.mail_config.path_virtual_mailboxes, pm=True) as lines:
            newlines = []
            for line in lines:
                if line.strip() in to_remove:
                    self.log("remove virtual mailbox:", line)
                    continue
                newlines.append(line)
            lines[:] = newlines

        to_remove_emails = set(x.split()[0] for x in to_remove)

        to_remove_vmail = []
        with self.modify_lines(self.mail_config.path_dovecot_users) as lines:
            newlines = []
            for line in lines:
                email = line.split(":", 1)[0]
                if email in to_remove_emails:
                    self.log("removing dovecot-user:", email)
                    to_remove_vmail.append(email)
                    continue
                newlines.append(line)

            self.log(line)
            lines.append(line)

        to_remove_dirs = []
        for email in to_remove_vmail:
            path = os.path.join(self.mail_config.path_vmaildir, email)
            to_remove_dirs.append((email, path))
        return to_remove_dirs

    def prune_expired_accounts(self, dryrun=False):
        pruned = []

        with self.modify_lines(self.mail_config.path_virtual_mailboxes) as lines:
            newlines = []
            for line in lines:
                if not line.strip():
                    continue
                try:
                    email, timestamp, expiry, origin = line.split()
                except ValueError:
                    newlines.append(line)
                    continue
                if time.time() - float(timestamp) > parse_expiry_code(expiry):
                    pruned.append(email)
                    continue
                newlines.append(line)
            if not dryrun:
                lines[:] = newlines
        return pruned

    def add_email_account(self, email, password=None):
        mc = self.mail_config
        if not email.endswith(mc.domain):
            raise ValueError("email {!r} is not on domain {!r}".format(email, mc.domain))

        now = time.time()
        with self.modify_lines(mc.path_virtual_mailboxes, pm=True) as lines:
            for line in lines:
                if line.startswith(email):
                    raise ValueError("account {!r} already exists".format(email))
            lines.append("{email} {timestamp} {expiry} {origin}".format(
                email=email, timestamp=now, expiry=mc.expiry, origin=mc.name
            ))
        self.log("added {!r} to {}".format(lines[-1], mc.path_virtual_mailboxes))

        clear_password, hash_pw = self.get_doveadm_pw(password=password)
        with self.modify_lines(mc.path_dovecot_users) as lines:
            for line in lines:
                assert not line.startswith(email), line
            line = "{}:{}::::::".format(email, hash_pw)
            self.log("adding line to users")
            self.log(line)
            lines.append(line)

        p = os.path.join(mc.path_vmaildir, email)
        self.log("vmaildir:", p)
        self.log("email:", email)
        self.log("password:", clear_password)
        self.log(email, clear_password)
        return {
            "email": email,
            "password": clear_password,
            "expires": now + parse_expiry_code(mc.expiry)
        }

    def get_doveadm_pw(self, password=None):
        if password is None:
            password = self.gen_password()
        hash_pw = subprocess.check_output(
            ["/usr/bin/doveadm", "pw", "-s", "SHA512-CRYPT", "-p", password])
        return password, hash_pw.decode("ascii").strip()

    def gen_password(self):
        with open("/dev/urandom", "rb") as f:
            s = f.read(21)
        return base64.b64encode(s).decode("ascii")[:12]

    def postmap(self, path):
        print("postmap", path)
        if not self.dryrun:
            subprocess.check_call(["/usr/sbin/postmap", path])

    def reload_services(self):
        if self.dryrun:
            print("would reload services")
        else:
            subprocess.check_call(["/usr/sbin/service", "postfix", "reload"])
            subprocess.check_call(["/usr/sbin/service", "dovecot", "reload"])
