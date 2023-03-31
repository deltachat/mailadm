Unreleased
-------------

0.12.0
------

- added the bot interface for giving mailadm commands via chat

0.11.0
------

- breaking change: mailadm now uses mailcow REST API for creating/manipulating e-mail accounts instead of fiddling with postfix/dovecot config
- deprecate dovecot/postfix support
- provider instructions for docker setup

0.10.5
-------------

- fix permission issue in install and readme

- make "mailadm-prune" systemd service run as vmail user
  and set group for mailadm.db as vmail user.

0.10.4
-------------

- fix #15 using a mailadm user not named "mailadm"
- fix various little errors

0.10.3
-------------

- fix computing the user vmail dir

0.10.2
-------------

- add mod-token command to modify parameters of a token

0.10.1
-------------

- fixed tokens to not contain special chars

0.10.0
-------------

- revamped configuration and documentation

- now all config/state is in a sqlite database
  see also new "mailadm config" subcommand

- mailadm now has root-less operations

- gen-qr subcommand creates a QR code with basic explanation text

- rename subcommand "add-local-user" to "add-user"
  because virtually all command line options are local-options

- add "add-token/del-token" sub commands

- rename subcommand "prune-expired" to "prune"
  because pruning is about expired accounts

- use setuptools_scm for automatic versioning

- added circle-ci config for running python tests


0.9.0
---------------

initial release
