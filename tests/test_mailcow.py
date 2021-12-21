import requests as r


def test_get_mailboxes(mailcow_endpoint, mailcow_auth):
    # how many mailboxes are there in the beginning?
    url = mailcow_endpoint + "get/mailbox/all"
    r1 = r.get(url, headers=mailcow_auth)
    if r1.status_code == 401:
        print("Wrong token: ", r1.json().get("msg"))
    assert r1.status_code == 200
    beginMB = len(r1.json())

    # create mailbox
    url = mailcow_endpoint + "add/mailbox"
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
    r2 = r.post(url, json=payload, headers=mailcow_auth)
    assert r2.status_code == 200
    print(r2.json())

    # is the mailbox there now?
    url = mailcow_endpoint + "get/mailbox/all"
    r3 = r.get(url, headers=mailcow_auth)
    assert r3.status_code == 200
    print(entry[0] for entry in r3.json())
    assert len(r3.json()) == beginMB + 1

    # delete mailbox again
    url = mailcow_endpoint + "delete/mailbox"
    payload = ["pytest123@x.testrun.org"]
    r4 = r.post(url, json=payload, headers=mailcow_auth)
    assert r4.status_code == 200
    assert r4.json()[0]["type"] == "success"
    assert r4.json()[0]["msg"][1] == "pytest123@x.testrun.org"
    assert len(r4.json()) == 1

    # still as many mailboxes as in the beginning?
    url = mailcow_endpoint + "get/mailbox/all"
    r5 = r.get(url, headers=mailcow_auth)
    assert r5.status_code == 200
    assert len(r5.json()) == beginMB
