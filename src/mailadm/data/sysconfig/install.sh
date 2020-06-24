#!/usr/bin/env bash

set -xe

DIR="$( cd "$( dirname "${{BASH_SOURCE[0]}}" )" >/dev/null 2>&1 && pwd )"

umask 0077
cp $DIR/mailadm.cfg /home/mailadm/
cp $DIR/dovecot-sql.conf.ext /home/mailadm/

sudo cp $DIR/auth-mailadm.conf.ext /etc/dovecot/conf.d/
sudo cp $DIR/mailadm-web.service $DIR/mailadm-prune.service /etc/systemd/system/
sudo systemctl enable mailadm-web mailadm-prune
sudo systemctl start mailadm-web mailadm-prune 

