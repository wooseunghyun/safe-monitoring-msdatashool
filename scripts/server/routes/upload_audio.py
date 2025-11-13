from flask import Blueprint, request, jsonify, make_response, current_app
from datetime import datetime
import os, json
from scripts.server.services.azure_clients import get_blob_service
from scripts.server.services import db as dbsvc
from scripts.server.utils.auth import resolve_user_id

bp = Blueprint("upload", __name__)

# @bp.post("/upload-audio")
# def upload_audio():
#     print("=== /upload-audio DEBUG ===")
#     print("content_type:", request.content_type)
#     print("files keys:", list(request.files.keys()))
#     print("form:", request.form.to_dict())

#     if "file" not in request.files:
#         return "file field missing", 400

#     resp = make_response()
#     user_id, resp, _ = resolve_user_id(resp)
#     if not user_id:
#         return jsonify({"error": "unauthorized"}), 401

#     ts_iso = request.form.get("ts") or datetime.utcnow().isoformat()
#     file = request.files["file"]
#     fname = file.filename or f"audio-{datetime.utcnow().isoformat().replace(':','-').replace('.','-')}.webm"
#     blob_name = f"user-{user_id}/{os.path.basename(fname)}"

#     blob_svc = get_blob_service(
#         current_app.config["AZURE_STORAGE_ACCOUNT_NAME"],
#         current_app.config["AZURE_STORAGE_ACCOUNT_KEY"]
#     )
#     container = current_app.config["VOICE_CONTAINER"]
#     blob_svc.get_container_client(container).upload_blob(
#         name=blob_name, data=file.stream, overwrite=True,
#         content_settings=None
#     )

#     size_bytes = request.content_length or 0
#     dbsvc.log_upload(
#         current_app.config["SQLITE_PATH"], user_id, blob_name, ts_iso,
#         size_bytes, file.mimetype or "application/octet-stream",
#         request.headers.get("X-Forwarded-For", request.remote_addr)
#     )

    

#     if current_app.config["ALLOW_ANON_UPLOAD"]:
#         resp.set_data(json.dumps({"ok": True, "user_id": user_id, "blob": blob_name}))
#         resp.mimetype = "application/json"
#         return resp
#     else:
#         return jsonify({"ok": True, "user_id": user_id, "blob": blob_name})

#로컬과 비교 테스트용
from pathlib import Path

DEBUG_AUDIO_DIR = Path("debug_audio")
DEBUG_AUDIO_DIR.mkdir(exist_ok=True)
#

@bp.post("/upload-audio")
def upload_audio():
    print("=== /upload-audio DEBUG ===")
    print("content_type:", request.content_type)
    print("files keys:", list(request.files.keys()))
    print("form:", request.form.to_dict())

    file = request.files.get("file")
    if file is None:
        return jsonify({"error": "file field missing"}), 400

    # 🔎 스트림에서 바로 읽어서 bytes 확보
    data = file.read()
    size_bytes = len(data)

    if size_bytes == 0:
        # 완전히 빈 파일이면 거절
        return jsonify({"error": "empty file"}), 400

    # 파일명을 다시 결정 (원래 로직 유지)
    ts_iso = request.form.get("ts") or datetime.utcnow().isoformat()

    #로컬과 비교 테스트용
    # 🔍 1) 서버에서 받은 bytes를 로컬에 그대로 저장 (디버그용)
    debug_name = f"server-{ts_iso.replace(':','-').replace('.','-')}.webm"
    debug_path = DEBUG_AUDIO_DIR / debug_name
    with open(debug_path, "wb") as f:
        f.write(data)

    # 🔍 로그 찍어서 나중에 매칭하기 좋게
    print("[DEBUG] saved raw audio to", debug_path, "size=", size_bytes)

    resp = make_response()
    user_id, resp, _ = resolve_user_id(resp)
    if not user_id:
        return jsonify({"error": "unauthorized"}), 401

    fname = file.filename or f"audio-{datetime.utcnow().isoformat().replace(':','-').replace('.','-')}.webm"
    blob_name = f"user-{user_id}/{os.path.basename(fname)}"

    blob_svc = get_blob_service(
        current_app.config["AZURE_STORAGE_ACCOUNT_NAME"],
        current_app.config["AZURE_STORAGE_ACCOUNT_KEY"]
    )
    container = current_app.config["VOICE_CONTAINER"]

    # ⚠️ file.stream 대신 data(bytes)를 바로 업로드
    blob_svc.get_container_client(container).upload_blob(
        name=blob_name, data=data, overwrite=True,
        content_settings=None
    )

    # DB에는 우리가 계산한 size_bytes를 기록
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
