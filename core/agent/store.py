"""Separate SQLite audit store; session epochs prevent a cleared run being restored."""
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from .runtime import redact, scrub


class AgentStore:
    def __init__(self,path=None):
        self.path=Path(path or Path(__file__).resolve().parents[2]/'data/campus_agent.db')
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.connect() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS agent_sessions(session_id TEXT PRIMARY KEY, epoch INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS agent_runs(id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT UNIQUE,
              session_id TEXT NOT NULL, question TEXT NOT NULL, result TEXT NOT NULL,
              created_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE INDEX IF NOT EXISTS agent_session_idx ON agent_runs(session_id,id);
            ''')

    @contextmanager
    def connect(self):
        db=sqlite3.connect(str(self.path),timeout=10)
        db.row_factory=sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def version(self,session):
        with self.connect() as db:
            db.execute('INSERT OR IGNORE INTO agent_sessions(session_id) VALUES (?)',(session,))
            return db.execute('SELECT epoch FROM agent_sessions WHERE session_id=?',(session,)).fetchone()[0]

    def save(self,session,question,result,version):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT epoch FROM agent_sessions WHERE session_id=?',(session,)).fetchone()
            if row is None or row[0]!=version:return False
            db.execute('INSERT INTO agent_runs(run_id,session_id,question,result) VALUES (?,?,?,?)',
                (result['agent']['run_id'],session,redact(question),json.dumps(scrub(result),ensure_ascii=False)))
            return True

    def history(self,session,limit=12):
        with self.connect() as db:
            rows=db.execute('SELECT run_id,question,result,created_at FROM agent_runs WHERE session_id=? ORDER BY id DESC LIMIT ?',
                            (session,max(1,min(limit,200)))).fetchall()
        return [{**dict(row),'result':json.loads(row['result'])} for row in reversed(rows)]

    def sessions(self,limit=100):
        with self.connect() as db:
            rows=db.execute('''SELECT session_id,COUNT(*) AS turn_count,MAX(created_at) AS updated_at,
                (SELECT question FROM agent_runs first WHERE first.session_id=r.session_id ORDER BY id LIMIT 1) AS title
                FROM agent_runs r GROUP BY session_id ORDER BY MAX(id) DESC LIMIT ?''',
                (max(1,min(limit,100)),)).fetchall()
        return [dict(row) for row in rows]

    def clear(self,session=None):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if session:
                db.execute('INSERT OR IGNORE INTO agent_sessions(session_id) VALUES (?)',(session,))
                db.execute('UPDATE agent_sessions SET epoch=epoch+1 WHERE session_id=?',(session,))
                result=db.execute('DELETE FROM agent_runs WHERE session_id=?',(session,))
            else:
                db.execute('UPDATE agent_sessions SET epoch=epoch+1')
                result=db.execute('DELETE FROM agent_runs')
            return result.rowcount
