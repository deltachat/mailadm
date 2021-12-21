from mailadm.mailcow import MailcowConnection


def test_mailcow_happy_path(mailcow_endpoint, mailcow_auth, db):
    config = db.get_config()
    mailcow = MailcowConnection(config)

    # how many mailboxes are there in the beginning?
    r1 = mailcow.get_users()
    if r1.status_code == 401:
        print("Wrong token: ", r1.json().get("msg"))
    assert r1.status_code == 200
    begin_mailboxes = r1.json()

    # create mailbox
    r2 = mailcow.add_user_mailcow("pytest123@x.testrun.org", "pytest123")
    assert r2.status_code == 200
    assert r2.json()[0]["type"] == "success"
    print(r2.json())

    # is the mailbox there now?
    r3 = mailcow.get_users()
    assert r3.status_code == 200
    print(entry[0] for entry in r3.json())
    assert len(r3.json()) == len(begin_mailboxes) + 1

    # delete mailbox again
    r4 = mailcow.del_user_mailcow("pytest123@x.testrun.org")
    assert r4.status_code == 200
    assert r4.json()[0]["type"] == "success"
    assert r4.json()[0]["msg"][1] == "pytest123@x.testrun.org"
    assert len(r4.json()) == 1

    # still as many mailboxes as in the beginning?
    r5 = mailcow.get_users()
    assert r5.status_code == 200
    assert r5.json() == begin_mailboxes
