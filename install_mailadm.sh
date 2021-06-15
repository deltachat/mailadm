#!/usr/bin/env bash

# mailadm installation script for Debian/Ubuntu 
#
# The idea of this script is that it is idempotent: you can repeatedly
# call it and it doesn't bark. It will keep existing state. 
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
export MAIL_DOMAIN=example.org

export VMAIL_USER=vmail 
export VMAIL_HOME=/home/vmail 

export MAILADM_USER=mailadm 
export MAILADM_HOME=/var/lib/mailadm
export WEB_ENDPOINT=https://example.org/new_email
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
    useradd --no-log-init --system --home-dir $MAILADM_HOME $MAILADM_USER
    echo "export MAILADM_DB=$MAILADM_HOME/mailadm.db" >> $MAILADM_HOME/.bashrc
    echo "cd ~" >> $MAILADM_HOME/.bashrc
    echo "source venv/bin/activate" >> $MAILADM_HOME/.bashrc
else
    echo "** mailadm user already exists, using it"
fi

echo "** fixing permissions"
umask 0022
chown -R $MAILADM_USER:$VMAIL_USER $MAILADM_HOME
chmod ug+rwx $MAILADM_HOME

python3 -m venv $MAILADM_HOME/venv
$MAILADM_HOME/venv/bin/pip install -U -q pip
$MAILADM_HOME/venv/bin/pip install -U -q .

export MAILADM_DB=$MAILADM_HOME/mailadm.db

$MAILADM_HOME/venv/bin/mailadm init \
    --web-endpoint=$WEB_ENDPOINT \
    --mail-domain=$MAIL_DOMAIN \
    --vmail-user=$VMAIL_USER 

# allow vmail user (which runs mailadm-prune job) to write to db 
chown $MAILADM_USER:$VMAIL_USER $MAILADM_DB
chmod ug+rw $MAILADM_DB

$MAILADM_HOME/venv/bin/mailadm gen-sysconfig \
    --localhost-web-port=$LOCALHOST_WEB_PORT \
    --mailadm-user $MAILADM_USER


systemctl daemon-reload 
systemctl enable mailadm-web mailadm-prune mailadm-last_seen
systemctl restart mailadm-web  mailadm-prune mailadm-last_seen

# :todo
# create mail address for sending out messages to users
# simplebot init to send out messages to users
# ask user whether they want to use the admin group
# if yes, show an invite QR code for the admin group

# allow g+w for virtual_mailboxes
# create /usr/bin/mailadm caller script, so other users in the vmail & mailadm groups can run this as well

