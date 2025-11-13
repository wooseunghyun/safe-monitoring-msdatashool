"""
Utility script to send a sample transcript event into Event Hubs.

If no user_id/blob_name is supplied, we look up the most recent audio upload
from uploads.db so that the event matches an actual recording blob.
"""

import argparse
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from azure.eventhub import EventHubProducerClient, EventData


def load_latest_upload(db_path: Path):
    """Return (user_id, blob_name, ts) for the latest upload or None."""
    if not db_path.exists():
        return None

    con = None
    try:
        con = sqlite3.connect(db_path)
        cur = con.cursor()
        row = cur.execute(
            """
            SELECT user_id, blob_name, ts
            FROM uploads
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()
        return row
    except sqlite3.Error as exc:
        print(f"[warn] uploads.db lookup failed: {exc}")
        return None
    finally:
        if con:
            con.close()


def build_payload(args, db_path: Path):
    latest = None
    if not args.user_id or not args.blob_name or not args.ts:
        latest = load_latest_upload(db_path)

    user_id = args.user_id or (latest[0] if latest else None) or "anonymous"
    blob_name = args.blob_name or (latest[1] if latest else None) or (
        f"user-{user_id}/audio-{datetime.now(timezone.utc).isoformat().replace(':', '-')}.webm"
    )
    ts_value = args.ts or (latest[2] if latest else None) or datetime.now(timezone.utc).isoformat()

    return {
        "user_id": user_id,
        "text": args.text,
        "blob_name": blob_name,
        "ts": ts_value,
    }


def main():
    parser = argparse.ArgumentParser(description="Send a sample transcript Event Hub message.")
    parser.add_argument("--user-id", help="Override the user_id to send.")
    parser.add_argument("--blob-name", help="Override the blob_name (e.g. user-123/audio-...).")
    parser.add_argument("--text", default="도와줘요! help me please", help="Transcript text to send.")
    parser.add_argument("--ts", help="ISO8601 timestamp. Defaults to now or the latest upload entry.")
    args = parser.parse_args()

    eh_conn = os.environ["EH_CONN_STRING2"]  # Namespace connection string (primary key)
    hub_name = os.environ.get("EH_TRANSCRIPTS_HUB", "transcripts-events")

    db_path = Path(__file__).with_name("uploads.db")
    payload = build_payload(args, db_path)

    producer = EventHubProducerClient.from_connection_string(eh_conn, eventhub_name=hub_name)
    batch = producer.create_batch()
    batch.add(EventData(json.dumps(payload, ensure_ascii=False)))
    producer.send_batch(batch)
    print(f"✅ sent transcript sample for user={payload['user_id']} blob={payload['blob_name']}")


if __name__ == "__main__":
    main()
