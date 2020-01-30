import os
import pprint
from flask import Flask, request, jsonify
from .mail import MailController
from .config import Config


def create_app_from_file(config_fn):
    config = Config(config_fn)

    app = Flask("testrun-account-server")

    @app.route('/new_email', methods=["POST"])
    def new_email():
        token = request.args.get("t")
        if token is None:
            return "?t (token) parameter not specified", 403

        mailconfig = config.get_mail_config_from_token(token)
        if mailconfig is None:
            return "token {} is invalid".format(token), 403

        email = mailconfig.make_email_address()
        mc = mailconfig.make_controller()
        try:
            d = mc.add_email_account(email)
        except ValueError as e:
            return str(e), 409
        return jsonify(d)

    return app
