#!/usr/bin/env bash

# mailadm installation script for Debian/Ubuntu 
#
# The idea of this script is that it is idempotent: you can repeatedly
# call it and it doesn't bark.  It will keep existing state. 
# mailadm has an internal automatic database-upgrade mechanism
# but you can't downgrade mailadm versions safely. 
#
# You may adjust variables at the top. 

if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root" 
   exit 1
fi

set -xe

# modify the following variables 
export WEB_ENDPOINT=https://example.org/new_email
export MAIL_DOMAIN=example.org

export VMAIL_USER=vmail 
export MAILADM_USER=mailadm 
export MAILADM_HOME=/var/lib/mailadm
export LOCALHOST_WEB_PORT=3691

# check if vmail user exists
if ! getent passwd $VMAIL_USER > /dev/null 2>&1; then
    echo "user $VMAIL_USER does not exist, do you have a doveocot virtual user setup?"
    exit 1
fi

# check if mailadm user exists 
if ! getent passwd $MAILADM_USER > /dev/null 2>&1; then
    echo "** adding mailadm user"
    mkdir -p $MAILADM_HOME
    useradd --no-log-init --system --home-dir $MAILADM_HOME --groups $VMAIL_USER $MAILADM_USER
    chown -R $MAILADM_USER $MAILADM_HOME 
else
    echo "** adding vmail group to mailadm user"
    usermod -G vmail $MAILADM_USER 
fi

umask 0022
chown -R $MAILADM_USER $MAILADM_HOME
chmod ug+rwx $MAILADM_HOME

python3 -m venv $MAILADM_HOME/venv
$MAILADM_HOME/venv/bin/pip install -q .

$MAILADM_HOME/venv/bin/mailadm init \
    --web-endpoint=$WEB_ENDPOINT \
    --mail-domain=$MAIL_DOMAIN \
    --vmail-user=$VMAIL_USER 
chown $MAILADM_USER $MAILADM_HOME/mailadm.db
chmod ug+rw $MAILADM_HOME/mailadm.db

$MAILADM_HOME/venv/bin/mailadm gen-sysconfig \
    --localhost-web-port=$LOCALHOST_WEB_PORT \

systemctl daemon-reload 
systemctl enable mailadm-web mailadm-prune
systemctl restart mailadm-web  mailadm-prune 
