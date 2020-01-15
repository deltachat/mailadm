import os
from .web import create_app_from_file

__version__ = "0.1"

config_fn = os.environ.get("TADM_APP_CONFIG_FILENAME")
if config_fn is None and os.path.exists("/etc/tadm/webconfig.json"):
    config_fn = "/etc/tadm/webconfig.json"

if config_fn:
    app = create_app_from_file(config_fn)
