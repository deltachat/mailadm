"""
script implementation of
https://github.com/codespeaknet/sysadmin/blob/master/docs/postfix-virtual-domains.rst#add-a-virtual-mailbox

"""

from __future__ import print_function

from pathlib import Path
import os
import time
import pwd
import grp
import sys
import click
from click import style

import mailadm
from .config import Config, InvalidConfig, get_cfg


option_dryrun = click.option(
    "-n", "--dryrun", is_flag=True,
    help="don't change any files, only show what would be changed.")


@click.command(cls=click.Group, context_settings=dict(help_option_names=["-h", "--help"]))
@click.option("--config", type=click.Path(), default=None,
              help="config file for mailadm")
@click.version_option()
@click.pass_context
def mailadm_main(context, config):
    """e-mail account creation admin tool and web service. """

    def get_config_path():
        if config is None:
            try:
                return get_cfg()
            except RuntimeError as e:
                context.fail(e.args)
        return config

    context.get_config_path = get_config_path


def get_mailadm_config(ctx, show=False):
    config_path = ctx.parent.get_config_path()
    try:
        cfg = Config(config_path)
    except InvalidConfig as e:
        ctx.fail(str(e))

    if show:
        click.secho("using config file: {}".format(cfg.cfg.path), file=sys.stderr)
    return cfg


@click.command()
@click.pass_context
def list_tokens(ctx):
    """list available tokens """
    config = get_mailadm_config(ctx)
    with config.read_connection() as conn:
        for name in conn.get_token_list():
            token_info = conn.get_tokeninfo_by_name(name)
            dump_token_info(token_info)


@click.command()
@click.option("--token", type=str, default=None, help="name of token")
@click.pass_context
def list_users(ctx, token):
    """list users """
    config = get_mailadm_config(ctx)
    with config.read_connection() as conn:
        for user_info in conn.get_user_list(token=token):
            click.secho("{} [token={}]".format(user_info.addr, user_info.token_name))


def dump_token_info(token_info):
    click.echo(style("token:{}".format(token_info.name), fg="green"))
    click.echo("  prefix = {}".format(token_info.prefix))
    click.echo("  expiry = {}".format(token_info.expiry))
    click.echo("  maxuse = {}".format(token_info.maxuse))
    click.echo("  usecount = {}".format(token_info.usecount))
    click.echo("  token  = {}".format(token_info.token))
    click.echo("  " + token_info.get_web_url())
    click.echo("  " + token_info.get_qr_uri())


@click.command()
@click.argument("name", type=str, required=True)
@click.option("--expiry", type=str, default="1d",
              help="account expiry eg 1w 3d -- default is 1d")
@click.option("--maxuse", type=int, default=50,
              help="maximum number of accounts this token can create")
@click.option("--prefix", type=str, default="tmp.",
              help="prefix for all e-mail addresses for this token")
@click.option("--token", type=str, default=None, help="name of token to be used")
@click.pass_context
def add_token(ctx, name, expiry, prefix, token, maxuse):
    """add new token for generating new e-mail addresses
    """
    from mailadm.db import gen_password

    config = get_mailadm_config(ctx)
    if token is None:
        token = expiry + "_" + gen_password()
    with config.write_transaction() as conn:
        info = conn.add_token(name=name, token=token, expiry=expiry,
                              maxuse=maxuse, prefix=prefix)
        tc = conn.get_tokeninfo_by_name(info.name)
        dump_token_info(tc)


@click.command()
@click.argument("name", type=str, required=True)
@click.pass_context
def del_token(ctx, name):
    """remove named token"""
    config = get_mailadm_config(ctx)
    with config.write_transaction() as conn:
        conn.del_token(name=name)


@click.command()
@click.argument("tokenname", type=str, required=True)
@click.pass_context
def gen_qr(ctx, tokenname):
    """generate qr code image for a token. """
    from .gen_qr import gen_qr

    config = get_mailadm_config(ctx)
    with config.read_connection() as conn:
        token_info = conn.get_tokeninfo_by_name(tokenname)

    if token_info is None:
        ctx.fail("token {!r} does not exist".format(tokenname))

    image = gen_qr(config, token_info)
    fn = "dcaccount-{domain}-{name}.png".format(
        domain=config.sysconfig.mail_domain, name=token_info.name)
    image.save(fn)
    click.secho("{} written for token '{}'".format(fn, token_info.name))


@click.command()
@option_dryrun
@click.option("--web-endpoint", type=str, prompt="external URL for Web API create-account requests",
              default="https://example.org/new_email", show_default="https://example.org/new_email")
@click.option("--mail-domain", type=str, prompt="mail domain for which we create new users",
              default="example.org", show_default="example.org")
