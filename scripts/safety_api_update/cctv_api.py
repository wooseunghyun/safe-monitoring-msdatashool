import logging
import azure.functions as func
import os
from io import StringIO
import pandas as pd
import json
from shared.api_client import fetch_paged_data
from shared.blob_uploader import upload_blob_from_memory

BASE_URL = "http://openapi.seoul.go.kr:8088"
API_KEY = os.getenv("SEOUL_API_KEY")
SERVICE_NAME = "safeOpenCCTV"

def run(myTimer: func.TimerRequest):
    logging.info("🔔 CCTV API 자동 업데이트 시작")

    data = fetch_paged_data(BASE_URL, API_KEY, SERVICE_NAME)
    logging.info(f"📌 총 {len(data)}개 CCTV 데이터 수집 완료")

    df = pd.DataFrame(data)
    csv_buffer = StringIO()
    df.to_csv(csv_buffer, index=False, encoding="utf-8-sig")
    csv_bytes = csv_buffer.getvalue().encode("utf-8-sig")

    json_bytes = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")

    upload_blob_from_memory(csv_bytes, "cctv_data.csv")
    upload_blob_from_memory(json_bytes, "cctv_data.json")

    logging.info("✔ CCTV API 처리 완료")

