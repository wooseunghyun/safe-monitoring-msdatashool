# function_app.py
import os
import json
import logging
from datetime import datetime, timedelta, timezone

import azure.functions as func
import psycopg2
from openai import AzureOpenAI

app = func.FunctionApp()

COOLDOWN_SECONDS = int(os.getenv("ALERT_COOLDOWN_SEC", "60"))  # 기본 60초

def analyze_with_openai(user_id: str, logs):
    """
    logs: [(created_at, stt_text, risk_level), ...]
    반환: (decision, reason)
    decision: "ALERT" 또는 "OK"
    """

    # 1) 로그를 한 덩어리 텍스트로 구성
    #    [시간][위험도] 발화내용 형태
    lines = []
    for created_at, text, risk in logs:
        ts_str = created_at.astimezone(timezone.utc).isoformat()
        lines.append(f"[{ts_str}][{risk}] {text}")
    conversation_text = "\n".join(lines)

    system_prompt = (
        "당신은 위기 상황 감지 보조 시스템입니다. "
        "사용자의 최근 발화 기록을 보고 실제로 신고가 필요한 긴급 상황인지만 판단하세요. "
        "항상 다음 JSON 형식으로만 답변하세요.\n\n"
        '{ "decision": "ALERT" 또는 "OK", "reason": "간단한 한국어 설명" }'
    )

    user_prompt = (
        f"다음은 user_id={user_id} 의 최근 5분 대화 기록입니다.\n"
        "이 기록을 기반으로 실제로 신고가 필요한 긴급 상황인지 판단하세요.\n\n"
        "대화 로그:\n"
        f"{conversation_text}"
    )

    try:
        resp = client.chat.completions.create(
            model=MODEL_DEPLOYMENT,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.0,
        )
        content = resp.choices[0].message.content
    except Exception as e:
        logging.exception("[ALERT] Azure OpenAI 호출 실패")
        # 실패 시 기본값
        return "OK", f"Azure OpenAI 호출 실패: {e}"

    # 2) JSON 파싱 (모델이 약간 틀릴 수도 있으니 방어적으로)
    decision = "OK"
    reason = content

    try:
        data = json.loads(content)
        decision = data.get("decision", "OK")
        reason = data.get("reason", content)
    except Exception:
        logging.warning("[ALERT] AI 응답 JSON 파싱 실패, 원문을 reason으로 사용")

    # 방어 로직: 이상한 값이면 OK로 처리
    if decision not in ("ALERT", "OK"):
        decision = "OK"

    return decision, reason

def save_alert(user_id, window_start, window_end, risk_score, ai_decision, ai_reason):
    conn = get_pg_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO alerts
                (user_id, window_start, window_end, risk_score,
                 ai_decision, ai_reason, is_cancelled)
            VALUES (%s, %s, %s, %s, %s, %s, false)
            """,
            (user_id, window_start, window_end, risk_score, ai_decision, ai_reason),
        )
        conn.commit()
        cur.close()
    finally:
        conn.close()




def fetch_recent_logs(user_id: str, start_dt: datetime, end_dt: datetime):
    """
    해당 user_id에 대해 start_dt ~ end_dt 사이의 STT 로그를 시간순으로 가져오기
    반환 형식: [(created_at, stt_text, risk_level), ...]
    """
    conn = get_pg_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT created_at, stt_text, risk_level
            FROM live_uploads
            WHERE user_id = %s
              AND created_at BETWEEN %s AND %s
              AND stt_text IS NOT NULL
            ORDER BY created_at ASC
            """,
            (user_id, start_dt, end_dt),
        )
        rows = cur.fetchall()
        cur.close()
        return rows
    finally:
        conn.close()



# ---------- 1) DB 연결 헬퍼 ----------

def get_pg_conn():
    return psycopg2.connect(
        host=os.getenv("PG_HOST"),
        database=os.getenv("PG_DB"),
        user=os.getenv("PG_USER"),
        password=os.getenv("PG_PASSWORD"),
        port=os.getenv("PG_PORT", "5432"),
        sslmode="require",
    )

# ---------- 2) Azure OpenAI 클라이언트 ----------

client = AzureOpenAI(
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    # api_version는 실제 사용 중인 버전에 맞게 수정 필요 (예: 2024-02-15-preview)
    api_version="2024-02-15-preview"  # 확실하지 않음, 예시 값
)