@click.pass_context
def gen_sysconfig(ctx, dryrun, web_endpoint, mail_domain):
    """generate pre-configured system configuration files (config/dovecot/postfix/systemd). """

    def get_env(name, default=None):
        try:
            return os.environ[name]
        except KeyError:
            if not default:
                ctx.fail("environment variable {} not set".format(name))
            return default

    mailadm_user = get_env("MAILADM_USER", "mailadm")
    vmail_user = get_env("VMAIL_USER", "vmail")
    localhost_web_port = get_env("LOCALHOST_WEB_PORT", "3961")

    mailadm_info = get_pwinfo(ctx, "mailadm", mailadm_user)
    vmail_info = get_pwinfo(ctx, "vmail", vmail_user)

    group_info = grp.getgrnam(vmail_user)
    if mailadm_user not in group_info.gr_mem:
        ctx.fail("vmail group {!r} does not have mailadm user "
                 "{!r} as member".format(vmail_user, mailadm_user))

    path = Path("sysconfig")
    for fn, data, mode in mailadm.config.gen_sysconfig(
        mailadm_etc=get_env("MAILADM_ETC"),
        mailadm_info=mailadm_info, vmail_info=vmail_info,
        web_endpoint=web_endpoint, mail_domain=mail_domain,
        localhost_web_port=localhost_web_port
    ):
        if dryrun:
            click.secho("")
            click.secho("")
            click.secho("DRY-WRITE: {}".format(str(fn)))
            click.secho("")
            for line in data.strip().splitlines():
                click.secho("    " + line)
        else:
            fn.write_text(data)
            fn.chmod(mode)
            os.chown(str(fn), 0, 0)  # uid root, gid root
            if str(fn.parent) in ("/etc/mailadm", "/var/lib/mailadm"):
                dirmode = 0o775
                dirfn = fn.parent
                dirfn.chmod(dirmode)
                os.chown(str(dirfn), mailadm_info.pw_uid, mailadm_info.pw_gid)
                click.secho("change-perm {} [owner={}, mode={:03o}]".format(
                            dirfn, mailadm_user, dirmode))
            click.secho("wrote {} [mode={:03o}]".format(fn, mode))


def get_pwinfo(ctx, description, username):
    try:
        return pwd.getpwnam(username)
    except KeyError:
        ctx.fail("{} user {!r} does not exist".format(description, username))


@click.command()
@click.argument("addr", type=str, required=True)
@click.option("--password", type=str, default=None,
              help="if not specified, generate a random password")
@click.option("--token", type=str, default=None,
              help="name of token. if not specified, automatically use first token matching addr")
@click.pass_context
def add_user(ctx, addr, password, token):
    """add user as a mailadm managed account.
    """
    config = get_mailadm_config(ctx)
    with config.write_transaction() as conn:
        if token is None:
            if "@" not in addr:
                ctx.fail("invalid email address: {}".format(addr))

            token_info = conn.get_tokeninfo_by_addr(addr)
            if token_info is None:
                ctx.fail("could not determine token for addr: {!r}".format(addr))
        else:
            token_info = conn.get_tokeninfo_by_name(token)
            if token_info is None:
                ctx.fail("token does not exist: {!r}".format(token))
        try:
            conn.add_email_account(token_info, addr=addr, password=password)
        except ValueError as e:
            ctx.fail("failed to add e-mail account: {}".format(e))

        conn.gen_sysfiles()


@click.command()
@click.argument("addr", type=str, required=True)
@click.pass_context
def del_user(ctx, addr):
    """remove e-mail address"""
    config = get_mailadm_config(ctx)
    with config.write_transaction() as conn:
        conn.del_user(addr=addr)


@click.command()
@option_dryrun
@click.pass_context
def prune(ctx, dryrun):
    """prune expired users from postfix and dovecot configurations """
    config = get_mailadm_config(ctx)
    sysdate = int(time.time())
    with config.write_transaction() as conn:
        expired_users = conn.get_expired_users(sysdate)
        if not expired_users:
            click.secho("nothing to prune")
            return

        if dryrun:
            for user_info in expired_users:
                click.secho("{} [{}]".format(user_info.addr, user_info.token_name), fg="red")
        else:
            for user_info in expired_users:
                conn.del_user(user_info.addr)
                click.secho("{} (token {!r})".format(user_info.addr, user_info.token_name))


@click.command()
@click.pass_context
@click.option("--debug", is_flag=True, default=False,
              help="run server in debug mode and don't change any files")
def web(ctx, debug):
    """(debugging-only!) serve http account creation Web API on localhost"""
    from .web import create_app_from_config
    config = get_mailadm_config(ctx)
    app = create_app_from_config(config)
    app.run(debug=debug, host="localhost", port=3961)


mailadm_main.add_command(list_tokens)
mailadm_main.add_command(add_token)
mailadm_main.add_command(del_token)
mailadm_main.add_command(gen_qr)
mailadm_main.add_command(add_user)
mailadm_main.add_command(del_user)
mailadm_main.add_command(list_users)
mailadm_main.add_command(prune)
mailadm_main.add_command(gen_sysconfig)
mailadm_main.add_command(web)


if __name__ == "__main__":
    mailadm_main()
