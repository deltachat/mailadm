"""
script implementation of
https://github.com/codespeaknet/sysadmin/blob/master/docs/postfix-virtual-domains.rst#add-a-virtual-mailbox

"""

from __future__ import print_function

import os
import sys
import click
from click import style

from .config import Config
from .mailctl import AccountExists
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
    cfg = Config(config_path)
    if show:
        click.secho("using config file: {}".format(cfg.cfg.path), file=sys.stderr)
    return cfg


@click.command()
@click.pass_context
def list_tokens(ctx):
    """list available tokens """
    config = get_mailadm_config(ctx)
    for mc in config.get_token_configs():
        click.echo(style("token:{}".format(mc.name), fg="green"))
        click.echo("  prefix = {}".format(mc.prefix))
        click.echo("  expiry = {}".format(mc.expiry))
        click.echo("  " + mc.get_web_url())
        click.echo("  " + mc.get_qr_uri())


@click.command()
@click.argument("token", type=str, required=True)
@click.pass_context
def gen_qr(ctx, token):
    """generate qr code image for a token. """
    from .gen_qr import gen_qr

    config = get_mailadm_config(ctx)
    mc = config.get_token_config_from_name(token)

    text = ("Scan with Delta Chat app\n"
            "@{domain} {expiry} {name}").format(
            domain=mc.mail_domain, expiry=mc.expiry, name=mc.name)
    image = gen_qr(mc.get_qr_uri(), text)
    fn = "dcaccount-{domain}-{name}.png".format(domain=mc.mail_domain, name=mc.name)
    image.save(fn)
    print("{} written for token '{}'".format(fn, mc.name))


@click.command()
@click.argument("emailadr", type=str, required=True)
@click.option("--password", type=str, default=None,
              help="if not specified, generate a random password")
@option_dryrun
@click.pass_context
def add_user(ctx, emailadr, password, dryrun):
    """add user to postfix and dovecot configurations
    """
    if "@" not in emailadr:
        ctx.exit("invalid email address: {}".format(emailadr))

    config = get_mailadm_config(ctx)
    mu = config.get_token_config_from_email(emailadr).make_controller()
    try:
        mu.add_email_account(email=emailadr, password=password)
    except AccountExists as e:
        ctx.exit("failed to add e-mail account: {}".format(e))


@click.command()
@option_dryrun
@click.pass_context
def prune(ctx, dryrun):
    """prune expired users from postfix and dovecot configurations """
    config = get_mailadm_config(ctx)
    for mc in config.get_token_configs():
        mu = mc.make_controller()
        for email in mu.prune_expired_accounts(dryrun=dryrun):
            click.secho(email, fg="red")


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
mailadm_main.add_command(gen_qr)
mailadm_main.add_command(add_user)
mailadm_main.add_command(prune)
mailadm_main.add_command(serve)


if __name__ == "__main__":
    mailadm_main()