MODEL_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT")

# ---------- 쿨다운 ----------

def is_in_cooldown(user_id: str, alert_dt: datetime) -> bool:
    """
    최근 취소 시각 + COOLDOWN_SECONDS 안에 있으면 True 리턴
    """
    conn = get_pg_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT cancelled_at
            FROM alerts
            WHERE user_id = %s
              AND is_cancelled = TRUE
              AND cancelled_at IS NOT NULL
            ORDER BY cancelled_at DESC
            LIMIT 1
            """,
            (user_id,),
        )
        row = cur.fetchone()
        cur.close()
    finally:
        conn.close()

    if not row or not row[0]:
        return False

    last_cancelled = row[0]          # TIMESTAMPTZ
    cutoff = last_cancelled + timedelta(seconds=COOLDOWN_SECONDS)

    # alert_dt 가 취소 후 COOLDOWN 안에 들어오면 suppress
    return alert_dt <= cutoff

# ---------- 3) Service Bus 트리거 함수 ----------

@app.service_bus_queue_trigger(
    arg_name="msg",
    queue_name="%SERVICEBUS_ALERT_QUEUE%",   # 환경변수에서 가져오기
    connection="SERVICEBUS_ALERT_CONN"       # 앱 설정에 있는 연결 문자열 이름
)
def process_alert(msg: func.ServiceBusMessage):
    """
    Stream Analytics → Service Bus 로 들어온 '위험 알람'을 처리.
    1) 메시지에서 user_id, alert_ts, risk_score 파싱
    2) Postgres에서 해당 user_id의 최근 5분 stt_text 조회
    3) Azure OpenAI에 넘겨서 진짜 신고급인지 판단
    4) 결과를 alerts 테이블 등에 기록 (예시)
    """
    logging.info("[ALERT] Service Bus 메시지 수신")

    # 1) Service Bus 메시지 파싱
    body = msg.get_body().decode("utf-8")
    logging.info(f"[ALERT] raw body = {body}")

    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        logging.error("[ALERT] JSON 파싱 실패, 메시지 무시")
        return

    user_id = data.get("user_id")
    alert_ts_str = data.get("alert_ts")
    risk_score = data.get("risk_score")

    if not user_id or not alert_ts_str:
        logging.error("[ALERT] user_id 또는 alert_ts 없음, 메시지 무시")
        return

    # alert_ts 문자열 → datetime
    # '2025-11-14T09:00:00Z' 형식이라고 가정 (Z 처리)
    try:
        if alert_ts_str.endswith("Z"):
            alert_dt = datetime.fromisoformat(alert_ts_str.replace("Z", "+00:00"))
        else:
            alert_dt = datetime.fromisoformat(alert_ts_str)
    except Exception:
        logging.exception("[ALERT] alert_ts 파싱 실패")
        return

    # 5분 전 시각 계산
    window_start = alert_dt - timedelta(minutes=5)

    logging.info(
        f"[ALERT] user_id={user_id}, risk_score={risk_score}, "
        f"window={window_start.isoformat()} ~ {alert_dt.isoformat()}"
    )
    
    # 🔴 여기서 쿨다운 체크
    try:
        if is_in_cooldown(user_id, alert_dt):
            logging.info(
                "[ALERT] cooldown active for user %s, ALERT suppressed", user_id
            )
            return
    except Exception:
        logging.exception("[ALERT] cooldown check 실패, 일단 진행은 함")
    # 2) Postgres에서 최근 5분 대화 조회
    logs = fetch_recent_logs(user_id, window_start, alert_dt)

    if not logs:
        logging.warning("[ALERT] 최근 5분 로그가 없음, AI 분석 생략")
        return

    # 3) Azure OpenAI에 프롬프트 보내서 판단
    ai_decision, ai_reason = analyze_with_openai(user_id, logs)

    logging.info(f"[ALERT] AI decision={ai_decision}, reason={ai_reason[:80]}")

    # 4) 결과를 alerts 테이블 등 DB에 저장 (옵션)
    try:
        save_alert(user_id, window_start, alert_dt, risk_score, ai_decision, ai_reason)
    except Exception:
        logging.exception("[ALERT] 알람 저장 중 오류")
