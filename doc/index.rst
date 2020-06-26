mailadm: managing token-based temporary e-mail accounts
========================================================

mailadm is automated e-mail account management tooling
for use by [Delta Chat](https://delta.chat).

The `mailadm` command line tool allows to add or remove tokens
for which a QR code can be generated. This QR code can then be
scanned in the Setup screen from all Delta Chat apps. After scanning
the user is asked if they want to create a temporary account.

The account creation happens via the `mailadm` web interface
and creates a random user id (the local part of an e-mail).

Mailadm implements a sqlite database for keeping token and user state
and provides queries to Dovecot and a `virtual_mailboxes` database
to tell Postfix that a virtual account exists.

.. note::

    At this point installation is only well supported/documented for particular
    Dovecot/Postfix/Systemd/Nginx configurations. The mailadm software does
    not depend on it but you will have to figure the use of other server software
    yourselve. It might still make sense to use part of the install script.
    As we are advocating working from a git checkout you may keep your own
    branch in your local git and update with remote master from time to time.
    Please report bugs and improvements as issues or PR requests.


Quickstart
----------

Cd into a local git copy of the mailadm repository::

    $ git clone https://github.com/deltachat/mailadm


    $ cd mailadm


Now **review and run** as root the install script:

    $ sudo bash install_mailadm.sh


Final touches with nginx and dovecot
++++++++++++++++++++++++++++++++++++

Adding a first token and user
++++++++++++++++++++++++++++++

With the `MAILADM_CFG` environment variable
pointing to the `~mailadm/mailadm.cfg` file above,
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

When adding/manipulating users `mailadm` writes out
virtual mailbox "map" files (including the ".db" form)
so that Postfix knows which mailadm mailboxes exist.


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
the `mailadm.cfg` file and modify the `web_endpoint` value accordingly
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

