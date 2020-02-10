mailadm tool (beta)
======================

mailadm is the reference administration tool for managing
e-mail accounts at https://testrun.org which uses a
standard dovecot/postfix installation.

On a debian system it allows to run a https-exposed
e-mail account creation service as a wsgi server app
that you can run via systemd (see mailadm.service example).



Installing and Configuring the server part
-------------------------------------------

Assumptions:

- you are using `dovecot` as MDA (mail delivery agent)
  and `postfix` as MTA (mail transport agent).

- `/home/vmail/testrun.org` is the directory where
  mail directories are created and managed from dovecot.

- `/home/mailadm` is the home directory of the "mailadm" user
  where the application is installed in the virtualenv environment
  located at `/home/mailadm/venv`.

mailadm Configuration file
+++++++++++++++++++++++++++++

Example config::

    [token:oneweek]
    domain = testrun.org
    webdomain = testrun.org
    prefix = tmp_
    path_dovecot_users= /etc/dovecot/users
    path_virtual_mailboxes= /etc/postfix/virtual_mailboxes
    path_vmaildir = /home/vmail/testrun.org
    token = 1w_7wDioPeeXyZx96v3


mailadm http web application
++++++++++++++++++++++++++++

The http interface is a FLASK application that exposes a
``/new_email?t=<TOKEN>`` http-POST endpoint which creates a new e-mail
user.  Typically this small web app is run through a `gunicorn
<https://gunicorn.org/>` invocation like this::

    gunicorn -b localhost:3961 -w 1 mailadm.app:app

Here is an example systemd example config file:

    [Unit]
    Description=Testrun account management administration web API
    After=network.target

    [Service]
    User=root
    ExecStart=/home/mailadm/venv/bin/gunicorn -b localhost:3960 -w 1 mailadm.app:app
    Restart=always

    [Install]
    WantedBy=multi-user.target


creating a temporary account
+++++++++++++++++++++++++++++++++

::

    import requests
    r = requests.post("https://testrun.org/new_email?t=1w_7wDioPeeXyZx96v3")
    account = r.json()
    assert "@" in account["email"]
    assert len(account["password"]) > 10
