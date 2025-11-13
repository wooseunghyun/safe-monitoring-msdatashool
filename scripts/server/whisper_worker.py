# scripts/server/whisper_worker.py

import os
import io
import json
import sqlite3
from pathlib import Path
from datetime import datetime
import tempfile

from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient
from azure.eventhub import EventHubProducerClient, EventData
from azure.core.exceptions import ResourceNotFoundError
import whisper


# ---------------------------
# 0) 환경설정 / 경로
# ---------------------------

BASE_DIR = Path(__file__).resolve().parents[2]   # repo 루트 (safe-monitoring-msdatashool)
ENV_PATH = BASE_DIR / ".env"
load_dotenv(ENV_PATH)


SQLITE_PATH = os.getenv("SQLITE_PATH")
if not SQLITE_PATH:
    # 안전장치: 설정 안 되어 있으면 바로 에러
    raise RuntimeError("SQLITE_PATH 가 .env에 설정되어 있어야 합니다.")

DB_PATH = Path(SQLITE_PATH)
print("[Worker] Using DB:", DB_PATH)

# DB_PATH = Path(__file__).with_name("uploads.db")  # scripts/server/uploads.db

ACCOUNT_NAME = os.getenv("AZURE_STORAGE_ACCOUNT_NAME")
ACCOUNT_KEY  = os.getenv("AZURE_STORAGE_ACCOUNT_KEY")
VOICE_CONTAINER = os.getenv("VOICE_CONTAINER", "voice-uploads")  # 기존 컨테이너 이름과 맞춰주세요

EH_CONN = os.getenv("EH_TRANSCRIPTS_CONN_STRING")  # transcripts용 EH (추측입니다)
EH_NAME = os.getenv("EH_TRANSCRIPTS_HUB_NAME")     # 예: "transcripts-events" (추측입니다)

if not ACCOUNT_NAME or not ACCOUNT_KEY:
    raise RuntimeError("AZURE_STORAGE_ACCOUNT_NAME / AZURE_STORAGE_ACCOUNT_KEY 가 .env에 설정되어 있어야 합니다.")

if not EH_CONN or not EH_NAME:
    raise RuntimeError("EH_TRANSCRIPTS_CONN_STRING / EH_TRANSCRIPTS_HUB_NAME 를 .env에 설정하세요 (transcripts용 Event Hub).")


# ---------------------------
# 1) DB 유틸 (스키마 보정 + 조회/업데이트)
# ---------------------------

def get_conn():
    return sqlite3.connect(DB_PATH)

def ensure_schema():
    """
    uploads 테이블에 stt_done, transcript 컬럼이 없으면 추가.
    """
    con = get_conn()
    cur = con.cursor()
    cur.execute("PRAGMA table_info(uploads);")
    cols = [row[1] for row in cur.fetchall()]   # row[1] = column name

    # stt_done 추가
    if "stt_done" not in cols:
        print("[DB] adding column stt_done")
        cur.execute("ALTER TABLE uploads ADD COLUMN stt_done INTEGER DEFAULT 0;")

    # transcript 추가
    if "transcript" not in cols:
        print("[DB] adding column transcript")
        cur.execute("ALTER TABLE uploads ADD COLUMN transcript TEXT;")

    con.commit()
    con.close()

def get_pending_uploads(limit=5):
    """
    아직 STT 안한( stt_done=0 또는 NULL ) audio만 가져오기.
    """
    con = get_conn()
    cur = con.cursor()
    cur.execute("""
        SELECT id, user_id, blob_name, ts
        FROM uploads
        WHERE (mime LIKE 'audio/%' OR blob_name LIKE '%.webm')
          AND (stt_done IS NULL OR stt_done = 0)
        ORDER BY ts ASC
        LIMIT ?
    """, (limit,))
    rows = cur.fetchall()
    con.close()
    return rows

def mark_done(upload_id, text):
    """
    STT 완료 표시 + transcript 저장.
    """
    con = get_conn()
    cur = con.cursor()
    cur.execute("""
        UPDATE uploads
        SET stt_done = 1, transcript = ?
        WHERE id = ?
    """, (text, upload_id))
    con.commit()
    con.close()


# ---------------------------
# 2) Azure Blob / EventHub 클라이언트
# ---------------------------

