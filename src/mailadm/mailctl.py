"""
User object for modifying virtual_mailbox and dovecot-users
"""

import os
import subprocess


class MailController:
    """ Mail MTA read/write methods for adding/removing users. """
    def __init__(self, config, dryrun=False):
        self.config = config
        self.dryrun = dryrun

    def log(self, *args):
        print(*args)

    def gen_sysfiles(self, conn):
        # conn should be a write connection so the modification
        # of postfix/dovecot files is atomic
        sysconfig = self.config.sysconfig
        postfix_lines = []
        dovecot_lines = []
        for user_info in conn.get_user_list():
            postfix_lines.append(user_info.addr + "   " + user_info.token_name)
            # {addr}:{hash_pw}:{dovecot_uid}:{dovecot_gid}::{path_vmaildir}::
            dovecot_lines.append(
                ":".join([
                    user_info.addr,
                    user_info.hash_pw,
                    sysconfig.dovecot_uid,
                    sysconfig.dovecot_gid,
                    "",
                    sysconfig.path_vmaildir,
                    "", ""]))

        postfix_data = "\n".join(postfix_lines)
        dovecot_data = "\n".join(dovecot_lines)

        if self.dryrun:
            self.log("would write", sysconfig.path_dovecot_users)
            self.log("would write", sysconfig.path_virtual_mailboxes)
            return

        # write postfix virtual_mailboxes style file
        with open(sysconfig.path_virtual_mailboxes, "w") as f:
            f.write(postfix_data)
        if not self.dryrun:
            subprocess.check_call(["postmap", sysconfig.path_virtual_mailboxes])
        self.log("wrote", sysconfig.path_virtual_mailboxes)

        # write dovecot users file
        tmp_path = sysconfig.path_dovecot_users + "_tmp"
        with open(tmp_path, "w") as f:
            f.write(dovecot_data)
        os.rename(tmp_path, sysconfig.path_dovecot_users)
        self.log("wrote", sysconfig.path_dovecot_users)
