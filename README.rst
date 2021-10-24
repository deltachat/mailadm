mailadm
=======

mailadm is an administration tool for creating and removing e-mail accounts
(especially temporary accounts) on a `mailcow <https://mailcow.email/>`_ mail
server. This makes creating an email account as easy as scanning a QR code.

The general idea of how it works:

1. Admins generate an "account creation token", which can be displayed as a QR
   code
2. A soon-to-be user uses an email client to scan the QR code, which sends a
   web request to mailadm
3. mailadm creates the account and sends the password to the Delta Chat app,
   the user is automatically logged in to the new account

mail clients with mailadm support
---------------------------------

So far only the `Delta Chat messenger <https://delta.chat/>`_ supports mailadm.

setup & usage
-------------

See the `docs/index.rst` file or https://mailadm.readthedocs.io for more info.

Setup Development Environment
-----------------------------

```
git clone https://github.com/deltachat/mailadm
python3 -m venv venv
. venv/bin/activate
pip install pytest tox
pip install .
sudo apt install postfix    # choose "No configuration" when asked
sudo systemctl disable postfix
sudo touch /etc/postfix/main.cf
```
