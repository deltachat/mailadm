mailadm: adding and purging e-mail accounts as a service
========================================================

mailadm is a simple administration command lihne tool for creating and
purging e-mail accounts in Dovecot/Postfix installations that work with
text files.  Mailadm can be run as a web app that allows remote creation
of e-mail accounts, based on using secret tokens.  On the server you
can configure multiple tokens

The development repository is at

    https://github.com/deltachat/mailadm


Installing and Configuring the server part
-------------------------------------------

Assumptions used in this doc:

- you are using `dovecot` as MDA (mail delivery agent)
  and `postfix` as MTA (mail transport agent).

- You have Python and virtualenv installed.

- `/home/vmail/testrun.org/` is the base directory where all user mail
  directories are created by dovecot. This directory is managed by dovecot
  by the `vmail` user and dirs/files are created by the dovecot service.

- `/home/mailadm` ("$HOME") is the home directory of the "mailadm" user
  where mailadm configuration is managed and where mailadm
  is installed in the virtualenv `/home/mailadm/venv` environment.


installing mailadm
+++++++++++++++++++++++++++++++++

Create and activate a Python virtualenv and install mailadm::

    # go to mailadm home directory
    cd ~mailadm

    python3 -m venv venv
    venv/bin/pip install mailadm

    # activate venv, and set mailadm config path on login
    echo "source ~/venv/bin/activate venv" >> .bashrc
    echo "export MAILADM_CONFIG=\$HOME/mailadm.config" >> .bashrc

Now do `source $HOME/.bashrc` so you have the new settings.


mailadm core configuration file
+++++++++++++++++++++++++++++++++

Example `$HOME/mailadm.config` file which configures one token
that allows creating e-mail accounts, of the form `tmp.*@testrun.org`::

    # content of $HOME/mailadm.config
    [token:oneweek]
    domain = testrun.org
    webdomain = testrun.org
    expiry = 1w
    prefix = tmp.
    path_dovecot_users= /home/mailadm/dovecot-users
    path_virtual_mailboxes= /home/mailadm/postfix-users
    path_vmaildir = /home/mailadm/vmail
    token = 1w_7wDioPeeXyZx96v3

You should now be able to run a first mailadm subcommand::

    mailadm list-tokens

which should show you::

    token:oneweek
      prefix = tmp.
      expiry = 1w
      DCACCOUNT:https://testrun.org/new_email?t=1w_7wDioPeeXyZx96v3


mailadm systemd unit file
++++++++++++++++++++++++++

You may copy this file to a systemd service directory::

    # content of /etc/systemd/system/mailadm.service
    [Unit]
    Description=Account management administration web API
    After=network.target

    [Service]
    User=mailadm
    Environment="MAILADM_CONFIG=/home/mailadm/mailadm.config"
    ExecStart=/home/mailadm/venv/bin/gunicorn -b localhost:3961 -w 1 mailadm.app:app
    Restart=always

    [Install]
    WantedBy=multi-user.target

You can then start the web service (on localhost port 3961) like this::

    systemctl enable mailadm
    systemctl start mailadm


nginx configuration
++++++++++++++++++++++++++++

If your nginx serves a domain you may add this endpoint to its config
to make mailadm available through the web::

You can configure your nginx site config by including this endpoint::

    # add these lines to your nginx-site config
    # (/etc/nginx/sites-enabled/XXX)
    location /new_email {
        proxy_pass http://localhost:3961/;
    }

We assume here that the site is exposed as `testrun.org` (see `webdomain` in the `mailadm.config` file)


creating a temporary account
+++++++++++++++++++++++++++++++++

A typical `DCACCOUNT` code specifies the token-configuration in URL format::

   DCACCOUNT:https://testrun.org/new_email?t=1w_7wDioPeeXyZx96v3&name=<NAME_OF_TOKEN>>

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
