from flask import Flask, request, jsonify
import mailadm.db
from mailadm.conn import DBError
from mailadm.mailcow import MailcowError
from requests.exceptions import ReadTimeout


def create_app_from_db_path(db_path=None):
    if db_path is None:
        db_path = mailadm.db.get_db_path()

    db = mailadm.db.DB(db_path)
    return create_app_from_db(db)


def create_app_from_db(db):
    app = Flask("mailadm-account-server")
    app.db = db

    @app.route("/", methods=["POST"])
    def new_email():
        token = request.args.get("t")
        if token is None:
            return (
                jsonify(type="error", status_code=403, reason="?t (token) parameter not specified"),
                403,
            )

        with db.write_transaction() as conn:
            token_info = conn.get_tokeninfo_by_token(token)
            if token_info is None:
                return (
                    jsonify(
                        type="error", status_code=403, reason="token {} is invalid".format(token)
                    ),
                    403,
                )
            try:
                user_info = conn.add_email_account_tries(token_info, tries=10)
                return jsonify(
                    email=user_info.addr,
                    password=user_info.password,
                    expiry=token_info.expiry,
                    ttl=user_info.ttl,
                )
            except (DBError, MailcowError) as e:
                if "does already exist" in str(e):
                    return (
                        jsonify(
                            type="error", status_code=409, reason="user already exists in mailcow"
                        ),
                        409,
                    )
                if "UNIQUE constraint failed" in str(e):
                    return (
                        jsonify(
                            type="error", status_code=409, reason="user already exists in mailadm"
                        ),
                        409,
                    )
                return jsonify(type="error", status_code=500, reason=str(e)), 500
            except ReadTimeout:
                return jsonify(type="error", status_code=504, reason="mailcow not reachable"), 504

    return app
