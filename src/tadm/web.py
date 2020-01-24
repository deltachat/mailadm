import os
import pprint
import json
import random
from flask import Flask, request, jsonify
from .mailuser import MailUser


def create_app(config):
    app = Flask("testrun-account-server")

    @app.route('/newtmpuser', methods=["POST"])
    def newtmpuser():
        json_data = request.get_json()
        token = json_data['token_create_user']
        if token == config["token_create_user"]:
            mu = MailUser("testrun.org", dryrun=False,
                          path_dovecot_users=config["path_dovecot_users"],
                          path_virtual_mailboxes=config["path_virtual_mailboxes"],
                          path_vmaildir=config["path_vmaildir"],
            )
            username = json_data.get("username")
            if not username:
                username = get_random_tmpname()
            email = "{}@testrun.org".format(username)
            try:
                d = mu.add_email_account(email)
            except ValueError as e:
                return str(e), 409
            return jsonify(d)
        else:
            return "token {} is invalid".format(token), 403

    return app


def get_random_tmpname():
    num = random.randint(0, 10000000000000000)
    return "tmp_{}".format(num)


def create_app_from_file(config_fn):
    with open(config_fn) as f:
        config = json.load(f)
    assert config["token_create_user"]
    return create_app(config)
