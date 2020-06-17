mailadm: adding and purging e-mail accounts as a service
========================================================

mailadm is a simple administration command lihne tool for creating and
purging e-mail accounts in Dovecot/Postfix installations that work with
text files.  Mailadm can be run as a web app that allows remote creation
of e-mail accounts, based on using secret tokens.  On the server you
can configure multiple tokens

The development repository is at

    https://github.com/deltachat/mailadm


Installing and Configuring the command line
-------------------------------------------

Assumptions used in this doc:

- you are using `dovecot` as MDA (mail delivery agent)
  and `postfix` as MTA (mail transport agent).

- You have Python and virtualenv installed.

- `/home/vmail/testrun.org/` is the base directory where all user mail
  directories are created by dovecot. This directory is managed by dovecot
  by the `vmail` user and dirs/files are created by the dovecot service.

- `/home/mailadm` ("$HOME") is the home directory of the "mailadm" user
  where mailadm configuration and account state is managed and where mailadm
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


mailadm configuration file
+++++++++++++++++++++++++++++++++

The mailadm configuration specifies where system file
locations and the mailadm database are to be found.
Token configuration are kept in the database.
We assume that `$HOME` points to the "mailadm" user home directory.

Example `$HOME/mailadm.config` file::

    # content of $HOME/mailadm.config
    [sysconfig]
    path_mailadm_db = $HOME/mailadm.db
    path_dovecot_users= $HOME/dovecot-users
    path_virtual_mailboxes = $HOME/virtual_mailboxes
    path_vmaildir = /home/vmail/testrun.org

    web_endpoint = http://localhost:3960
    mail_domain = testrun.org
    dovecot_uid = 1000
    dovecot_gid = 1000


Adding a first token and user
++++++++++++++++++++++++++++++

With the `MAILADM_CONFIG` environment variable
pointing to your `mailadm.config` file above,
you can now add a first "token"::

    $ mailadm add-token oneday --expiry 1d --prefix="tmp."
    added token 'oneday'
    token:oneday
      prefix = tmp.
      expiry = 1d
      maxuse = 50
      usecount = 0
      token  = 1d_cRqmTnHdQmku
      http://localhost:3960?t=1d_cRqmTnHdQmku&n=oneday
      DCACCOUNT:http://localhost:3960?t=1d_cRqmTnHdQmku&n=oneday

and then we can add a user (which will automatically use the token
because the email addresses matches the prefix)::

    $ mailadm add-user tmp.12345@testrun.org



Integration with dovecot
++++++++++++++++++++++++

mailadm integrates with dovecot by producing passwd files::

    # put this into /etc/dovecot/conf.d/auth-tmp-passwdfile.conf.ext
    passdb {
        driver = passwd-file
        args = scheme=CRYPT username_format=%u /home/mailadm/dovecot-users
    }

    userdb {
      driver = passwd-file
      args = username_format=%u /home/mailadm/dovecot-users

      default_fields = uid=vmail gid=vmail home=/home/vmail/%d/%n mail_location=maildir:/home/vmail/%d/%u/mail:INDEX=/home/vmail/%d/%u/index:LAYOUT=fs
    }

We need to include this file from the `/etc/dovecot/conf.d/10-auth.conf` file::

    !include auth-tmp-passwdfile.conf.ext

With these two files added/modified we can reload dovecot::

    systemctl reload mailadm


Integration with postfix
++++++++++++++++++++++++

You need to already have configured "virtual mailboxes" with postfix.
To make sure that postfix knows about about users added by
mailadm, add the mailadm related path `virtual_mailbox_maps`, for example::

    # somewhere in /etc/postfix/main.cfg
    virtual_mailbox_maps =
        hash:/etc/postfix/virtual_mailboxes
        hash:/home/mailadm/postfix-users


mailadm systemd unit file
++++++++++++++++++++++++++

To active the mailadm web app with systemd::

    # put this into /etc/systemd/system/mailadm.service
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
