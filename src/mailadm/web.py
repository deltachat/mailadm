from flask import Flask, request, jsonify
from .config import Config


def create_app_from_file(config_fn):
    config = Config(config_fn)
    return create_app_from_config(config)


def create_app_from_config(config):
    app = Flask("mailadm-account-server")
    app.mailadm_config = config

    @app.route('/new_email', methods=["POST"])
    def new_email():
        token = request.args.get("t")
        if token is None:
            return "?t (token) parameter not specified", 403

        mailconfig = config.get_mail_config_from_token(token)
        if mailconfig is None:
            return "token {} is invalid".format(token), 403

        username = request.args.get("username")
        password = request.args.get("password")

        try:
            email = mailconfig.make_email_address(username)
        except ValueError:
            return "username can not be set", 403

        mc = mailconfig.make_controller()
        try:
            d = mc.add_email_account(email, password=password)
        except ValueError as e:
            return str(e), 409
        return jsonify(d)

    return app
