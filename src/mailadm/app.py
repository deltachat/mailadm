"""
help gunicorn and other WSGI servers to instantiate a web instance of mailadm
"""

import os
from .web import create_app_from_file

TADM_SYSCONFIG_PATH = "/etc/mailadm/mailadm.cfg"

config_fn = os.environ.get("MAILADM_CONFIG")
if config_fn is None and os.path.exists(TADM_SYSCONFIG_PATH):
    config_fn = TADM_SYSCONFIG_PATH

if not config_fn:
    raise RuntimeError("could not find config file")

app = create_app_from_file(config_fn)
