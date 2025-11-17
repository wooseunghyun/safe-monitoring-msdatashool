import psycopg2
import os
import logging
import psycopg2.extras


def get_conn():
    return psycopg2.connect(
        host=os.getenv("PG_HOST"),
        database=os.getenv("PG_DB"),
        user=os.getenv("PG_USER"),
        password=os.getenv("PG_PASSWORD"),
        port=os.getenv("PG_PORT", "5432"),
        sslmode="require",
    )

def get_latest_alert(user_id: str):
    conn = get_conn()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """
            SELECT *
              FROM alerts
             WHERE user_id = %s
               AND (is_cancelled IS FALSE OR is_cancelled IS NULL)
             ORDER BY id DESC
             LIMIT 1
            """,
            (user_id,),
        )
        row = cur.fetchone()
        cur.close()
        return row
    finally:
        conn.close()


def cancel_all_alerts(user_id: str) -> bool:
    """
    사용자의 모든 미취소 ALERT들을 한 번에 취소한다.
    """
    try:
        conn = get_conn()
        cur = conn.cursor()

        cur.execute("""
            UPDATE alerts
            SET
                is_cancelled = TRUE,
                cancelled_at = NOW()
            WHERE
                user_id = %s
                AND ai_decision = 'ALERT'
                AND (is_cancelled IS NULL OR is_cancelled = FALSE);
        """, (user_id,))
        
        updated = cur.rowcount
        conn.commit()
        cur.close()
        conn.close()

        # 0개 업데이트면 False 반환
        return updated > 0

    except Exception as e:
        logging.error("[cancel_all_alerts] ERROR: %s", e)
        return False