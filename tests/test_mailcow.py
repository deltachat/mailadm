import requests as r
import os



def test_get_mailboxes():
    if not os.environ.get("MAILCOW_TOKEN"):
        raise KeyError("Please set mailcow API Key with the environment variable MAILCOW_TOKEN")
    baseurl = "https://dc.develcow.de/api/v1/"

    # how many mailboxes are there in the beginning?
    url = baseurl + "get/mailbox/all"
    authheader = {"X-API-Key": os.environ.get("MAILCOW_TOKEN")}
    r1 = r.get(url, headers=authheader)
    assert r1.status_code == 200
    beginMB = len(r1.json())

    # create mailbox
    url = baseurl + "add/mailbox"
    payload = {
        "local_part": "pytest123",
        "domain": "x.testrun.org",
        "password": "pytest123",
        "password2": "pytest123",
        "active": True,
        "force_pw_update": False,
        "tls_enforce_in": True,
        "tls_enforce_out": True,
    }
    r2 = r.post(url, json=payload, headers=authheader)
    assert r2.status_code == 200
    print(r2.json())

    # is the mailbox there now?
    url = baseurl + "get/mailbox/all"
    r3 = r.get(url, headers=authheader)
    assert r3.status_code == 200
    print(entry[0] for entry in r3.json())
    assert len(r3.json()) == beginMB + 1

    # delete mailbox again
    url = baseurl + "delete/mailbox"
    payload = ["pytest123@x.testrun.org"]
    r4 = r.post(url, json=payload, headers=authheader)
    assert r4.status_code == 200
    assert r4.json()[0]["type"] == "success"
    assert r4.json()[0]["msg"][1] == "pytest123@x.testrun.org"
    assert len(r4.json()) == 1

    # still as many mailboxes as in the beginning?
    url = baseurl + "get/mailbox/all"
    r5 = r.get(url, headers=authheader)
    assert r5.status_code == 200
    assert len(r5.json()) == beginMB


if __name__ == "__main__":
    test_get_mailboxes()
