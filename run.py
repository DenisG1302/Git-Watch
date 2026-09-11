import os
import logging
from gitwatch.web import create_app

if __name__ == '__main__':
    from waitress import serve
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(name)s: %(message)s')
    app = create_app()
    watcher = app.extensions['watcher']
    if os.name != 'nt':
        import fcntl
        process_lock = open(watcher.store.directory/'process.lock','w')
        try:
            fcntl.flock(process_lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit('Git Watch is already running for this data directory.') from None
    watcher.start()
    serve(app, host=os.getenv('GITWATCH_HOST', '127.0.0.1'), port=int(os.getenv('GITWATCH_PORT', '8788')), threads=8, url_scheme='http')
