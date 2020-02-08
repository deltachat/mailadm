"""
script implementation of https://github.com/codespeaknet/sysadmin/blob/master/docs/postfix-virtual-domains.rst#add-a-virtual-mailbox

"""

from __future__ import print_function

DOMAIN = "testrun.org"

import os
import base64
import sys
import subprocess
import contextlib

import iniconfig

from .mail import MailController
from .config import Config

import click
from click import style


@click.command(cls=click.Group, context_settings=dict(help_option_names=["-h", "--help"]))
@click.option("--config", type=click.Path(), envvar="TADM_CONFIG",
              help="config file for tadm")
@click.version_option()
@click.pass_context
def tadm_main(context, config):
    """e-mail account creation admin tool and web service. """
    if config is None:
        config = "/etc/tadm/config.ini"
    context.config_path = config


def get_tadm_config(ctx, show=True):
    config_path = ctx.parent.config_path
    if not os.path.exists(config_path):
        context.exit("TADM_CONFIG not set, "
                     "--config option missing and no config file found: {}".format(config))
    cfg = Config(config_path)
    if show:
        click.secho("using config file: {}".format(cfg.cfg.path), file=sys.stderr)
    return cfg


@click.command()
@click.pass_context
def list_tokens(ctx):
    """list available tokens """
    config = get_tadm_config(ctx)
    for mail_config in config.get_token_configs():
        click.echo(style("token:{}".format(mail_config.name), fg="green"))
        click.echo("  prefix = ".format(mail_config.prefix))
        click.echo("  add_user_url = https://{webdomain}/new_email?t={token}"
            .format(**mail_config.__dict__)
        )


@click.command()
@click.argument("emailadr", type=str, required=True)
@click.option("--password", type=str, default=None,
              help="if not specified, generate a random password")
@click.option("-n", "--dryrun", type=str,
              help="don't change any files, only show what would be changed.")
@click.pass_context
def add_local_user(ctx, emailadr, password, dryrun):
    """add user to postfix and dovecot configurations
    """
    if "@" not in emailadr:
        fail(ctx, "invalid email address: {}".format(msg))

    config = get_tadm_config(ctx)
    mu = config.get_mail_config_from_email(emailadr).make_controller()
    mu.add_email_account(email=emailadr, password=password)



@click.command()
@click.pass_context
@click.option("--debug", is_flag=True, default=False,
              help="run server in debug mode and don't change any files")
def serve(ctx, debug):
    """(debugging-only!) serve http account creation with a default token"""
    from .web import create_app_from_config
    config = get_tadm_config(ctx)
    app = create_app_from_config(config)
    app.run(debug=debug, host="0.0.0.0", port=3960)



tadm_main.add_command(list_tokens)
tadm_main.add_command(add_local_user)
tadm_main.add_command(serve)


if __name__ == "__main__":
    tadm_main()

