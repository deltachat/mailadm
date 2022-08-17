import time
from mailadm.util import get_human_readable_id
from mailadm.conn import DBError
from mailadm.mailcow import MailcowError
from mailadm.gen_qr import gen_qr


def add_token(db, name, expiry, maxuse, prefix, token) -> dict:
    """Adds a token to create users
    """
    if token is None:
        token = expiry + "_" + get_human_readable_id(len=15)
    with db.write_transaction() as conn:
        try:
            info = conn.add_token(name=name, token=token, expiry=expiry, maxuse=maxuse,
                                  prefix=prefix)
        except DBError:
            return {"status": "error", "message": "token %s does already exist" % (name,)}
        except ValueError:
            return {"status": "error", "message": "maxuse must be a number"}
        tc = conn.get_tokeninfo_by_name(info.name)
        return {"status": "success", "message": dump_token_info(tc)}


def add_user(db, token=None, addr=None, password=None, dryrun=False) -> {}:
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
        except MailcowError as e:
            return {"status": "error",
                    "message": "failed to add e-mail account {}: {}".format(addr, e)}
        if dryrun:
            conn.delete_email_account(user_info.addr)
            return {"status": "dryrun",
                    "message": user_info}
        return {"status": "success",
                "message": user_info}


def prune(db, dryrun=False) -> {}:
    sysdate = int(time.time())
    with db.write_transaction() as conn:
        expired_users = conn.get_expired_users(sysdate)
        if not expired_users:
            return {"status": "success",
                    "message": ["nothing to prune"]}
        if dryrun:
            result = {"status": "dryrun",
                      "message": []}
            for user_info in expired_users:
                result["message"].append("would delete %s (token %s)" %
                                         (user_info.addr, user_info.token_name))
        else:
            result = {"status": "success",
                      "message": []}
            for user_info in expired_users:
                try:
                    conn.delete_email_account(user_info.addr)
                except (DBError, MailcowError) as e:
                    result["status"] = "error"
                    result["message"].append("failed to delete account %s: %s" %
                                             (user_info.addr, e))
                    continue
                result["message"].append("pruned %s (token %s)" %
                                         (user_info.addr, user_info.token_name))
        return result


def list_tokens(db) -> str:
    """Print token info for all tokens
    """
    output = []
    with db.read_connection() as conn:
        for name in conn.get_token_list():
            token_info = conn.get_tokeninfo_by_name(name)
            output.append(dump_token_info(token_info))
    return '\n'.join(output)


def qr_from_token(db, tokenname):
    with db.read_connection() as conn:
        token_info = conn.get_tokeninfo_by_name(tokenname)
        config = conn.config

    if token_info is None:
        return {"status": "error",
                "message": "token {!r} does not exist".format(tokenname)}

    image = gen_qr(config, token_info)
    fn = "docker-data/dcaccount-%s-%s.png" % (config.mail_domain, token_info.name)
    image.save(fn)
    return {"status": "success", "filename": fn}


def dump_token_info(token_info) -> str:
    """Format token info into a string
    """
    return """token: {}
  address prefix: {}
  accounts expire after: {}
  token was used {} of {} times
  token: {}
    - url: {}
    - QR data: {}
    """.format(token_info.name, token_info.prefix, token_info.expiry, token_info.usecount,
               token_info.maxuse, token_info.token, token_info.get_web_url(),
               token_info.get_qr_uri())
