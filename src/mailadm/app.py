"""
help gunicorn and other WSGI servers to instantiate a web instance of mailadm
"""

from .web import create_app_from_db_path

app = create_app_from_db_path()
