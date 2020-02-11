mailadm: adding and purging e-mail accounts remote or locally
=================================================================

mailadm is a simple administration tool for managing e-mail accounts at
https://testrun.org. This e-mail server uses Debian9 and a
standard dovecot/postfix installation, configured through
standard text files.

On a debian system mailadm can be run as a wsgi server app
that you can run via systemd (see mailadm.service example).


Installing and Configuring the server part
-------------------------------------------

Assumptions used in this doc:

- you are using `dovecot` as MDA (mail delivery agent)
  and `postfix` as MTA (mail transport agent).

- `/home/vmail/testrun.org` is the directory where
  mail directories are created and managed from dovecot.

- `/home/mailadm` is the home directory of the "mailadm" user
  where the application is installed in the virtualenv environment
  located at `/home/mailadm/venv`.

- You have Python and virtualenv installed.


mailadm Configuration file
+++++++++++++++++++++++++++++

Example config:

.. include:: ../example_mailadm.config
    :literal:



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
    ExecStart=/home/mailadm/venv/bin/gunicorn -b localhost:3961 -w 1 mailadm.app:app
    Restart=always

    [Install]
    WantedBy=multi-user.target


creating a temporary account
+++++++++++++++++++++++++++++++++

from a shell::

   curl -X POST https://testrun.org/new_email?t=1w_7wDioPeeXyZx96v3


from python::

    import requests
    r = requests.post("https://testrun.org/new_email?t=1w_7wDioPeeXyZx96v3")
    account = r.json()
    assert "@" in account["email"] and account["email"].startswith("tmp_")
    assert len(account["password"]) > 10
