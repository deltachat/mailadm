import os
from flask import Flask, request, jsonify
from .config import Config


def getcfg():
    config_fn = os.environ.get("MAILADM_CFG")
    if config_fn is None:
        config_fn = os.path.expanduser("~mailadm/mailadm.cfg")
        if not os.path.exists(config_fn):
            raise RuntimeError("mailadm.cfg not found: MAILADM_CFG not set "
                               "and {!r} does not exist".format(config_fn))
    else:
        if not os.path.exists(config_fn):
            raise RuntimeError("MAILADM_CFG does not exist: '{!r}'".format(config_fn))
    return config_fn


def create_app_from_file(config_fn=None):
    if config_fn is None:
        config_fn = getcfg()

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

        with config.write_transaction() as conn:
            token_info = conn.get_tokeninfo_by_token(token)
            if token_info is None:
                return "token {} is invalid".format(token), 403

            try:
                user_info = conn.add_email_account(token_info, tries=10)
                conn.gen_sysfiles()
            except ValueError as e:
                return str(e), 409
            return jsonify(email=user_info.addr, password=user_info.clear_pw,
                           expiry=token_info.expiry, ttl=user_info.ttl)
    return app
