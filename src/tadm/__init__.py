import os
from .web import create_app_from_file

__version__ = "0.1"

config_fn = os.environ.get("TADM_CONFIG")
if config_fn is None and os.path.exists("/etc/tadm/tadm.cfg"):
    config_fn = "/etc/tadm/tadm.cfg"

if config_fn:
    app = create_app_from_file(config_fn)
