# scripts/server/services/db.py
import sqlite3

def _conn(db_path):
    return sqlite3.connect(db_path)

def init(db_path):
    con = _conn(db_path); cur = con.cursor()
    cur.execute("""
      CREATE TABLE IF NOT EXISTS uploads(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT, blob_name TEXT, ts TEXT,
        size_bytes INTEGER, mime TEXT, ip TEXT
      );
    """)
    con.commit(); con.close()

def log_upload(db_path, user_id, blob_name, ts_iso, size_bytes, mime, ip):
    con = _conn(db_path); cur = con.cursor()
    cur.execute("""INSERT INTO uploads
      (user_id, blob_name, ts, size_bytes, mime, ip)
      VALUES (?, ?, ?, ?, ?, ?)""",
      (user_id, blob_name, ts_iso, size_bytes, mime, ip))
    con.commit(); con.close()
