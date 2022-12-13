"""
help gunicorn and other WSGI servers to instantiate a web instance of mailadm
"""
from .web import create_app_from_db_path
import threading
from .db import get_db_path, DB
from mailadm.bot import main as run_bot
from mailadm.bot import get_admbot_db_path


def init_threads():
    botthread = threading.Thread(target=run_bot, args=(DB(get_db_path()), get_admbot_db_path()),
                                 daemon=True, name="bot")
    botthread.start()


app = create_app_from_db_path()
