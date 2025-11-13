from flask import Blueprint, request, jsonify, make_response, current_app
import json
from azure.eventhub import EventData
from scripts.server.services.azure_clients import get_eh_producer
from scripts.server.utils.auth import resolve_user_id

bp = Blueprint("telemetry", __name__)

@bp.post("/telemetry")
def telemetry():
    resp = make_response()
    user_id, resp, _ = resolve_user_id(resp)
    if not user_id:
        return jsonify({"error":"unauthorized"}), 401

    d = request.get_json(force=True) or {}
    ts = d.get("ts"); peak_db = d.get("peak_db")
    if not ts or peak_db is None:
        return jsonify({"error":"bad payload"}), 400

    evt = {
        "user_id": user_id,
        "ts": ts,
        "peak_db": float(peak_db),
        "baseline_db": float(d.get("baseline_db", -50)),
        "chunk_ms": int(d.get("chunk_ms", 2000)),
    }

    producer = get_eh_producer(
        current_app.config["EH_CONN_STRING"],
        current_app.config["EH_HUB_NAME"]
    )
    try:
        batch = producer.create_batch(partition_key=user_id)
    except TypeError:
        batch = producer.create_batch()

    batch.add(EventData(json.dumps(evt, ensure_ascii=False)))
    producer.send_batch(batch)

    if current_app.config["ALLOW_ANON_UPLOAD"]:
        resp.set_data(json.dumps({"ok": True})); resp.mimetype = "application/json"
        return resp
    else:
        return jsonify({"ok": True})
