import logging


def on_starting(_server):
    logging.basicConfig(level=logging.INFO)
    from mailadm.app import init_threads

    init_threads()
