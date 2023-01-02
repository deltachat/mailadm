import logging
def on_starting(server):
    logging.basicConfig(level=logging.INFO)
    from mailadm.app import init_threads
    init_threads()
