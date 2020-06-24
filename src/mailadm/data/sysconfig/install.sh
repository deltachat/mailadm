#!/usr/bin/env bash

set -xe

DIR="$( cd "$( dirname "${{BASH_SOURCE[0]}}" )" >/dev/null 2>&1 && pwd )"

umask 0077
cp $DIR/mailadm.cfg /home/mailadm/
cp $DIR/dovecot-sql.conf.ext /home/mailadm/
chown {mailadm_user} /home/mailadm/{{dovecot-sql.conf.ext,mailadm.cfg}}

cp $DIR/auth-mailadm.conf.ext /etc/dovecot/conf.d/
cp $DIR/mailadm-web.service $DIR/mailadm-prune.service /etc/systemd/system/
systemctl enable mailadm-web mailadm-prune
systemctl start mailadm-web mailadm-prune 

