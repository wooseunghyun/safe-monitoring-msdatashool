import logging
import azure.functions as func
import os
from io import StringIO
import pandas as pd
import json
from shared.api_client import odcloud_fetch_all
from shared.blob_uploader import upload_blob_from_memory

BASE_URL = "https://api.odcloud.kr/api/15107934/v1/uddi:20b10130-21ed-43f3-8e58-b8692fb8a2ff"
API_KEY = os.getenv("ODCLOUD_API_KEY")

def run(myTimer: func.TimerRequest):
    logging.info("🔔 가로등 API 자동 업데이트 시작")

    data = odcloud_fetch_all(BASE_URL, API_KEY)
    logging.info(f"📌 총 {len(data)}개 가로등 데이터 수집 완료")

    df = pd.DataFrame(data)
    csv_buffer = StringIO()
    df.to_csv(csv_buffer, index=False, encoding="utf-8-sig")
    csv_bytes = csv_buffer.getvalue().encode("utf-8-sig")

    json_bytes = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")

    upload_blob_from_memory(csv_bytes, "streetlight_data.csv")
    upload_blob_from_memory(json_bytes, "streetlight_data.json")

    logging.info("✔ 가로등 API 처리 완료")

