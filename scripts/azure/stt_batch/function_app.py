import azure.functions as func
import datetime
import json
import logging
import os
import logging
import psycopg2
from typing import Tuple, Optional, List
import requests

# 함수 앱 엔트리
app = func.FunctionApp()


def get_conn():
    """Azure PostgreSQL 접속용 헬퍼"""
    return psycopg2.connect(
        dbname=os.getenv("PG_DB"),
        user=os.getenv("PG_USER"),
        password=os.getenv("PG_PASSWORD"),
        host=os.getenv("PG_HOST"),
        port=os.getenv("PG_PORT"),
        sslmode="require",  # Azure PostgreSQL이면 보통 필요
    )


# -----------------------------
# Kakao 역지오코딩 헬퍼
# -----------------------------
KAKAO_KEY = os.getenv("KAKAO_REST_API_KEY")

def get_region_from_kakao(lat: float, lng: float) -> Tuple[Optional[str], Optional[str]]:
    """lat/lng → (구 이름, 동 이름)"""
    if not KAKAO_KEY:
        logging.warning("KAKAO_REST_API_KEY not set; skip region lookup")
        return None, None

    url = "https://dapi.kakao.com/v2/local/geo/coord2address.json"
    headers = {"Authorization": f"KakaoAK {KAKAO_KEY}"}
    params = {"x": lng, "y": lat}

    try:
        resp = requests.get(url, headers=headers, params=params, timeout=3)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logging.warning(f"Kakao API error for ({lat}, {lng}): {e}")
        return None, None

    docs = data.get("documents", [])
    if not docs:
        return None, None

    addr = docs[0].get("address") or docs[0].get("road_address")
    if not addr:
        return None, None

    gu = addr.get("region_2depth_name")   # 예: 종로구
    dong = addr.get("region_3depth_name") # 예: 사직동
    return gu, dong


# -----------------------------
# STT 텍스트 위험도 & 플래그 계산
# -----------------------------
def classify_risk(stt_text: Optional[str]):
    text = stt_text or ""

    has_help_kw = any(kw in text for kw in ["도와", "살려", "위험"])
    has_violence_kw = any(kw in text for kw in ["죽이", "때리", "칼", "총"])
    has_threat_kw = any(kw in text for kw in ["가만히 있", "움직이", "죽고 싶"])
    has_sexual_kw = any(kw in text for kw in ["만지지 마", "싫어", "하지 마"])
    has_kidnap_kw = any(kw in text for kw in ["놓아", "문 열", "갇혔", "잡혔"])
    has_child_kw = any(kw in text for kw in ["엄마", "아빠", "무서"])
    has_emotion_kw = any(kw in text for kw in ["안 돼", "그만", "하지 마"])
    has_report_kw = any(kw in text for kw in ["119", "경찰", "신고"])
    has_abuse_kw = any(kw in text for kw in ["죽어", "이 자식", "꺼져", "미쳤"])
    has_accident_kw = any(kw in text for kw in ["피", "쓰러졌", "불났", "다쳤"])

    # 위험도 우선순위: HIGH > MEDIUM > LOW > NONE
    if has_help_kw or has_violence_kw:
        risk_level = "HIGH"
    elif has_threat_kw or has_sexual_kw or has_kidnap_kw or has_child_kw:
        risk_level = "MEDIUM"
    elif (
        has_emotion_kw
        or has_report_kw
        or has_abuse_kw
        or has_accident_kw
    ):
        risk_level = "LOW"
    else:
        risk_level = "NONE"

    return {
        "risk_level": risk_level,
        "has_help_kw": has_help_kw,
        "has_violence_kw": has_violence_kw,
        "has_threat_kw": has_threat_kw,
        "has_sexual_kw": has_sexual_kw,
        "has_kidnap_kw": has_kidnap_kw,
        "has_child_kw": has_child_kw,
        "has_emotion_kw": has_emotion_kw,
        "has_report_kw": has_report_kw,
        "has_abuse_kw": has_abuse_kw,
        "has_accident_kw": has_accident_kw,
    }


# -----------------------------
# 타이머 트리거 함수
# -----------------------------
@app.timer_trigger(
    # schedule="*/30 * * * * *",  # 30초마다
    schedule="0 */10 * * * *",  # 10분마다
    arg_name="myTimer",
    run_on_startup=False,
    use_monitor=False,
)
def stt_batch_job(myTimer: func.TimerRequest) -> None:
    logging.info("⏱️ STT batch timer triggered")

    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                # 1) 10분 지난 live_uploads 로우 가져오기
                cur.execute(
                    """
                    SELECT id, lat, lng, stt_text, peak_volume, created_at
                    FROM live_uploads
                    WHERE created_at < NOW() - INTERVAL '10 minutes'
                    """
                )
                rows: List[tuple] = cur.fetchall()

                if not rows:
                    logging.info("No rows to process.")
                    return

                logging.info(f"Processing {len(rows)} rows from live_uploads")

                processed_ids = []

                for (row_id, lat, lng, stt_text, peak_volume, created_at) in rows:
                    # 2) 카카오에서 행정구 정보 가져오기
                    gu_name, dong_name = get_region_from_kakao(lat, lng)

                    # 3) 위험도 및 플래그 계산
                    risk = classify_risk(stt_text)

                    # 4) analytics 테이블에 INSERT
                    cur.execute(
                        """
                        INSERT INTO stt_events_analytics (
                            lat, lng, ts, stt_text, risk_level,
                            has_help_kw, has_violence_kw, has_threat_kw,
                            has_sexual_kw, has_kidnap_kw, has_child_kw,
                            has_emotion_kw, has_report_kw, has_abuse_kw,
                            has_accident_kw, peak_volume,
                            gu_name, dong_name
                        )
                        VALUES (
                            %s, %s, %s, %s, %s,
                            %s, %s, %s,
                            %s, %s, %s,
                            %s, %s, %s,
                            %s, %s,
                            %s, %s
                        )
                        """,
                        (
                            lat,
                            lng,
                            created_at,  # ts
                            stt_text,
                            risk["risk_level"],
                            risk["has_help_kw"],
                            risk["has_violence_kw"],
                            risk["has_threat_kw"],
                            risk["has_sexual_kw"],
                            risk["has_kidnap_kw"],
                            risk["has_child_kw"],
                            risk["has_emotion_kw"],
                            risk["has_report_kw"],
                            risk["has_abuse_kw"],
                            risk["has_accident_kw"],
                            peak_volume,
                            gu_name,
                            dong_name,
                        ),
                    )

                    processed_ids.append(row_id)

                # 5) 처리한 live_uploads 삭제
                if processed_ids:
                    cur.execute(
                        "DELETE FROM live_uploads WHERE id = ANY(%s)",
                        (processed_ids,),
                    )

        logging.info("✅ STT batch job completed successfully")

    except Exception as e:
        logging.error(f"❌ STT batch job failed: {e}")