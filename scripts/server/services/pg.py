# scripts/server/services/pg.py
import os
import psycopg2

def get_pg_conn():
    return psycopg2.connect(
        dbname=os.getenv("PG_DB", "safe_monitoring"),
        user=os.getenv("PG_USER"),
        password=os.getenv("PG_PASSWORD"),
        host=os.getenv("PG_HOST"),
        port=int(os.getenv("PG_PORT", "5432")),
        sslmode="require",
    )
