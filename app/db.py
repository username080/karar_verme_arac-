"""SQLite katmanı (yalnızca standart kütüphane)."""
import os
import sqlite3
from contextlib import closing
from datetime import datetime, timezone

SCHEMA = """
CREATE TABLE IF NOT EXISTS decisions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  notes TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'open',
  chosen_option_id INTEGER,
  decision_reason TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  decided_at TEXT
);
CREATE TABLE IF NOT EXISTS options (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  decision_id INTEGER NOT NULL REFERENCES decisions(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  gains TEXT NOT NULL DEFAULT '',
  losses TEXT NOT NULL DEFAULT '',
  risks TEXT NOT NULL DEFAULT '',
  position INTEGER NOT NULL DEFAULT 0
);
"""

OPTION_FIELDS = ("name", "gains", "losses", "risks")


class NotFound(Exception):
    pass


class BadRequest(Exception):
    pass


def db_path():
    return os.environ.get("DB_PATH", "/data/choices.db")


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def connect():
    path = db_path()
    d = os.path.dirname(os.path.abspath(path))
    os.makedirs(d, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    with closing(connect()) as conn:
        conn.executescript(SCHEMA)
        conn.commit()


def _text(data, key, required=False, default=None):
    """data[key] değerini doğrulanmış str olarak döndürür (yoksa default)."""
    if key not in data or data[key] is None:
        if required:
            raise BadRequest(f"'{key}' gerekli")
        return default
    v = data[key]
    if not isinstance(v, str):
        raise BadRequest(f"'{key}' metin olmalı")
    v = v.strip() if key in ("title", "name") else v
    if required and not v:
        raise BadRequest(f"'{key}' boş olamaz")
    return v


def _decision(conn, row):
    d = dict(row)
    d["options"] = [dict(r) for r in conn.execute(
        "SELECT * FROM options WHERE decision_id=? ORDER BY position, id", (d["id"],))]
    return d


def _get_decision_row(conn, did):
    row = conn.execute("SELECT * FROM decisions WHERE id=?", (did,)).fetchone()
    if row is None:
        raise NotFound("karar bulunamadı")
    return row


def list_decisions():
    with closing(connect()) as conn:
        rows = conn.execute("SELECT * FROM decisions ORDER BY id DESC").fetchall()
        return [_decision(conn, r) for r in rows]


def get_decision(did):
    with closing(connect()) as conn:
        return _decision(conn, _get_decision_row(conn, did))


def create_decision(data):
    title = _text(data, "title", required=True)
    notes = _text(data, "notes", default="")
    with closing(connect()) as conn:
        cur = conn.execute(
            "INSERT INTO decisions (title, notes, created_at) VALUES (?,?,?)",
            (title, notes, now()))
        conn.commit()
        return _decision(conn, _get_decision_row(conn, cur.lastrowid))


def update_decision(did, data):
    title = _text(data, "title")
    if title is not None and not title:
        raise BadRequest("'title' boş olamaz")
    notes = _text(data, "notes")
    with closing(connect()) as conn:
        _get_decision_row(conn, did)
        if title is not None:
            conn.execute("UPDATE decisions SET title=? WHERE id=?", (title, did))
        if notes is not None:
            conn.execute("UPDATE decisions SET notes=? WHERE id=?", (notes, did))
        conn.commit()
        return _decision(conn, _get_decision_row(conn, did))


def delete_decision(did):
    with closing(connect()) as conn:
        _get_decision_row(conn, did)
        conn.execute("DELETE FROM decisions WHERE id=?", (did,))
        conn.commit()


def create_option(did, data):
    name = _text(data, "name", required=True)
    vals = [_text(data, k, default="") for k in OPTION_FIELDS[1:]]
    with closing(connect()) as conn:
        _get_decision_row(conn, did)
        pos = conn.execute(
            "SELECT COALESCE(MAX(position), -1) + 1 FROM options WHERE decision_id=?",
            (did,)).fetchone()[0]
        cur = conn.execute(
            "INSERT INTO options (decision_id, name, gains, losses, risks, position)"
            " VALUES (?,?,?,?,?,?)", (did, name, *vals, pos))
        conn.commit()
        return dict(conn.execute("SELECT * FROM options WHERE id=?", (cur.lastrowid,)).fetchone())


def update_option(oid, data):
    changes = {}
    for k in OPTION_FIELDS:
        v = _text(data, k)
        if v is not None:
            if k == "name" and not v:
                raise BadRequest("'name' boş olamaz")
            changes[k] = v
    with closing(connect()) as conn:
        if conn.execute("SELECT 1 FROM options WHERE id=?", (oid,)).fetchone() is None:
            raise NotFound("seçenek bulunamadı")
        for k, v in changes.items():
            conn.execute(f"UPDATE options SET {k}=? WHERE id=?", (v, oid))
        conn.commit()
        return dict(conn.execute("SELECT * FROM options WHERE id=?", (oid,)).fetchone())


def delete_option(oid):
    with closing(connect()) as conn:
        row = conn.execute("SELECT decision_id FROM options WHERE id=?", (oid,)).fetchone()
        if row is None:
            raise NotFound("seçenek bulunamadı")
        conn.execute(
            "UPDATE decisions SET status='open', chosen_option_id=NULL,"
            " decision_reason='', decided_at=NULL WHERE chosen_option_id=?", (oid,))
        conn.execute("DELETE FROM options WHERE id=?", (oid,))
        conn.commit()


def decide(did, data):
    oid = data.get("option_id")
    if not isinstance(oid, int) or isinstance(oid, bool):
        raise BadRequest("'option_id' tam sayı olmalı")
    reason = _text(data, "reason", default="")
    with closing(connect()) as conn:
        _get_decision_row(conn, did)
        if conn.execute("SELECT 1 FROM options WHERE id=? AND decision_id=?",
                        (oid, did)).fetchone() is None:
            raise BadRequest("seçenek bu karara ait değil")
        conn.execute(
            "UPDATE decisions SET status='decided', chosen_option_id=?,"
            " decision_reason=?, decided_at=? WHERE id=?", (oid, reason, now(), did))
        conn.commit()
        return _decision(conn, _get_decision_row(conn, did))


def reopen(did):
    with closing(connect()) as conn:
        _get_decision_row(conn, did)
        conn.execute(
            "UPDATE decisions SET status='open', chosen_option_id=NULL,"
            " decision_reason='', decided_at=NULL WHERE id=?", (did,))
        conn.commit()
        return _decision(conn, _get_decision_row(conn, did))
