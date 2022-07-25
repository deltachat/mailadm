from mailadm.util import get_human_readable_id
from mailadm.conn import DBError


def add_token(db, name, expiry, maxuse, prefix, token):
    """Adds a token to create users
    """
    if token is None:
        token = expiry + "_" + get_human_readable_id(len=15)
    with db.write_transaction() as conn:
        info = conn.add_token(name=name, token=token, expiry=expiry,
                              maxuse=maxuse, prefix=prefix)
        tc = conn.get_tokeninfo_by_name(info.name)
        return dump_token_info(tc)


def add_user(db, token=None, addr=None, password=None, dryrun=False):
    """Adds a new user to be managed by mailadm
    """
    with db.write_transaction() as conn:
        if token is None:
            if "@" not in addr:
                # there is probably a more pythonic solution to this.
                # the goal is to display the error, whether the command came via CLI or delta bot.
                return {"status": "error",
                        "message": "invalid email address: {}".format(addr)}

            token_info = conn.get_tokeninfo_by_addr(addr)
            if token_info is None:
                return {"status": "error",
                        "message": "could not determine token for addr: {!r}".format(addr)}
        else:
            token_info = conn.get_tokeninfo_by_name(token)
            if token_info is None:
                return {"status": "error",
                        "message": "token does not exist: {!r}".format(token)}
        try:
            user_info = conn.add_email_account(token_info, addr=addr, password=password)
        except DBError as e:
            return {"status": "error",
                    "message": "failed to add e-mail account {}: {}".format(addr, e)}
        return {"status": "success",
                "message": user_info}


def list_tokens(db):
    """Print token info for all tokens
    """
    output = []
    with db.read_connection() as conn:
        for name in conn.get_token_list():
            token_info = conn.get_tokeninfo_by_name(name)
            output.append(dump_token_info(token_info))
    return '\n'.join(output)


def dump_token_info(token_info):
    """Format token info into a string
    """
    return """token: {}
  address prefix: {}
  accounts expire after: {}
  token was used {} of {} times
  token: {}
    - url: {}
    - QR data: {}
    """.format(token_info.name, token_info.prefix, token_info.expiry, token_info.usecount, token_info.maxuse,
               token_info.token, token_info.get_web_url(), token_info.get_qr_uri())
