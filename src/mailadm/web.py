from flask import Flask, request, jsonify
import mailadm.db
from mailadm.conn import DBError


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
            return "?t (token) parameter not specified", 403

        with db.write_transaction() as conn:
            token_info = conn.get_tokeninfo_by_token(token)
            if token_info is None:
                return "token {} is invalid".format(token), 403

            try:
                user_info = conn.add_email_account(token_info, tries=10)
                conn.gen_sysfiles()
            except DBError as e:
                return str(e), 409
            return jsonify(email=user_info.addr, password=user_info.clear_pw,
                           expiry=token_info.expiry, ttl=user_info.ttl)
    return app
