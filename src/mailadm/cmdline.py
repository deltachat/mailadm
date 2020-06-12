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

from .config import Config, gen_password, InvalidConfig
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
    for name in config.get_token_list():
        tc = config.get_tokenconfig_by_name(name)
        dump_token_info(tc)


@click.command()
@click.pass_context
def list_users(ctx):
    """list users """
    config = get_mailadm_config(ctx)
    for user_info in config.get_user_list():
        click.secho("{} [token={}]".format(user_info.addr, user_info.token_name))


def dump_token_info(tc):
    click.echo(style("token:{}".format(tc.info.name), fg="green"))
    click.echo("  prefix = {}".format(tc.info.prefix))
    click.echo("  expiry = {}".format(tc.info.expiry))
    click.echo("  token  = {}".format(tc.info.token))
    click.echo("  " + tc.get_web_url())
    click.echo("  " + tc.get_qr_uri())


@click.command()
@click.argument("name", type=str, required=True)
@click.option("--expiry", type=str, default="1d",
              help="expiry eg 1w 3d -- default is 1d")
@click.option("--prefix", type=str, default="tmp.",
              help="prefix for all e-mail addresses for this token")
@click.option("--token", type=str, default=None, help="the token to be used")
@click.pass_context
def add_token(ctx, name, expiry, prefix, token):
    """add new token for generating new e-mail addresses
    """
    config = get_mailadm_config(ctx)
    if token is None:
        token = expiry + "_" + gen_password()
    info = config.add_token(name=name, token=token, expiry=expiry, prefix=prefix)
    tc = config.get_tokenconfig_by_name(info.name)
    dump_token_info(tc)


@click.command()
@click.argument("name", type=str, required=True)
@click.pass_context
def del_token(ctx, name):
    """remove named token"""
    config = get_mailadm_config(ctx)
    config.del_token(name=name)
    click.secho("token {!r} deleted".format(name))


@click.command()
@click.argument("tokenname", type=str, required=True)
@click.pass_context
def gen_qr(ctx, tokenname):
    """generate qr code image for a token. """
    from .gen_qr import gen_qr

    config = get_mailadm_config(ctx)
    tc = config.get_tokenconfig_by_name(tokenname)

    text = ("Scan with Delta Chat app\n"
            "@{domain} {expiry} {name}").format(
            domain=config.sysconfig.mail_domain, expiry=tc.info.expiry, name=tc.info.name)
    image = gen_qr(tc.get_qr_uri(), text)
    fn = "dcaccount-{domain}-{name}.png".format(
        domain=config.sysconfig.mail_domain, name=tc.info.name)
    image.save(fn)
    click.secho("{} written for token '{}'".format(fn, tc.info.name))


@click.command()
@click.argument("addr", type=str, required=True)
@click.option("--password", type=str, default=None,
              help="if not specified, generate a random password")
@click.option("--token", type=str, default=None,
              help="if not specified, automatically use first matching token")
@click.pass_context
def add_user(ctx, addr, password, token):
    """add user as a mailadm managed account.
    """
    config = get_mailadm_config(ctx)
    if token is None:
        if "@" not in addr:
            ctx.exit("invalid email address: {}".format(addr))

        token_config = config.get_tokenconfig_by_addr(addr)
        if token_config is None:
            ctx.exit("could not determine token for addr: {!r}".format(addr))
    else:
        token_config = config.get_tokenconfig_by_name(token)
        if token_config is None:
            ctx.exit("token does not exist: {!r}".format(token))
    try:
        token_config.add_email_account(addr=addr, password=password, gen_sysfiles=True)
    except ValueError as e:
        ctx.exit("failed to add e-mail account: {}".format(e))


@click.command()
@click.argument("addr", type=str, required=True)
@click.pass_context
def del_user(ctx, addr):
    """remove e-mail address"""
    config = get_mailadm_config(ctx)
    config.del_user(addr=addr)


@click.command()
@option_dryrun
@click.pass_context
def prune(ctx, dryrun):
    """prune expired users from postfix and dovecot configurations """
    config = get_mailadm_config(ctx)
    sysdate = int(time.time())
    expired_users = config.get_expired_users(sysdate)
    if not expired_users:
        click.secho("nothing to prune")
        return

    if dryrun:
        for user_info in expired_users:
            click.secho("{} [{}]".format(user_info.addr, user_info.token_name), fg="red")
    else:
        with config.db.write_connection() as conn:
            for user_info in expired_users:
                conn.delete_user(user_info.addr)
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
