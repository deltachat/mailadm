from mailadm.util import get_human_readable_id
from mailadm.conn import DBError


def add_token(name, expiry, maxuse, prefix, token, db):
    if token is None:
        token = expiry + "_" + get_human_readable_id(len=15)
    with db.write_transaction() as conn:
        info = conn.add_token(name=name, token=token, expiry=expiry,
                              maxuse=maxuse, prefix=prefix)
        tc = conn.get_tokeninfo_by_name(info.name)
        dump_token_info(tc)
