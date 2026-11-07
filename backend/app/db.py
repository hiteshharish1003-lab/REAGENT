import json
import sqlite3
import time
from contextlib import contextmanager

from .config import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
  id TEXT PRIMARY KEY,
  topic TEXT NOT NULL,
  mode TEXT NOT NULL,
  status TEXT NOT NULL,
  created_at REAL NOT NULL,
  report TEXT,
  sources TEXT,
  analysis TEXT,
  stats TEXT,
  usage TEXT
);
CREATE TABLE IF NOT EXISTS events (
  run_id TEXT NOT NULL,
  seq INTEGER NOT NULL,
  type TEXT NOT NULL,
  data TEXT NOT NULL,
  ts REAL NOT NULL,
  PRIMARY KEY (run_id, seq)
);
CREATE TABLE IF NOT EXISTS documents (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  sha TEXT NOT NULL UNIQUE,
  pages INTEGER NOT NULL,
  chars INTEGER NOT NULL,
  chunks INTEGER NOT NULL,
  created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS chunks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  doc_id INTEGER NOT NULL,
  ord INTEGER NOT NULL,
  page INTEGER NOT NULL,
  text TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS chunks_doc ON chunks (doc_id);
CREATE VIRTUAL TABLE IF NOT EXISTS chunk_fts USING fts5(text, tokenize='porter unicode61');
CREATE TABLE IF NOT EXISTS doc_qa (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  question TEXT NOT NULL,
  result TEXT NOT NULL,
  created_at REAL NOT NULL
);
"""


@contextmanager
def conn():
    c = sqlite3.connect(settings.db_path)
    c.row_factory = sqlite3.Row
    try:
        yield c
        c.commit()
    finally:
        c.close()


def init() -> None:
    with conn() as c:
        c.executescript(SCHEMA)


def create_run(run_id: str, topic: str, mode: str) -> None:
    with conn() as c:
        c.execute(
            "INSERT INTO runs (id, topic, mode, status, created_at) VALUES (?,?,?,?,?)",
            (run_id, topic, mode, "planning", time.time()),
        )


def update_run(run_id: str, **fields) -> None:
    if not fields:
        return
    cols = ", ".join(f"{k}=?" for k in fields)
    vals = [v if isinstance(v, (str, int, float, type(None))) else json.dumps(v) for v in fields.values()]
    with conn() as c:
        c.execute(f"UPDATE runs SET {cols} WHERE id=?", (*vals, run_id))


def add_event(run_id: str, seq: int, type_: str, data: dict, ts: float) -> None:
    with conn() as c:
        c.execute(
            "INSERT INTO events (run_id, seq, type, data, ts) VALUES (?,?,?,?,?)",
            (run_id, seq, type_, json.dumps(data), ts),
        )


def list_runs() -> list[dict]:
    with conn() as c:
        rows = c.execute(
            "SELECT id, topic, mode, status, created_at, stats FROM runs ORDER BY created_at DESC LIMIT 50"
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["stats"] = json.loads(d["stats"]) if d["stats"] else None
        out.append(d)
    return out


def get_run(run_id: str) -> dict | None:
    with conn() as c:
        row = c.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
        if not row:
            return None
        events = c.execute(
            "SELECT seq, type, data, ts FROM events WHERE run_id=? ORDER BY seq", (run_id,)
        ).fetchall()
    d = dict(row)
    for k in ("report", "sources", "analysis", "stats", "usage"):
        d[k] = json.loads(d[k]) if d[k] else None
    d["events"] = [
        {"seq": e["seq"], "type": e["type"], "data": json.loads(e["data"]), "ts": e["ts"]}
        for e in events
    ]
    return d


def delete_run(run_id: str) -> None:
    with conn() as c:
        c.execute("DELETE FROM events WHERE run_id=?", (run_id,))
        c.execute("DELETE FROM runs WHERE id=?", (run_id,))


def fail_interrupted() -> None:
    """Runs left mid-flight by a server restart can never resume; mark them so the UI does not wait forever."""
    now = time.time()
    with conn() as c:
        rows = c.execute("SELECT id FROM runs WHERE status NOT IN ('done','error')").fetchall()
        for r in rows:
            seq = c.execute("SELECT COALESCE(MAX(seq), -1) + 1 FROM events WHERE run_id=?", (r["id"],)).fetchone()[0]
            c.execute(
                "INSERT INTO events (run_id, seq, type, data, ts) VALUES (?,?,?,?,?)",
                (r["id"], seq, "error", json.dumps({"message": "Run was interrupted by a server restart."}), now),
            )
            c.execute("UPDATE runs SET status='error' WHERE id=?", (r["id"],))
