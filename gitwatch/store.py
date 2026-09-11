import contextlib
import json
import os
from pathlib import Path
import sqlite3
import threading
import time

DEFAULT_SETTINGS = {
    'github_token': '', 'telegram_token': '', 'username': '', 'bot_username': '',
    'chat_id': 0, 'binding_after': 0, 'offset': 0, 'generation': 0, 'revision': 0,
}


class Store:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path = self.directory / 'gitwatch.sqlite3'
        self.lock = threading.RLock()
        with self.transaction() as db:
            db.executescript('''
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS settings (id INTEGER PRIMARY KEY CHECK(id=1), value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS repos (
                    id INTEGER PRIMARY KEY, full_name TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    url TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
                    mode TEXT NOT NULL DEFAULT 'all', branch TEXT NOT NULL DEFAULT '',
                    interval_minutes INTEGER NOT NULL DEFAULT 5, enabled INTEGER NOT NULL DEFAULT 1,
                    heads TEXT NOT NULL DEFAULT '{}', initialized INTEGER NOT NULL DEFAULT 0,
                    last_checked REAL, next_check REAL NOT NULL DEFAULT 0, last_change REAL,
                    last_error TEXT NOT NULL DEFAULT '', revision INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY, repo_id INTEGER REFERENCES repos(id) ON DELETE SET NULL,
                    full_name TEXT NOT NULL, branch TEXT NOT NULL, kind TEXT NOT NULL,
                    old_sha TEXT NOT NULL DEFAULT '', sha TEXT NOT NULL DEFAULT '',
                    summary TEXT NOT NULL DEFAULT '', author TEXT NOT NULL DEFAULT '',
                    commit_count INTEGER, url TEXT NOT NULL, created REAL NOT NULL,
                    delivery TEXT NOT NULL, generation INTEGER NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0, next_attempt REAL NOT NULL DEFAULT 0,
                    error TEXT NOT NULL DEFAULT ''
                );
                CREATE INDEX IF NOT EXISTS events_delivery_next ON events(delivery, next_attempt);
                CREATE INDEX IF NOT EXISTS events_created ON events(created);
            ''')
            db.execute('INSERT OR IGNORE INTO settings VALUES (1,?)', (json.dumps(DEFAULT_SETTINGS),))
        if os.name != 'nt':
            os.chmod(self.directory, 0o700)
            os.chmod(self.path, 0o600)

    @contextlib.contextmanager
    def transaction(self):
        with self.lock:
            db = sqlite3.connect(self.path, timeout=20)
            db.row_factory = sqlite3.Row
            db.execute('PRAGMA foreign_keys=ON')
            try:
                with db:
                    yield db
            finally:
                db.close()

    def settings(self, db=None):
        if db is not None:
            return {**DEFAULT_SETTINGS, **json.loads(db.execute('SELECT value FROM settings WHERE id=1').fetchone()[0])}
        with self.transaction() as db:
            return self.settings(db)

    def save_settings(self, value, db):
        db.execute('UPDATE settings SET value=? WHERE id=1', (json.dumps(value),))

    def meta(self, key, default=None):
        with self.transaction() as db:
            row = db.execute('SELECT value FROM meta WHERE key=?', (key,)).fetchone()
            return json.loads(row[0]) if row else default

    def put_meta(self, key, value):
        with self.transaction() as db:
            db.execute('INSERT INTO meta VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value', (key, json.dumps(value)))

    def repos(self):
        with self.transaction() as db:
            return [dict(row) for row in db.execute('SELECT * FROM repos ORDER BY id DESC')]

    def repo(self, repo_id, db=None):
        if db is not None:
            row = db.execute('SELECT * FROM repos WHERE id=?', (repo_id,)).fetchone()
            return dict(row) if row else None
        with self.transaction() as db:
            return self.repo(repo_id, db)

    def events(self, limit=60, before=None):
        with self.transaction() as db:
            return [dict(row) for row in db.execute('SELECT * FROM events WHERE id<? ORDER BY id DESC LIMIT ?', (before or 2**63-1, limit))]

    def prune(self):
        with self.transaction() as db:
            db.execute("DELETE FROM events WHERE created<? AND delivery!='pending'", (time.time()-90*86400,))

    def backup(self, destination):
        with self.lock:
            with contextlib.closing(sqlite3.connect(self.path)) as src, contextlib.closing(sqlite3.connect(destination)) as dst:
                src.backup(dst)
