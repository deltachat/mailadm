mailadm: adding and purging e-mail accounts as a service
========================================================

mailadm is a simple administration tool for managing e-mail accounts at
https://testrun.org. This e-mail server uses Debian9 and a
standard dovecot/postfix installation, configured through
standard text files.

On a debian system mailadm can be run as a wsgi server app
that you can run via systemd (see mailadm.service example).

The development repository is at

    https://github.com/deltachat/mailadm


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

A typical `DCACCOUNT` code specifies the token-configuration in URL format::

   DCACCOUNT:https://testrun.org/new_email?t=1w_7wDioPeeXyZx96v3&usermod&maxdays=<NUMDAYS>

   &usermod is present if the server will allow setting a username and password
   &maxdays indicates the number of days after which the account is removed

To get a random e-mail address with a random password you may issue::

   curl -X POST https://testrun.org/new_email?t=1w_7wDioPeeXyZx96v3

To get a specific e-mail address with a random password you may issue::

   curl -X POST https://testrun.org/new_email?t=1w_7wDioPeeXyZx96v3&username=<name>

To get a specific e-mail address with a specific password you may issue::

   curl -X POST https://testrun.org/new_email?t=1w_7wDioPeeXyZx96v3&username=<name>&password=<password>

In each case, the server will return :

- 409 status code if the name is already taken.

- 200 status code and json content with these keys::

      email: <final e-mail address>
      password: <final password>
      expires: <expiration UTC timestamp in seconds>

is


from python::

    import requests
    r = requests.post("https://testrun.org/new_email?t=1w_7wDioPeeXyZx96v3")
    account = r.json()
    assert "@" in account["email"] and account["email"].startswith("tmp_")
    assert len(account["password"]) > 10
