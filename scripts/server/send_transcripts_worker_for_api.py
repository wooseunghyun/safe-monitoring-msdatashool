# scripts/server/send_transcripts_worker.py
import os, json, sqlite3, io
from datetime import datetime
from azure.storage.blob import BlobServiceClient
from azure.eventhub import EventHubProducerClient, EventData
from openai import OpenAI  # 또는 Azure OpenAI용 클라이언트

DB_PATH = os.path.join(os.path.dirname(__file__), "uploads.db")

# Blob
account_name = os.getenv("AZURE_STORAGE_ACCOUNT_NAME")
account_key = os.getenv("AZURE_STORAGE_ACCOUNT_KEY")
blob_service = BlobServiceClient(
    account_url=f"https://{account_name}.blob.core.windows.net",
    credential=account_key,
)
CONTAINER_NAME = "voice-uploads"

# Event Hub (transcripts-events)
EH_CONN = os.getenv("EH_TRANSCRIPTS_CONN_STRING")
EH_NAME = os.getenv("EH_TRANSCRIPTS_HUB_NAME")  # transcripts-events
eh_producer = EventHubProducerClient.from_connection_string(
    conn_str=EH_CONN, eventhub_name=EH_NAME
)

# STT 클라이언트 (Whisper/OpenAI 예시, 모델명은 문서에서 확인 필요 – 확실하지 않음)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def get_pending_uploads(limit=10):
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    # 예시: 아직 stt_done 플래그가 없는 것만
    cur.execute("""
        SELECT id, user_id, blob_name, ts
        FROM uploads
        WHERE mime LIKE 'audio/%'
          AND (stt_done IS NULL OR stt_done = 0)
        ORDER BY ts ASC
        LIMIT ?
    """, (limit,))
    rows = cur.fetchall()
    con.close()
    return rows


def mark_done(upload_id, text):
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("""
        UPDATE uploads
        SET stt_done = 1, transcript = ?
        WHERE id = ?
    """, (text, upload_id))
    con.commit()
    con.close()


def transcribe_blob(user_id, blob_name):
    container = blob_service.get_container_client(CONTAINER_NAME)
    blob_client = container.get_blob_client(blob_name)
    data = blob_client.download_blob().readall()

    # 메모리에 올려서 Whisper 호출 (형식 예시, 정확한 호출 방식은 문서 참고 – 확실하지 않음)
    audio_file = io.BytesIO(data)
    audio_file.name = "audio.webm"

    resp = client.audio.transcriptions.create(
        model="whisper-1",  # 또는 최신 STT 모델명
        file=audio_file,
        language="ko"  # 한국어라면
    )
    return resp.text  # or resp["text"]


def send_to_eventhub(user_id, ts_iso, blob_name, text):
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


def main():
    rows = get_pending_uploads()
    if not rows:
        print("no pending uploads")
        return

    for upload_id, user_id, blob_name, ts in rows:
        try:
            print(f"processing id={upload_id}, blob={blob_name}")
            text = transcribe_blob(user_id, blob_name)
            send_to_eventhub(user_id, ts, blob_name, text)
            mark_done(upload_id, text)
        except Exception as e:
            print("[STT ERROR]", upload_id, e)


if __name__ == "__main__":
    main()
