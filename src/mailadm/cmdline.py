"""
script implementation of
https://github.com/codespeaknet/sysadmin/blob/master/docs/postfix-virtual-domains.rst#add-a-virtual-mailbox

"""

from __future__ import print_function

import os
import time
import sys
import click
from click import style

from .config import Config, InvalidConfig
from . import MAILADM_SYSCONFIG_PATH


option_dryrun = click.option(
    "-n", "--dryrun", is_flag=True,
    help="don't change any files, only show what would be changed.")


@click.command(cls=click.Group, context_settings=dict(help_option_names=["-h", "--help"]))
@click.option("--config", type=click.Path(), envvar="MAILADM_CONFIG",
              help="config file for mailadm")
@click.version_option()
@click.pass_context
def mailadm_main(context, config):
    """e-mail account creation admin tool and web service. """
    if config is None:
        config = MAILADM_SYSCONFIG_PATH
    context.config_path = config


def get_mailadm_config(ctx, show=True):
    config_path = ctx.parent.config_path
    if not os.path.exists(config_path):
        ctx.exit("MAILADM_CONFIG not set, "
                 "--config option missing and no config file found: {}".format(config_path))
    try:
        cfg = Config(config_path)
    except InvalidConfig as e:
        ctx.exit(str(e))

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
              help="expiry eg 1w 3d -- default is 1d")
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

    text = ("Scan with Delta Chat app\n"
            "@{domain} {expiry} {name}").format(
            domain=config.sysconfig.mail_domain, expiry=token_info.expiry, name=token_info.name)
    image = gen_qr(token_info.get_qr_uri(), text)
    fn = "dcaccount-{domain}-{name}.png".format(
        domain=config.sysconfig.mail_domain, name=token_info.name)
    image.save(fn)
    click.secho("{} written for token '{}'".format(fn, token_info.name))


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
                ctx.exit("invalid email address: {}".format(addr))

            token_info = conn.get_tokeninfo_by_addr(addr)
            if token_info is None:
                ctx.exit("could not determine token for addr: {!r}".format(addr))
        else:
            token_info = conn.get_tokeninfo_by_name(token)
            if token_info is None:
                ctx.exit("token does not exist: {!r}".format(token))
        try:
            conn.add_email_account(token_info, addr=addr, password=password)
        except ValueError as e:
            ctx.exit("failed to add e-mail account: {}".format(e))

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
def serve(ctx, debug):
    """(debugging-only!) serve http account creation with a default token"""
    from .web import create_app_from_config
    config = get_mailadm_config(ctx)
    app = create_app_from_config(config)
    app.run(debug=debug, host="0.0.0.0", port=3960)


mailadm_main.add_command(list_tokens)
mailadm_main.add_command(add_token)
mailadm_main.add_command(del_token)
mailadm_main.add_command(gen_qr)
mailadm_main.add_command(add_user)
mailadm_main.add_command(del_user)
mailadm_main.add_command(list_users)
mailadm_main.add_command(prune)
mailadm_main.add_command(serve)


if __name__ == "__main__":
    mailadm_main()
