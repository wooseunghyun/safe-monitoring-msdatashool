import os
import sqlite3
from pathlib import Path

from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient
from azure.core.exceptions import ResourceNotFoundError

# -----------------------
# 0) 경로 & 환경변수 로딩
# -----------------------
BASE_DIR = Path(__file__).resolve().parents[2]  # safe-monitoring-msdatashool
ENV_PATH = BASE_DIR / ".env"
load_dotenv(ENV_PATH)

SQLITE_PATH = os.getenv("SQLITE_PATH")
if not SQLITE_PATH:
    # 안전장치: 설정 안 되어 있으면 바로 에러
    raise RuntimeError("SQLITE_PATH 가 .env에 설정되어 있어야 합니다.")

DB_PATH = Path(SQLITE_PATH)
print("[Worker] Using DB:", DB_PATH)

ACCOUNT_NAME = os.getenv("AZURE_STORAGE_ACCOUNT_NAME")
ACCOUNT_KEY  = os.getenv("AZURE_STORAGE_ACCOUNT_KEY")
VOICE_CONTAINER = os.getenv("VOICE_CONTAINER", "voice-uploads")

if not ACCOUNT_NAME or not ACCOUNT_KEY:
    raise RuntimeError("AZURE_STORAGE_ACCOUNT_NAME / AZURE_STORAGE_ACCOUNT_KEY 가 .env에 필요합니다.")

blob_service = BlobServiceClient(
    account_url=f"https://{ACCOUNT_NAME}.blob.core.windows.net",
    credential=ACCOUNT_KEY,
)
container_client = blob_service.get_container_client(VOICE_CONTAINER)


# -----------------------
# 1) DB 유틸
# -----------------------
def get_conn():
    return sqlite3.connect(DB_PATH)

def get_pending_rows(limit=1000):
    """
    아직 stt_done이 0 또는 NULL인 row들 가져오기
    """
    con = get_conn()
    cur = con.cursor()
    cur.execute("""
        SELECT id, user_id, blob_name, ts, stt_done
        FROM uploads
        WHERE stt_done IS NULL OR stt_done = 0
        ORDER BY ts ASC
        LIMIT ?
    """, (limit,))
    rows = cur.fetchall()
    con.close()
    return rows

def mark_missing(upload_id: int):
    """
    Blob이 없어서 더이상 처리 못하는 row → stt_done=1, transcript를 표시용으로 남김
    """
    con = get_conn()
    cur = con.cursor()
    cur.execute("""
        UPDATE uploads
        SET stt_done = 1,
            transcript = COALESCE(transcript, '[MISSING_BLOB]')
        WHERE id = ?
    """, (upload_id,))
    con.commit()
    con.close()


# -----------------------
# 2) 메인 로직
# -----------------------
def main():
    rows = get_pending_rows(limit=1000)
    if not rows:
        print("[cleanup] no pending rows.")
        return

    fixed = 0
    kept  = 0

    for upload_id, user_id, blob_name, ts, stt_done in rows:
        print(f"\n[cleanup] checking id={upload_id}, user_id={user_id}, blob={blob_name}")
        blob_client = container_client.get_blob_client(blob_name)
        try:
            blob_client.get_blob_properties()
            print("  -> blob EXISTS, keep for worker.")
            kept += 1
        except ResourceNotFoundError:
            print("  -> blob NOT FOUND, mark as done(missing).")
            mark_missing(upload_id)
            fixed += 1

    print(f"\n[cleanup] done. fixed={fixed}, kept={kept}")


if __name__ == "__main__":
    main()
