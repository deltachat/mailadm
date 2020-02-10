mailadm tool (beta)
======================

mailadm is the reference administration tool for managing
e-mail accounts at https://testrun.org.

On a debian system it allows to run a https-exposed
e-mail account creation service as a wsgi server app
that you can run via systemd (see mailadm.service example).

the http interface has a single ``newtmpuser`` endpoint
which takes a json that contains a shared-secret token_create_user
that must match the secret token with which "mailadm serve" runs.
This secret number is configurable via /etc/mailadm/webservice.json::

    {
       "token_create_user": <secretnumber>,
       "path_virtual_mailboxes": "/etc/postfix/virtual_mailboxes",
       "path_dovecot_users": "/etc/dovecot/users"
    }

