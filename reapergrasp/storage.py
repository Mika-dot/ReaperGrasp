"""Local transactional event journal; images and results commit together."""
from contextlib import contextmanager
import json
import shutil
import sqlite3
import time
from pathlib import Path


class EventStore:
    def __init__(self,root,settings):
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True)
        self.path=self.root/'events.sqlite';self.settings=settings
        with self.connect() as db:
            db.execute('PRAGMA auto_vacuum=INCREMENTAL')
            db.execute('PRAGMA journal_mode=WAL')
            db.execute('CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY, created REAL NOT NULL, camera TEXT NOT NULL, state TEXT NOT NULL, result TEXT NOT NULL, jpeg BLOB NOT NULL)')
            db.execute('CREATE INDEX IF NOT EXISTS event_time ON events(created)')
        self.cleanup()

    @contextmanager
    def connect(self):
        db=sqlite3.connect(self.path,timeout=3)
        db.execute('PRAGMA synchronous=FULL')
        try:
            with db:yield db
        finally:db.close()

    def cleanup(self):
        with self.connect() as db:
            db.execute('DELETE FROM events WHERE created < ?',(time.time()-86400*self.settings.retention_days,))
            db.execute('DELETE FROM events WHERE id NOT IN (SELECT id FROM events ORDER BY id DESC LIMIT ?)',(self.settings.max_events,))
            db.execute('PRAGMA incremental_vacuum(256)')

    def record(self,camera,result,jpeg):
        if shutil.disk_usage(self.root).free<self.settings.min_free_mb*1024**2:
            self.cleanup()
            if shutil.disk_usage(self.root).free<self.settings.min_free_mb*1024**2:raise OSError('Недостаточно свободного места для журнала')
        with self.connect() as db:
            cur=db.execute('INSERT INTO events(created,camera,state,result,jpeg) VALUES(?,?,?,?,?)',(time.time(),camera,result['state'],json.dumps(result,ensure_ascii=False,allow_nan=False),jpeg))
            event_id=cur.lastrowid
        self.cleanup()
        return event_id

    def list(self,limit=100):
        with self.connect() as db:
            rows=db.execute('SELECT id,created,camera,state,result FROM events ORDER BY id DESC LIMIT ?',(min(100,max(1,limit)),)).fetchall()
        return [dict(id=r[0],created=r[1],camera=r[2],state=r[3],result=json.loads(r[4])) for r in rows]

    def image(self,event_id):
        with self.connect() as db:
            row=db.execute('SELECT jpeg FROM events WHERE id=?',(event_id,)).fetchone()
        return row[0] if row else None
