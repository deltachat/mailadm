def on_starting(server):
    from mailadm.app import init_threads
    init_threads()
