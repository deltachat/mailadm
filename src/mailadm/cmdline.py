"""
script implementation of
https://github.com/codespeaknet/sysadmin/blob/master/docs/postfix-virtual-domains.rst#add-a-virtual-mailbox

"""

from __future__ import print_function

import os
import time
import pwd
import grp
import sys
import click
from click import style

import mailadm
import mailadm.db
from .conn import DBError
import mailadm.util


option_dryrun = click.option(
    "-n", "--dryrun", is_flag=True,
    help="don't change any files, only show what would be changed.")


@click.command(cls=click.Group, context_settings=dict(help_option_names=["-h", "--help"]))
@click.version_option()
@click.pass_context
def mailadm_main(context):
    """e-mail account creation admin tool and web service. """


def get_mailadm_db(ctx, show=False, fail_missing_config=True):
    try:
        db_path = mailadm.db.get_db_path()
    except RuntimeError as e:
        ctx.fail(e.args)

    try:
        db = mailadm.db.DB(db_path)
    except DBError as e:
        ctx.fail(str(e))

    if show:
        click.secho("using db: {}".format(db_path), file=sys.stderr)
    if fail_missing_config:
        with db.read_connection() as conn:
            if not conn.is_initialized():
                ctx.fail("database not initialized, use 'init' subcommand to do so")
    return db


@click.command()
@click.pass_context
def config(ctx):
    """show and manipulate config settings. """
    db = get_mailadm_db(ctx)
    with db.read_connection() as conn:
        click.secho("** mailadm version: {}".format(mailadm.__version__))
        click.secho("** mailadm database path: {}".format(db.path))
        for name, val in conn.get_config_items():
            click.secho("{:22s} {}".format(name, val))


@click.command()
@click.pass_context
def list_tokens(ctx):
    """list available tokens """
    db = get_mailadm_db(ctx)
    with db.read_connection() as conn:
        for name in conn.get_token_list():
            token_info = conn.get_tokeninfo_by_name(name)
            dump_token_info(token_info)


@click.command()
@click.option("--token", type=str, default=None, help="name of token")
@click.pass_context
def list_users(ctx, token):
    """list users """
    db = get_mailadm_db(ctx)
    with db.read_connection() as conn:
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
    from mailadm.util import get_human_readable_id

    db = get_mailadm_db(ctx)
    if token is None:
        token = expiry + "_" + get_human_readable_id(len=15)
    with db.write_transaction() as conn:
        info = conn.add_token(name=name, token=token, expiry=expiry,
                              maxuse=maxuse, prefix=prefix)
        tc = conn.get_tokeninfo_by_name(info.name)
        dump_token_info(tc)


@click.command()
@click.argument("name", type=str, required=True)
@click.option("--expiry", type=str, default=None,
              help="account expiry eg 1w 3d -- default is to not change")
@click.option("--maxuse", type=int, default=None,
              help="maximum number of accounts this token can create, default is not to change")
@click.option("--prefix", type=str, default=None,
              help="prefix for all e-mail addresses for this token, default is not to change")
@click.pass_context
def mod_token(ctx, name, expiry, prefix, maxuse):
    """modify a token selectively
    """
    db = get_mailadm_db(ctx)

    with db.write_transaction() as conn:
        conn.mod_token(name=name, expiry=expiry, maxuse=maxuse, prefix=prefix)
        tc = conn.get_tokeninfo_by_name(name)
        dump_token_info(tc)


@click.command()
@click.argument("name", type=str, required=True)
@click.pass_context
def del_token(ctx, name):
    """remove named token"""
    db = get_mailadm_db(ctx)
    with db.write_transaction() as conn:
        conn.del_token(name=name)