blob_service = BlobServiceClient(
    account_url=f"https://{ACCOUNT_NAME}.blob.core.windows.net",
    credential=ACCOUNT_KEY,
)
container_client = blob_service.get_container_client(VOICE_CONTAINER)

eh_producer = EventHubProducerClient.from_connection_string(
    conn_str=EH_CONN,
    eventhub_name=EH_NAME,
)


# ---------------------------
# 3) Whisper 로컬 모델 로딩
# ---------------------------
# tiny / base / small / medium / large 중 선택 가능
# small 정도가 속도/정확도 밸런스 괜찮음 (GPU 있으면 medium도 가능)
print("[Whisper] loading model 'small'...")
model = whisper.load_model("small")
print("[Whisper] model loaded.")


def transcribe_blob(user_id: str, blob_name: str) -> str:
    print(f"[STT] downloading blob: {blob_name}")
    blob_client = container_client.get_blob_client(blob_name)

    try:
        props = blob_client.get_blob_properties()
        print(f"[STT] blob size={props.size}, content_type={props.content_settings.content_type}")

        data = blob_client.download_blob().readall()
    except ResourceNotFoundError:
        print(f"[STT][WARN] blob not found: {blob_name}")
        # 더 이상 재시도하지 않게 하기 위해 빈 문자열 리턴
        return ""

    # 여기부터는 blob이 실제로 있는 경우만 실행됨
    tmp = tempfile.NamedTemporaryFile(suffix=".webm", delete=False)
    try:
        tmp.write(data)
        tmp.flush()
        tmp.close()

        print(f"[STT] running whisper on {blob_name} ...")
        result = model.transcribe(tmp.name, language="ko")
        text = result.get("text", "").strip()
        print(f"[STT] result text: {text[:60]}{'...' if len(text) > 60 else ''}")
        return text
    finally:
        try:
            os.remove(tmp.name)
        except OSError:
            pass



def send_to_eventhub(user_id: str, ts_iso: str, blob_name: str, text: str):
    """
    transcripts Event Hub로 {user_id, ts, blob_name, text} 이벤트 전송.
    """
    if not ts_iso:
        ts_iso = datetime.utcnow().isoformat()

    evt = {
        "user_id": user_id,
        "ts": ts_iso,
        "blob_name": blob_name,
        "text": text,
    }

    batch = eh_producer.create_batch()
    batch.add(EventData(json.dumps(evt, ensure_ascii=False)))
    eh_producer.send_batch(batch)

    print("[Transcripts → EH] ✅", evt)


# ---------------------------
# 4) 메인 루프 (한 번에 N개 처리)
# ---------------------------

def run_once(limit=5):
    ensure_schema()

    rows = get_pending_uploads(limit=limit)
    if not rows:
        print("[Worker] no pending uploads.")
        return

    for upload_id, user_id, blob_name, ts_iso in rows:
        print(f"\n[Worker] processing id={upload_id}, user_id={user_id}, blob={blob_name}")
        try:
            text = transcribe_blob(user_id, blob_name)
            # 정상적으로 텍스트가 나오든 ""이 나오든 일단 Event Hub로 보내고
            send_to_eventhub(user_id, ts_iso, blob_name, text)
            # 빈 문자열이면 "[ERROR or EMPTY AUDIO]" 저장
            mark_done(upload_id, text or "[ERROR or EMPTY AUDIO]")
            print(f"[Worker] done id={upload_id}")
        except Exception as e:
            print(f"[Worker][ERROR] id={upload_id} error={e}")

            # ✅ 여기 추가: 에러가 나도 "시도는 했다"로 간주하고 다시는 안 건드리기
            error_text = f"[STT ERROR] {type(e).__name__}: {e}"
            try:
                mark_done(upload_id, error_text)
                print(f"[Worker] marked id={upload_id} as done with error")
            except Exception as e2:
                # 이마저도 실패하면 그냥 로그만 남김
                print(f"[Worker][ERROR] failed to mark id={upload_id} as done: {e2}")



if __name__ == "__main__":
    import time

    ensure_schema()
    print("[Worker] starting loop...")

    while True:
        try:
            run_once(limit=5)
        except Exception as e:
            print("[Worker][FATAL LOOP ERROR]", e)

        # 새 녹음이 들어올 시간을 조금 준 뒤 다시 확인
        time.sleep(5)   # 5초마다 DB 확인 (원하면 1~10초 사이로 조정 가능)
