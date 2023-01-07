import sys
import random
import base64


def gen_password():
    with open("/dev/urandom", "rb") as f:
        s = f.read(21)
    return base64.b64encode(s).decode("ascii")[:12]


def get_human_readable_id(len=5, chars="2345789acdefghjkmnpqrstuvwxyz"):
    return "".join(random.choice(chars) for i in range(len))


def parse_expiry_code(code):
    if code == "never":
        return sys.maxsize

    if len(code) < 2:
        raise ValueError("expiry codes are at least 2 characters")
    val = int(code[:-1])
    c = code[-1]
    if c == "y":
        return val * 365 * 24 * 60 * 60
    elif c == "w":
        return val * 7 * 24 * 60 * 60
    elif c == "d":
        return val * 24 * 60 * 60
    elif c == "h":
        return val * 60 * 60
    elif c == "m":
        return val * 60
    elif c == "s":
        return val
