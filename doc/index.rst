mailadm: managing token-based temporary e-mail accounts
========================================================

mailadm is automated e-mail account management tooling
for use by `Delta Chat <https://delta.chat>`_.

The `mailadm` command line tool allows to add or remove tokens which are
typically presented to users as QR tokens.  This QR code can then be
scanned in the Setup screen from all Delta Chat apps. After scanning the
user is asked if they want to create a temporary account.

The account creation happens via the `mailadm` web interface
and creates a random user id (the local part of an e-mail).

Mailadm keeps all configuration, token and user state in a single
sqlite database.  It comes with an example install script that
can be modified for distributions.


Quick Start
-----------

.. note::

    To use mailadm, you need admin access to a `Mailcow
    <https://mailcow.email/>`_ instance. You can run mailadm as a docker
    container, either on the same machine as mailcow or somewhere else.

First get a git copy of the mailadm repository and change into it.

    $ git clone https://github.com/deltachat/mailadm
    $ cd mailadm
    $ mkdir docker-data

Now you need to configure some environment variables in a file called ``.env``:

* ``MAIL_DOMAIN``: the domain part of the email addresses your users will have. 
* ``WEB_ENDPOINT``: the web endpoint of mailadm; make sure mailadm receives
  POST requests at this address.
* ``MAILCOW_ENDPOINT``: the API endpoint of your mailcow instance.
* ``MAILCOW_TOKEN``: the access token for the mailcow API; you can generate it
  in the mailcow admin interface.

In the end, your ``.env`` file should look similar to this:

.. code:: bash

    MAIL_DOMAIN=mail.example.org
    WEB_ENDPOINT=http://mailadm.example.org:3691/
    MAILCOW_ENDPOINT=https://mailcow-web.example.org/api/v1/
    MAILCOW_TOKEN=932848-324B2E-787E98-FCA29D-89789A
    
Now you can build and run the docker container:

.. code:: bash

    $ sudo docker build . -t mailadm-mailcow
    $ sudo docker run --mount type=bind,source=$PWD/docker-data,target=/mailadm/docker-data --env-file .env --rm mailadm-mailcow mailadm init
    $ sudo docker run -d -p 3691:3691 --mount type=bind,source=$PWD/docker-data,target=/mailadm/docker-data --name mailadm mailadm-mailcow gunicorn -b :3691 -w 1 mailadm.app:app

.. note::

    As the web endpoint also transmits passwords, it is highly recommended to
    protect the WEB_ENDPOINT with HTTPS, for example through an nginx reverse
    proxy. In this case, WEB_ENDPOINT needs to be the outward facing address,
    in this example maybe something like
    `https://mailadm.example.org/new_email/`.
    
Adding a first token and user
++++++++++++++++++++++++++++++

In order to use `mailadm` you need to be able
to execute `~mailadm/venv/bin/mailadm` and you
need write rights to the `mailadm/mailadm.db` file.
Moreover you need to set an environment variable
for finding the mailadm database file::

    export MAILADM_DB=~mailadm/mailadm.db

You can then add a first token::

    $ mailadm add-token oneday --expiry 1d --prefix="tmp."
    DB: Creating schema /home/mailadm/mailadm.db
    added token 'oneday'
    token:oneday
      prefix = tmp.
      expiry = 1d
      maxuse = 50
      usecount = 0
      token  = 1d_r84EW3N8hEKk
      http://localhost:3691/new_email?t=1d_r84EW3N8hEKk&n=oneday
      DCACCOUNT:http://localhost:3691/new_email?t=1d_r84EW3N8hEKk&n=oneday

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
      http://localhost:3691/?t=1d_r84EW3N8hEKk&n=oneday
      DCACCOUNT:http://localhost:3691/new_email?t=1d_r84EW3N8hEKk&n=oneday

The second last line is the one we can use with curl::

   $ curl -X POST 'http://localhost:3691/?t=1d_r84EW3N8hEKk&n=oneday'
   {"email":"tmp.km5y5@example.org","expiry":"1d","password":"cg8VL5f0jH2U","ttl":86400}

We got an e-mail account through the web API, nice.

Note that we are using a localhost-url whereas in reality
your "web_endpoint" will be a full https-url.

Purging old accounts
++++++++++++++++++++++++

The `mailadm prune` command will remove accounts
including the home directories of expired users.
The install-script mentioned above makes systemd
execute a `mailadm-prune` service which runs every hour.

QR code generation
---------------------------

Once you have mailadm configured and integrated with
nginx, postfix and dovecot you can generate a QR code:

    $ mailadm gen-qr oneday
    dcaccount-testrun.org-oneday.png written for token 'oneday'

You can print or hand out this QR code file and people can scan it with
their Delta Chat to get a oneday "burner" account.

Migrating from a pre-mailcow setup
++++++++++++++++++++++++++++++++++

mailadm used to be built on top of a standard postfix/dovecot setup; with
mailcow many things are simplified. The migration can be a bit tricky though.

What you need to do:

* migrate your dovecot accounts to mailadm
* create a master password for dovecot
* do an IMAP sync to migrate all the dovecot accounts to mailcow (see https://mailcow.github.io/mailcow-dockerized-docs/post_installation/firststeps-sync_jobs_migration/)
* migrate the mailadm database (maybe this script works for you: )
* re-initialize the mailadm database with your mailcow credentials (see above: Quick Start)

