
# buster is newer but mailadm should run on older systems anyway 
FROM bitnami/minideb:stretch

RUN install_packages dovecot-core
RUN install_packages postfix 
RUN install_packages python-tox python3-pip git
RUN install_packages make
