from flask import Flask, request, jsonify
import mailadm.db
from mailadm.conn import DBError
from mailadm.mailcow import MailcowError


def create_app_from_db_path(db_path=None):
    if db_path is None:
        db_path = mailadm.db.get_db_path()

    db = mailadm.db.DB(db_path)
    return create_app_from_db(db)


def create_app_from_db(db):
    app = Flask("mailadm-account-server")
    app.db = db

    @app.route('/', methods=["POST"])
    def new_email():
        token = request.args.get("t")
        if token is None:
            return jsonify(type="error", status_code=403,
                           reason="?t (token) parameter not specified")

        with db.write_transaction() as conn:
            token_info = conn.get_tokeninfo_by_token(token)
            if token_info is None:
                return jsonify(type="error", status_code=403,
                               reason="token {} is invalid".format(token))
            try:
                user_info = conn.add_email_account_tries(token_info, tries=10)
                return jsonify(email=user_info.addr, password=user_info.password,
                               expiry=token_info.expiry, ttl=user_info.ttl)
            except (DBError, MailcowError) as e:
                return jsonify(type="error", status_code=500, reason=str(e))
    return app
