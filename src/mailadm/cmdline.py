"""
script implementation of
https://github.com/codespeaknet/sysadmin/blob/master/docs/postfix-virtual-domains.rst#add-a-virtual-mailbox

"""

from __future__ import print_function

import mailadm
import mailadm.db
from .conn import UserInfo
from .mailcow import MailcowError
import mailadm.util
import sys
import click
from click import style
import qrcode

import mailadm.db
import mailadm.commands
import mailadm.util
from .conn import DBError
from .bot import SetupPlugin, get_admbot_db_path

from deltachat import Account, account_hookimpl
from deltachat.events import FFIEventLogger
from deltachat.tracker import ConfigureFailed

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


def create_bot_account(ctx, email: str, password=None) -> (str, str):
    """Make sure that there is a mailcow account to use for the bot.

    This method tries to use the --email and --password CLI arguments. If they are incomplete

    """
    mailadmdb = get_mailadm_db(ctx)
    with mailadmdb.read_connection() as rconn:
        mc = rconn.get_mailcow_connection()
        if not password:
            password = mailadm.util.gen_password()
        try:
            mc.add_user_mailcow(email, password, "bot")
        except MailcowError as e:
            if "object_exists" in str(e):
                ctx.fail("%s already exists; delete the account in mailcow or specify "
                         "credentials with --email and --password." % (email,))
            else:
                raise
        print("New account %s created as bot account." % (email,))
    return email, password


@click.command()
@click.option("--email", type=str, default=None, help="name of email")
@click.option("--password", type=str, default=None, help="name of password")
@click.option("--show-ffi", is_flag=True, help="show low level ffi events")
@click.pass_context
@account_hookimpl
def setup_bot(ctx, email, password, show_ffi):
    """initialize the deltachat bot as an alternative command interface.

    :param ctx: the click object passing the CLI environment
    :param email: the email account the deltachat bot will use for receiving commands
    :param password: the password to the bot's email account
    :param db: the path to the deltachat database of the bot - NOT the path to the mailadm database!
    :param show_ffi: show low level ffi events
    """
    admbot_db = get_admbot_db_path()
    ac = Account(admbot_db)
    if show_ffi:
        ac.add_account_plugin(FFIEventLogger(ac))

    mailadmdb = get_mailadm_db(ctx)
    with mailadmdb.read_connection() as rconn:
        mail_domain = rconn.config.mail_domain
        admingrpid_old = rconn.config.admingrpid

    if not ac.is_configured():
        if email and not password:
            if email.split("@")[1] == mail_domain:
                print("--password not specified, creating account automatically... ")
                email, password = create_bot_account(ctx, email)
            else:
                ctx.fail("You need to provide --password if you want to use an existing account "
                         "for the mailadm bot.")
        elif not email and not password:
            print("--email and --password not specified, creating account automatically... ")
            email = "mailadm@" + mail_domain
            email, password = create_bot_account(ctx, email, password=password)
        elif not email and password:
            ctx.fail("Please also provide --email to use an email account for the mailadm bot.")
    if email:
        ac.set_config("addr", email)
    if password:
        ac.set_config("mail_pw", password)
    ac.set_config("mvbox_move", "0")
    ac.set_config("sentbox_watch", "0")
    ac.set_config("bot", "1")
    configtracker = ac.configure(reconfigure=ac.is_configured())
    try:
        configtracker.wait_finish()
    except ConfigureFailed as e:
        ctx.fail("Authentication Failed: " + str(e))

    ac.start_io()

    chat = ac.create_group_chat("Admin group on {}".format(mail_domain), contacts=[], verified=True)

    setupplugin = SetupPlugin(chat.id)
    ac.add_account_plugin(setupplugin)

    chatinvite = chat.get_join_qr()
    qr = qrcode.QRCode()
    qr.add_data(chatinvite)
    print("\nPlease scan this qr code to join a verified admin group chat:\n\n")
    qr.print_ascii(invert=True)
    print("\nAlternatively, copy-paste this invite to your Delta Chat desktop client:", chatinvite)

    print("\nWaiting until you join the chat")
    sys.stdout.flush()  # flush stdout to actually show the messages above
    setupplugin.member_added.wait()
    setupplugin.message_sent.clear()

    chat.send_text("Welcome to the Admin group on %s! Type /help to see the existing commands." %
                   (mail_domain,))
    print("Welcome message sent.")
    setupplugin.message_sent.wait()
    if admingrpid_old is not None:
        setupplugin.message_sent.clear()
        try:
            oldgroup = ac.get_chat_by_id(int(admingrpid_old))
            oldgroup.send_text("Someone created a new admin group on the command line. "
                               "This one is not valid anymore.")
            setupplugin.message_sent.wait()
        except ValueError as e:
            if "cannot get chat with id=" + admingrpid_old in str(e):
                print("Could not notify the old admin group.")
            else:
                raise
        print("The old admin group was deactivated.")
    sys.stdout.flush()  # flush stdout to actually show the messages above
    ac.shutdown()

    with mailadmdb.write_transaction() as wconn:
        wconn.set_config("admingrpid", chat.id)


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
    click.secho(mailadm.commands.list_tokens(db))


