from flask import Flask, request, jsonify
from .config import Config


def create_app_from_file(config_fn):
    config = Config(config_fn)
    return create_app_from_config(config)


def create_app_from_config(config):
    app = Flask("mailadm-account-server")
    app.mailadm_config = config

    @app.route('/', methods=["POST"])
    def new_email():
        token = request.args.get("t")
        if token is None:
            return "?t (token) parameter not specified", 403

        token_config = config.get_tokenconfig_by_token(token)
        if token_config is None:
            return "token {} is invalid".format(token), 403

        try:
            user_info = token_config.add_email_account(gen_sysfiles=True, tries=10)
        except ValueError as e:
            return str(e), 409
        return jsonify(email=user_info.addr, password=user_info.clear_pw,
                       expiry=token_config.info.expiry, ttl=user_info.ttl)
    return app
