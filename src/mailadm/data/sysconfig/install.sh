#!/usr/bin/env bash

umask 0077
cp mailadm.cfg {mailadm_homedir}/
cp auth-mailadm.conf.ext {dovecot_conf_d}/
cp dovecot-sql.conf.ext {mailadm_homedir}/

cp mailadm-prune.service {systemd}/
cp mailadm-web.service {systemd}/