@click.command()
@click.argument("tokenname", type=str, required=True)
@click.pass_context
def gen_qr(ctx, tokenname):
    """generate qr code image for a token. """
    from .gen_qr import gen_qr

    db = get_mailadm_db(ctx)
    with db.read_connection() as conn:
        token_info = conn.get_tokeninfo_by_name(tokenname)
        config = conn.config

    if token_info is None:
        ctx.fail("token {!r} does not exist".format(tokenname))

    image = gen_qr(config, token_info)
    fn = "dcaccount-{domain}-{name}.png".format(
        domain=config.mail_domain, name=token_info.name)
    image.save(fn)
    click.secho("{} written for token '{}'".format(fn, token_info.name))


@click.command()
@click.option("--web-endpoint", type=str, prompt="external URL for Web API create-account requests",
              default="https://example.org/new_email", show_default="https://example.org/new_email")
@click.option("--mail-domain", type=str, prompt="mail domain for which we create new users",
              default="example.org", show_default="example.org")
@click.option("--vmail-user", type=str, default="vmail",
              help="dovecot virtual mail delivery user")
@click.option("--path-virtual-mailboxes", default=None, type=str,
              help="postfix virtual users map, generated by mailadm")
@click.pass_context
def init(ctx, web_endpoint, mail_domain, vmail_user, path_virtual_mailboxes):
    """(re-)initialize configuration in mailadm database.

    Warnings: init can be called multiple times but if you are doing this to a
    database that already has users and tokens, you might run into trouble,
    depending on what you changed.
    """
    db = get_mailadm_db(ctx, fail_missing_config=False)
    click.secho("initializing database {}".format(db.path))

    db.init_config(
        mail_domain=mail_domain,
        web_endpoint=web_endpoint,
        vmail_user=vmail_user,
    )


@click.command()
@click.option("--localhost-web-port", type=int, default=3961,
              help="localhost port the web app will run on")
@click.option("--mailadm-user", type=str, default="mailadm",
              help="mailadm user which runs mailadm web and purge services")
@option_dryrun
@click.pass_context
def gen_sysconfig(ctx, dryrun, localhost_web_port, mailadm_user):
    """generate pre-configured system configuration files (config/dovecot/postfix/systemd). """

    db = get_mailadm_db(ctx)
    config = db.get_config()

    mailadm_info = get_pwinfo(ctx, "mailadm", mailadm_user)
    vmail_info = get_pwinfo(ctx, "vmail", config.vmail_user)
    group_info = grp.getgrnam(config.vmail_user)

    if mailadm_user not in group_info.gr_mem:
        ctx.fail("vmail group {!r} does not have mailadm user "
                 "{!r} as member".format(config.vmail_user, mailadm_user))

    for fn, data, mode in mailadm.util.gen_sysconfig(
            db, mailadm_info=mailadm_info, vmail_info=vmail_info,
            localhost_web_port=localhost_web_port):
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
            dirfn = fn.parent
            if str(dirfn) == mailadm_info.pw_dir:
                dirmode = 0o775
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
    with get_mailadm_db(ctx).write_transaction() as conn:
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
        except DBError as e:
            ctx.fail("failed to add e-mail account {}: {}".format(addr, e))

        conn.gen_sysfiles()


@click.command()
@click.argument("addr", type=str, required=True)
@click.pass_context
def del_user(ctx, addr):
    """remove e-mail address"""
    with get_mailadm_db(ctx).write_transaction() as conn:
        conn.del_user(addr=addr)


@click.command()
@option_dryrun
@click.pass_context
def prune(ctx, dryrun):
    """prune expired users from postfix and dovecot configurations """
    sysdate = int(time.time())
    with get_mailadm_db(ctx).write_transaction() as conn:
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
    from .web import create_app_from_db

    db = get_mailadm_db(ctx)
    app = create_app_from_db(db)
    app.run(debug=debug, host="localhost", port=3961)


mailadm_main.add_command(init)
mailadm_main.add_command(config)
mailadm_main.add_command(list_tokens)
mailadm_main.add_command(add_token)
mailadm_main.add_command(mod_token)
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
