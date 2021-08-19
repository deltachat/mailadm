from mailadm.util import get_human_readable_id
from mailadm.db import write_connection


def add_token(name, expiry, maxuse, prefix, token):
    if token is None:
        token = expiry + "_" + get_human_readable_id(len=15)
    with write_connection() as conn:
        info = conn.add_token(name=name, token=token, expiry=expiry,
                              maxuse=maxuse, prefix=prefix)
        tc = conn.get_tokeninfo_by_name(info.name)
        return dump_token_info(tc)


def dump_token_info(token_info):
    """Format token info into a string
    """
    return """token: {}
  address prefix: {}
  accounts expire after: {}
  token was used {} of {} times
  token: {}
    - url: 
    - 
    """.format(token_info.name, token_info.prefix, token_info.expiry, token_info.usecount, token_info.maxuse,
               token_info.token, token_info.get_web_url(), token_info.get_qr_url())
