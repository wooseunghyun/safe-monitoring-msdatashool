# scripts/server/services/db.py
import sqlite3

def _conn(db_path):
    return sqlite3.connect(db_path)

def init(db_path):
    con = _conn(db_path)
    cur = con.cursor()

    # 1) 기본 테이블 없으면 생성
    cur.execute("""
      CREATE TABLE IF NOT EXISTS uploads(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id   TEXT,
        blob_name TEXT,
        ts        TEXT,
        size_bytes INTEGER,
        mime      TEXT,
        ip        TEXT
      );
    """)

    # 2) 이미 있는 테이블이라도 lat / lon 컬럼 없으면 추가
    cur.execute("PRAGMA table_info(uploads)")
    cols = [row[1] for row in cur.fetchall()]  # row[1] = column name

    if "lat" not in cols:
        cur.execute("ALTER TABLE uploads ADD COLUMN lat REAL")

    if "lon" not in cols:
        cur.execute("ALTER TABLE uploads ADD COLUMN lon REAL")

    con.commit()
    con.close()

def log_upload(db_path, user_id, blob_name, ts_iso, size_bytes, mime, ip, lat=None, lon=None):
    con = _conn(db_path)
    cur = con.cursor()
    cur.execute("""
      INSERT INTO uploads
        (user_id, blob_name, ts, size_bytes, mime, ip, lat, lon)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (user_id, blob_name, ts_iso, size_bytes, mime, ip, lat, lon))
    con.commit()
    con.close()
