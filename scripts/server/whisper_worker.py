# scripts/server/whisper_worker.py
import os
import json
import tempfile
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient
from azure.eventhub import EventHubProducerClient, EventData
from azure.core.exceptions import ResourceNotFoundError
import whisper
import psycopg2

# -----------------------------------
# 0) 환경 변수 로딩
# -----------------------------------
BASE_DIR = Path(__file__).resolve().parents[2]
ENV_PATH = BASE_DIR / ".env"
load_dotenv(ENV_PATH)

# 🔹 PostgreSQL 정보
PG_HOST = os.getenv("PG_HOST")
PG_DB = os.getenv("PG_DB")
PG_USER = os.getenv("PG_USER")
PG_PASSWORD = os.getenv("PG_PASSWORD")
PG_PORT = os.getenv("PG_PORT", "5432")

if not (PG_HOST and PG_DB and PG_USER and PG_PASSWORD):
    raise RuntimeError("PostgreSQL 환경변수가 누락되었습니다. (PG_HOST/PG_DB/PG_USER/PG_PASSWORD)")


def get_pg_conn():
    return psycopg2.connect(
        host=PG_HOST,
        database=PG_DB,
        user=PG_USER,
        password=PG_PASSWORD,
        port=PG_PORT,
        sslmode="require",
    )


# 🔹 Blob Storage
ACCOUNT_NAME = os.getenv("AZURE_STORAGE_ACCOUNT_NAME")
ACCOUNT_KEY = os.getenv("AZURE_STORAGE_ACCOUNT_KEY")
VOICE_CONTAINER = os.getenv("VOICE_CONTAINER", "voice-uploads")

if not (ACCOUNT_NAME and ACCOUNT_KEY):
    raise RuntimeError("AZURE_STORAGE_ACCOUNT_NAME / AZURE_STORAGE_ACCOUNT_KEY 가 필요합니다.")

blob_service = BlobServiceClient(
    account_url=f"https://{ACCOUNT_NAME}.blob.core.windows.net",
    credential=ACCOUNT_KEY,
)
container_client = blob_service.get_container_client(VOICE_CONTAINER)

# 🔹 Event Hub (transcripts 용 – 선택)
EH_CONN = os.getenv("EH_TRANSCRIPTS_CONN_STRING")
EH_NAME = os.getenv("EH_TRANSCRIPTS_HUB_NAME")

eh_producer = None
if EH_CONN and EH_NAME:
    eh_producer = EventHubProducerClient.from_connection_string(
        conn_str=EH_CONN,
        eventhub_name=EH_NAME,
    )
    print("[EH] transcripts EventHub 활성화됨")
else:
    print("[EH] transcripts EventHub 비활성 (환경변수 없음)")


# -----------------------------------
# 1) Whisper 모델
# -----------------------------------
print("[Whisper] loading model 'small' ...")
model = whisper.load_model("small")
print("[Whisper] model loaded.")


# -----------------------------------
# 2) DB 처리 함수들 (PostgreSQL, live_uploads)
# -----------------------------------


