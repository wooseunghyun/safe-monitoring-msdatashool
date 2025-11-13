# send_transcripts_sample.py
import os, json
from datetime import datetime, timezone
from azure.eventhub import EventHubProducerClient, EventData

EH_CONN = os.environ["EH_CONN_STRING2"]          # 네임스페이스 정책(Connection string - primary key)
HUB_NAME = "transcripts-events"                 # transcripts용 이벤트 허브 이름

producer = EventHubProducerClient.from_connection_string(EH_CONN, eventhub_name=HUB_NAME)

evt = {
    "user_id": "anonymous",
    "text": "도와줘! help me please",            # 키워드 포함(쿼리 조건에 걸리게)
    "blob_name": "user-anonymous/audio-2025-11-12T08-00-00.webm",
    "ts": datetime.now(timezone.utc).isoformat()
}

batch = producer.create_batch()
batch.add(EventData(json.dumps(evt, ensure_ascii=False)))
producer.send_batch(batch)
print("✅ sent 1 transcript sample")
