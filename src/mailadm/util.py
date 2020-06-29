import sys
import os
import crypt
import random
import time
import pkg_resources
import pathlib
import urllib
import base64

import mailadm


def get_doveadm_pw(password=None):
    if password is None:
        password = gen_password()
    hash_pw = crypt.crypt(password, crypt.METHOD_SHA512)
    return password, "{SHA512-CRYPT}" + hash_pw


def gen_password():
    with open("/dev/urandom", "rb") as f:
        s = f.read(21)
    return base64.b64encode(s).decode("ascii")[:12]


def get_human_readable_id(len=5, chars="2345789acdefghjkmnpqrstuvwxyz"):
    return "".join(random.choice(chars) for i in range(len))


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


def gen_sysconfig(db, mailadm_info, vmail_info, localhost_web_port):
    config = db.get_config()
    path = pathlib.Path(pkg_resources.resource_filename('mailadm', 'data/sysconfig'))
    assert path.exists()
    mailadm_homedir = pathlib.Path(mailadm_info.pw_dir)
    parts = urllib.parse.urlparse(config.web_endpoint)
    web_domain = parts.netloc.split(":", 1)[0]
    web_path = parts.path

    targets = [
        "/etc/dovecot/conf.d/auth-mailadm.conf.ext",
        "/etc/dovecot/conf.d/dovecot-sql.conf.ext",
        "/etc/systemd/system/mailadm-web.service",
        "/etc/systemd/system/mailadm-prune.service",
        "{}/README.txt".format(mailadm_homedir),
    ]

    for target in targets:
        bn = os.path.basename(target)
        template_fn = path.joinpath(bn)
        content = template_fn.read_text()
        data = content.format(
            mailadm_homedir=mailadm_homedir,
            web_domain=web_domain,
            web_path=web_path,
            web_endpoint=config.web_endpoint,
            localhost_web_port=localhost_web_port,
            mailadm_user=mailadm_info.pw_name,
            path_mailadm_db=db.path,
            path_virtual_mailboxes=config.path_virtual_mailboxes,
            mail_domain=config.mail_domain,
            vmail_user=vmail_info.pw_name,
            vmail_homedir=vmail_info.pw_dir,
            systemd="/etc/systemd/system",
            dovecot_conf_d="/etc/dovecot/conf.d",
            postfix_maincf="/etc/postfix/main.cf",
            mailadm_home=mailadm_homedir,
            nginx_sites_enabled="/etc/nginx/sites-enabled",
            args=" ".join(sys.argv[1:]),
        )
        data = "# mailadm-generated version={} time={}\n\n{}".format(
               mailadm.__version__, time.asctime(), data)

        yield pathlib.Path(target), data, 0o644
