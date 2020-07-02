from imapclient import IMAPClient
import email
import requests
import smtplib
import urllib.parse


def receive_imap(host, user, password, num):
    conn = IMAPClient(host)
    conn.login(user, password)
    info = conn.select_folder("INBOX")
    print(info)
    messages = conn.fetch("1:*", [b'FLAGS'])
    latest_msg = max(messages)
    requested = "FLAGS BODY.PEEK[]"
    for uid, data in conn.fetch([latest_msg], [b"FLAGS", b"BODY.PEEK[]"]).items():
        body_bytes = data[b'BODY[]']
        email_message = email.message_from_bytes(body_bytes)
        assert email_message["subject"] == str(num)
        print("received message num={}".format(num))
        print(email_message)


def send_self_mail(host, user, password, num):
    smtp = smtplib.SMTP(host, 587)
    smtp.set_debuglevel(1)
    smtp.starttls()
    smtp.login(user, password)
    msg = """\
From: {user}
To: {user}
Subject: {num}

hi there
""".format(user=user, num=num)
    smtp.sendmail(user, [user], msg)
    print("send message num={}".format(num))


if __name__ == "__main__":
    import sys
    if sys.argv[1].startswith("https"):
        res = requests.post(sys.argv[1])
        assert res.status_code == 200
        data = res.json()
        user = data["email"]
        password = data["password"]

        if len(sys.argv) >= 3:
            host = sys.argv[2]
        else:
            host = urllib.parse.urlparse(sys.argv[1]).hostname
    else:
        user, password, host = sys.argv[1:]
    num = 42
    send_self_mail(host, user, password, num)
    receive_imap(host, user, password, num)
