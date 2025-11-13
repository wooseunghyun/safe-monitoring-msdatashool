from flask import Blueprint, request, jsonify, make_response, current_app
from datetime import datetime
import os, json
from scripts.server.services.azure_clients import get_blob_service
from scripts.server.services import db as dbsvc
from scripts.server.utils.auth import resolve_user_id

bp = Blueprint("upload", __name__)

@bp.post("/upload-audio")
def upload_audio():
    if "file" not in request.files:
        return "file field missing", 400

    resp = make_response()
    user_id, resp, _ = resolve_user_id(resp)
    if not user_id:
        return jsonify({"error": "unauthorized"}), 401

    ts_iso = request.form.get("ts") or datetime.utcnow().isoformat()
    file = request.files["file"]
    fname = file.filename or f"audio-{datetime.utcnow().isoformat().replace(':','-').replace('.','-')}.webm"
    blob_name = f"user-{user_id}/{os.path.basename(fname)}"

    blob_svc = get_blob_service(
        current_app.config["AZURE_STORAGE_ACCOUNT_NAME"],
        current_app.config["AZURE_STORAGE_ACCOUNT_KEY"]
    )
    container = current_app.config["VOICE_CONTAINER"]
    blob_svc.get_container_client(container).upload_blob(
        name=blob_name, data=file.stream, overwrite=True,
        content_settings=None
    )

    size_bytes = request.content_length or 0
    dbsvc.log_upload(
        current_app.config["SQLITE_PATH"], user_id, blob_name, ts_iso,
        size_bytes, file.mimetype or "application/octet-stream",
        request.headers.get("X-Forwarded-For", request.remote_addr)
    )

    if current_app.config["ALLOW_ANON_UPLOAD"]:
        resp.set_data(json.dumps({"ok": True, "user_id": user_id, "blob": blob_name}))
        resp.mimetype = "application/json"
        return resp
    else:
        return jsonify({"ok": True, "user_id": user_id, "blob": blob_name})