@click.command()
@click.option("--token", type=str, default=None, help="name of token")
@click.pass_context
def list_users(ctx, token):
    """list users """
    db = get_mailadm_db(ctx)
    with db.read_connection() as conn:
        for user_info in conn.get_user_list(token=token):
            click.secho("{} [{}]".format(user_info.addr, user_info.token_name))


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
def add_token(ctx, name, expiry, maxuse, prefix, token):
    """add new token for generating new e-mail addresses
    """
    db = get_mailadm_db(ctx)
    result = mailadm.commands.add_token(db, name, expiry, maxuse, prefix, token)
    if result["status"] == "error":
        ctx.fail(result["message"])
    click.secho(result["message"])


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
    db = get_mailadm_db(ctx)
    result = mailadm.commands.qr_from_token(db, tokenname)
    if result["status"] == "error":
        ctx.fail(result["message"])
    fn = result["filename"]

    click.secho("{} written for token '{}'".format(fn, tokenname))


@click.command()
@click.option("--web-endpoint", type=str, help="external URL for Web API create-account requests",
              envvar="WEB_ENDPOINT", default="https://example.org/new_email", show_default=True)
@click.option("--mail-domain", type=str, help="mail domain for which we create new users",
              envvar="MAIL_DOMAIN", default="example.org", show_default=True)
@click.option("--mailcow-endpoint", type=str, required=True, envvar="MAILCOW_ENDPOINT",
              help="the API endpoint of the mailcow instance")
@click.option("--mailcow-token", type=str, required=True, envvar="MAILCOW_TOKEN",
              help="you can get an API token in the mailcow web interface")
@click.pass_context
def init(ctx, web_endpoint, mail_domain, mailcow_endpoint, mailcow_token):
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
        mailcow_endpoint=mailcow_endpoint,
        mailcow_token=mailcow_token
    )


@click.command()
@click.argument("addr", type=str, required=True)
@click.option("--password", type=str, default=None,
              help="if not specified, generate a random password")
@click.option("--token", type=str, default=None,
              help="name of token. if not specified, automatically use first token matching addr")
@option_dryrun
@click.pass_context
def add_user(ctx, addr, password, token, dryrun):
    """add user as a mailadm managed account.
    """
    db = get_mailadm_db(ctx)
    result = mailadm.commands.add_user(db, token, addr, password, dryrun)
    if result["status"] == "error":
        ctx.fail(result["message"])
    elif result["status"] == "success":
        click.secho("Created %s with password: %s" %
                    (result["message"].addr, result["message"].password))
    elif result["status"] == "dryrun":
        click.secho("Would create %s with password %s" %
                    (result["message"].addr, result["message"].password))


@click.command()
@click.argument("addr", type=str, required=True)
@click.pass_context
def del_user(ctx, addr):
    """remove e-mail address"""
    with get_mailadm_db(ctx).write_transaction() as conn:
        try:
            conn.delete_email_account(addr)
        except (DBError, MailcowError) as e:
            ctx.fail("failed to delete e-mail account {}: {}".format(addr, e))


@click.command()
@option_dryrun
@click.pass_context
def prune(ctx, dryrun):
    """prune expired users from postfix and dovecot configurations """
    result = mailadm.commands.prune(get_mailadm_db(ctx), dryrun=dryrun)
    for msg in result.get("message"):
        if result.get("status") == "error":
            ctx.fail(msg)
        else:
            click.secho(msg)


@click.command()
@click.pass_context
@click.option("--debug", is_flag=True, default=False,
              help="run server in debug mode and don't change any files")
def web(ctx, debug):
    """(debugging-only!) serve http account creation Web API on localhost"""
    from .web import create_app_from_db

    db = get_mailadm_db(ctx)
    app = create_app_from_db(db)
    app.run(debug=debug, host="localhost", port=3691)


@click.command()
@click.pass_context
def migrate_db(ctx):
    db = get_mailadm_db(ctx)
    with db.write_transaction() as conn:
        conn.execute("PRAGMA foreign_keys=on;")

        q = "SELECT addr, date, ttl, token_name from users"
        users = [UserInfo(*args) for args in conn.execute(q).fetchall()]
        q = "DROP TABLE users"
        conn.execute(q)

        conn.execute("""
                    CREATE TABLE users (
                        addr TEXT PRIMARY KEY,
                        date INTEGER,
                        ttl INTEGER,
                        token_name TEXT NOT NULL,
                        FOREIGN KEY (token_name) REFERENCES tokens (name)
                    )
                """)
        for u in users:
            q = """INSERT INTO users (addr, date, ttl, token_name)
                           VALUES (?, ?, ?, ?)"""
            conn.execute(q, (u.addr, u.date, u.ttl, u.token_name))

        q = "DELETE FROM config WHERE name=?"
        conn.execute(q, ("vmail_user",))
        conn.execute(q, ("path_virtual_mailboxes",))


mailadm_main.add_command(setup_bot)
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
mailadm_main.add_command(web)
mailadm_main.add_command(migrate_db)


if __name__ == "__main__":
    mailadm_main()