def get_pending_rows(limit=5):
    """
    live_uploads 중 stt_text IS NULL 이고 audio_url IS NOT NULL 인 것만 가져오기
    ─> 아직 STT 안 했고, 파일 URL도 있는 것만 처리
    """
    conn = get_pg_conn()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id, user_id, audio_url, created_at
        FROM live_uploads
        WHERE stt_text IS NULL
          AND audio_url IS NOT NULL
        ORDER BY created_at ASC
        LIMIT %s
        """,
        (limit,),
    )

    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


def update_with_stt(id_, text, risk_level):
    """
    Whisper 결과와 risk_level 업데이트
    """
    conn = get_pg_conn()
    cur = conn.cursor()

    cur.execute(
        """
        UPDATE live_uploads
        SET stt_text   = %s,
            risk_level = %s,
            processed_at = NOW()
        WHERE id = %s
        """,
        (text, risk_level, id_),
    )

    conn.commit()
    cur.close()
    conn.close()


# -----------------------------------
# 3) 위험도 평가 (간단 버전 – 나중에 규칙 더 넣어도 됨)
# -----------------------------------


def classify_risk(text: str) -> str:
    t = (text or "").strip()
    if not t:
        return "NONE"

    HIGH = ["살려", "도와", "죽이", "칼", "총", "위험", "강간", "성폭력"]
    MED = ["가만히", "움직이", "갇혔", "잡혔", "싫어", "하지마", "협박"]
    LOW = ["신고", "119", "경찰", "꺼져", "미쳤", "그만해"]

    if any(k in t for k in HIGH):
        return "HIGH"
    if any(k in t for k in MED):
        return "MEDIUM"
    if any(k in t for k in LOW):
        return "LOW"
    return "NONE"


# -----------------------------------
# 4) Blob URL → Whisper STT
# -----------------------------------


def _extract_blob_name_from_url(audio_url: str) -> str:
    """
    audio_url 이 전체 URL일 때:
      https://{account}.blob.core.windows.net/voice-uploads/user-xxx/audio-yyy.webm
    여기서 blob_name = 'user-xxx/audio-yyy.webm' 만 뽑아냄
    """
    parsed = urlparse(audio_url)
    # parsed.path 예: '/voice-uploads/user-xxx/audio-yyy.webm'
    path = parsed.path.lstrip("/")  # 'voice-uploads/user-xxx/audio-yyy.webm'
    parts = path.split("/", 1)
    if len(parts) == 2:
        container, blob_name = parts
        if container != VOICE_CONTAINER:
            print(f"[WARN] URL의 container({container})가 VOICE_CONTAINER({VOICE_CONTAINER})와 다름")
    else:
        blob_name = parts[0]
    return blob_name


def transcribe_url(audio_url: str) -> str:
    """
    Blob URL에서 파일 다운로드 → Whisper 실행 → 텍스트 반환
    """
    if not audio_url:
        return ""

    blob_name = _extract_blob_name_from_url(audio_url)
    print(f"[STT] downloading blob: {blob_name}")

    blob_client = container_client.get_blob_client(blob_name)

    try:
        data = blob_client.download_blob().readall()
    except ResourceNotFoundError:
        print("[STT] blob not found:", blob_name)
        return ""

    tmp = tempfile.NamedTemporaryFile(suffix=".webm", delete=False)
    try:
        tmp.write(data)
        tmp.flush()
        tmp.close()

        print("[STT] running whisper...")
        result = model.transcribe(tmp.name, language="ko")
        text = result.get("text", "").strip()
        print(f"[STT] text: {text[:60]}{'...' if len(text) > 60 else ''}")
        return text
    finally:
        try:
            os.remove(tmp.name)
        except OSError:
            pass


# -----------------------------------
# 5) transcripts EventHub 전송 (선택)
# -----------------------------------


def send_to_eventhub(user_id, ts_iso, audio_url, text, risk):
    """
    transcripts 이벤트를 EventHub 로 보냄 (옵션)
    """
    if eh_producer is None:
        return  # EventHub 미구성 시 그냥 무시

    evt = {
        "user_id": user_id,
        "ts": ts_iso,
        "audio_url": audio_url,
        "text": text,
        "risk_level": risk,
    }
    batch = eh_producer.create_batch()
    batch.add(EventData(json.dumps(evt, ensure_ascii=False)))
    eh_producer.send_batch(batch)
    print("[EH] transcripts 이벤트 전송 완료")


# -----------------------------------
# 6) 메인 루프 한 번 처리
# -----------------------------------


def run_once(limit=5):
    rows = get_pending_rows(limit)
    if not rows:
        print("[Worker] no pending live_uploads")
        return

    for id_, user_id, audio_url, created_at in rows:
        print(f"\n[Worker] processing id={id_}, user_id={user_id}")
        print(f"       audio_url={audio_url}")

        text = ""
        try:
            text = transcribe_url(audio_url)
        except Exception as e:
            print("❌ Whisper error:", e)

        risk = classify_risk(text)

        # DB 업데이트
        try:
            update_with_stt(id_, text or "[ERROR OR EMPTY]", risk)
        except Exception as e:
            print("❌ DB update error:", e)
            continue

        # EventHub 전송 (있을 때만)
        try:
            ts_for_evt = (created_at or datetime.utcnow()).isoformat()
            send_to_eventhub(user_id, ts_for_evt, audio_url, text, risk)
        except Exception as e:
            print("⚠️ EventHub 전송 중 오류 (무시):", e)

        print(f"[DONE] id={id_}, risk={risk}, text='{text[:30]}'")


# -----------------------------------
# 7) 메인 루프
# -----------------------------------

if __name__ == "__main__":
    import time

    print("[Worker] start loop (live_uploads 기반 STT)")

    while True:
        try:
            run_once(limit=5)
        except Exception as e:
            print("🔥 [Worker FATAL] run_once 오류:", e)
        time.sleep(5)
