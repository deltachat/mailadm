

systemctl stop mailadm-web
systemctl stop mailadm-prune
systemctl disable mailadm-prune
systemctl disable mailadm-web

userdel -r mailadm 
groupdel mailadm 

# XXX removing dovecot, systemd config missing
