# scripts/server/routes/live_peak.py
from flask import Blueprint, request, jsonify, make_response, current_app
from datetime import datetime, timezone
import os
import json
import psycopg2   # pip install psycopg2-binary
from scripts.server.utils.auth import resolve_user_id

bp = Blueprint("live_peak", __name__)


def get_pg_conn():
    """
    Azure PostgreSQL 연결 헬퍼
    🔹 PG_HOST, PG_DB, PG_USER, PG_PASSWORD, PG_PORT 은
       .env / 환경변수에 이미 넣어둔 값 사용
    """
    return psycopg2.connect(
        dbname=os.getenv("PG_DB", "safe_monitoring"),
        user=os.getenv("PG_USER"),
        password=os.getenv("PG_PASSWORD"),
        host=os.getenv("PG_HOST"),
        port=int(os.getenv("PG_PORT", "5432")),
        sslmode="require",
    )


@bp.post("/api/live_peak")
def api_live_peak():
    """10초 구간의 peak dB + 위치를 live_uploads에 저장"""

    resp = make_response()
    user_id, resp, _ = resolve_user_id(resp)
    if not user_id:
        return jsonify({"error": "unauthorized"}), 401

    d = request.get_json(force=True) or {}

    ts = d.get("ts")
    peak_db = d.get("peak_db")
    lat = d.get("lat")
    lng = d.get("lng")
    window_sec = d.get("window_sec")

    # ---- 기본 유효성 검사 ----
    if peak_db is None or lat is None or lng is None:
        return jsonify({"error": "missing lat/lng/peak_db"}), 400

    try:
        peak_db = float(peak_db)
        lat = float(lat)
        lng = float(lng)
    except ValueError:
        return jsonify({"error": "bad number format"}), 400

    # ts가 오면 그걸 쓰고, 없으면 지금 시간 사용
    if ts:
        try:
            created_at = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except Exception:
            created_at = datetime.now(timezone.utc)
    else:
        created_at = datetime.now(timezone.utc)

    # ---- DB INSERT ----
    try:
        conn = get_pg_conn()
        cur = conn.cursor()

        # ⚠️ 여기 컬럼 이름은 실제 live_uploads 스키마에 맞게 조정 필요
        #    (예: audio_url, stt_text, risk_level 등이 NOT NULL이면 같이 넣어야 함)
        cur.execute(
            """
            INSERT INTO live_uploads (
                user_id,
                lat,
                lng,
                peak_volume,
                created_at
            )
            VALUES (%s, %s, %s, %s, %s)
            """,
            (user_id, lat, lng, peak_db, created_at),
        )

        conn.commit()
        cur.close()
        conn.close()

    except Exception as e:
        print("❌ live_peak insert error:", e)
        return jsonify({"error": "db_error"}), 500

    # 기존 패턴 그대로 ALLOW_ANON_UPLOAD 처리
    if current_app.config.get("ALLOW_ANON_UPLOAD"):
        resp.set_data(json.dumps({"ok": True}))
        resp.mimetype = "application/json"
        return resp
    else:
        return jsonify({"ok": True})
