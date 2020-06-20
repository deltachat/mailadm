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

- `/home/vmail/example.org/` is the base directory where all user mail
  directories are created by dovecot. This directory is managed by dovecot
  by the `vmail` user and dirs/files are created by the dovecot service.

- `/home/mailadm` ("$HOME") is the home directory of the "mailadm" user
  where mailadm configuration and account state is managed and where mailadm
  is installed in the virtualenv `/home/mailadm/venv` environment.


installing mailadm
+++++++++++++++++++++++++++++++++

Create a user account "mailadm" and login/su to this user.
Then create and activate a Python virtualenv and install mailadm::

    # go to mailadm home directory
    cd ~mailadm

    virtualenv venv
    venv/bin/pip install -q mailadm

    # always activate venv, and set mailadm config path for mailadm user
    echo "source ~/venv/bin/activate venv" >> .bashrc
    echo "export MAILADM_CONFIG=\$HOME/mailadm.config" >> .bashrc

Now do `source $HOME/.bashrc` so you have the new settings.


mailadm configuration file
+++++++++++++++++++++++++++++++++

The mailadm configuration specifies where system file
locations and the mailadm database are to be found.
Token and user information is kept in the sqlite database
located at `path_mailadm_db`.  Here, we assume that `$HOME` points to
the "mailadm" user home directory::

    # content of /home/mailadm/mailadm.config
    [sysconfig]
    path_mailadm_db = $HOME/mailadm.db
    path_dovecot_users= $HOME/dovecot-users
    path_virtual_mailboxes = $HOME/virtual_mailboxes
    path_vmaildir = /home/vmail/example.org

    web_endpoint = http://localhost:3961/
    mail_domain = example.org
    dovecot_uid = 1000
    dovecot_gid = 1000


Adding a first token and user
++++++++++++++++++++++++++++++

With the `MAILADM_CONFIG` environment variable
pointing to your `mailadm.config` file above,
you can now add a first "token"::

    $ mailadm add-token oneday --expiry 1d --prefix="tmp."
    DB: Creating schema /home/mailadm/mailadm.db
    added token 'oneday'
    token:oneday
      prefix = tmp.
      expiry = 1d
      maxuse = 50
      usecount = 0
      token  = 1d_r84EW3N8hEKk
      http://localhost:3961/new_email?t=1d_r84EW3N8hEKk&n=oneday
      DCACCOUNT:http://localhost:3961/new_email?t=1d_r84EW3N8hEKk&n=oneday

and then we can add a user (which will automatically use the token
because the email addresses matches the prefix)::

    $ mailadm add-user tmp.12345@example.org
    added addr 'tmp.12345@example.org' with token 'oneday'
    wrote /home/mailadm/virtual_mailboxes
    wrote /home/mailadm/dovecot-users

Mailadm writes out files for use by postfix and dovecot
and the next section provides an example how to integrate them.


Integrate with system services
------------------------------


integration with dovecot
++++++++++++++++++++++++

We can integrate mailadm with dovecot (for serving IMAP users)
by producing a passwd configuration file::

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

Now we need to include this file from the `/etc/dovecot/conf.d/10-auth.conf` file
by adding the following line::

    !include auth-tmp-passwdfile.conf.ext

With these two dovecot related files added/modified we can reload dovecot::

    systemctl reload dovecot


Integration with postfix
++++++++++++++++++++++++

You need to already have configured "virtual mailboxes" with postfix.
Also, the `mail_domain` in the `mailadm.config` file needs to point
to the domain which postfix serves.

To make sure that postfix knows about about users added by
mailadm, add the `postfix-users` file controlled by mailadm::

    # somewhere in /etc/postfix/main.cfg
    virtual_mailbox_maps =
        hash:/etc/postfix/virtual_mailboxes
        hash:/home/mailadm/postfix-users


Configuring the web API
++++++++++++++++++++++++++++

In order to make the mailadm web app available you can
create a systemd service and configure nginx to serve
the web app to the outside world.

First we need to install the web runner "gunicorn"
while logged in as "mailadm" user::

    venv/bin/pip install gunicorn

And then we add the following systemd unit file::

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

You should now be able to start the systemd web service like this::

    $ systemctl enable mailadm

    $ systemctl start mailadm

Please ensure that the service is running with `systemctl status mailadm`.


Testing the web app
-----------------------------

Let's find out the URL again for creating new users::

    $ mailadm list-tokens
    token:oneday
      prefix = tmp.
      expiry = 1d
      maxuse = 50
      usecount = 1
      token  = 1d_r84EW3N8hEKk
      http://localhost:3961/?t=1d_r84EW3N8hEKk&n=oneday
      DCACCOUNT:http://localhost:3961/new_email?t=1d_r84EW3N8hEKk&n=oneday

The second last line is the one we can use with curl::

   $ curl -X POST 'http://localhost:3961/?t=1d_r84EW3N8hEKk&n=oneday'
   {"email":"tmp.km5y5@example.org","expiry":"1d","password":"cg8VL5f0jH2U","ttl":86400}

We got an e-mail account through the web API, nice.

Note that we are using a localhost-url.  Let's see how
we could configure "nginx" to serve our web app.


nginx configuration
++++++++++++++++++++++++++++

We assume here that you:

- have HTTPS working for your web domain

- have an operational postfix/dovecot configuration for the domain
  configured by `mail_domain`

- mailadm is running as a service and dovecot and postfix are using its files.

To make the web API available you can configure nginx
to proxy to the localhost app::

    # add these lines to your nginx-site config
    # (/etc/nginx/sites-enabled/XXX)
    location / {
        proxy_pass http://localhost:3961/;
    }

Note that if you change the `location /` parameter you need to edit
the `mailadm.config` file and modify the `web_endpoint` value accordingly
and then restart the mailadm service.


Purging old accounts
++++++++++++++++++++++++

The `mailadm purge` command will remove accounts
including the home directories of expired users.
You can call it from a "cron.daily" script.

Purging old accounts
++++++++++++++++++++++++

The `mailadm purge` command will remove accounts
including the home directories of expired users.
You can call it from a "cron.daily" script.



Bonus: QR code generation
---------------------------

Once you have mailadm configured and integrated with
nginx, postfix and dovecot you can generate a QR code:

    $ mailadm gen-qr oneday
    dcaccount-testrun.org-oneday.png written for token 'oneday'

You can print or hand out this QR code file and people can scan it with
their Delta Chat to get a oneday "burner" account.

