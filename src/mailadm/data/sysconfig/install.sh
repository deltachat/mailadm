#!/usr/bin/env bash

set -xe

umask 0077
cp mailadm.cfg /home/mailadm/
cp dovecot-sql.conf.ext /home/mailadm/
cp auth-mailadm.conf.ext /etc/dovecot/conf.d/

sudo cp mailadm-web.service mailadm-prune.service /etc/systemd/system/
sudo systemctl enable mailadm-web mailadm-prune
sudo systemctl start mailadm-web mailadm-prune 

