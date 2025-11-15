# from flask import Blueprint, request, jsonify, make_response, current_app
# from datetime import datetime
# import os, json
# from scripts.server.services.azure_clients import get_blob_service
# from scripts.server.services import db as dbsvc
# from scripts.server.utils.auth import resolve_user_id

# bp = Blueprint("upload", __name__)

# #로컬과 비교 테스트용
# from pathlib import Path

# DEBUG_AUDIO_DIR = Path("debug_audio")
# DEBUG_AUDIO_DIR.mkdir(exist_ok=True)
# #

# @bp.post("/upload-audio")
# def upload_audio():
#     print("=== /upload-audio DEBUG ===")
#     print("content_type:", request.content_type)
#     print("files keys:", list(request.files.keys()))
#     print("form:", request.form.to_dict())

#     file = request.files.get("file")
#     if file is None:
#         return jsonify({"error": "file field missing"}), 400

#     # 🔎 스트림에서 바로 읽어서 bytes 확보
#     data = file.read()
#     size_bytes = len(data)

#     if size_bytes == 0:
#         # 완전히 빈 파일이면 거절
#         return jsonify({"error": "empty file"}), 400

#     # 파일명을 다시 결정 (원래 로직 유지)
#     ts_iso = request.form.get("ts") or datetime.utcnow().isoformat()

#     #로컬과 비교 테스트용
#     # 🔍 1) 서버에서 받은 bytes를 로컬에 그대로 저장 (디버그용)
#     debug_name = f"server-{ts_iso.replace(':','-').replace('.','-')}.webm"
#     debug_path = DEBUG_AUDIO_DIR / debug_name
#     with open(debug_path, "wb") as f:
#         f.write(data)

#     # 🔍 로그 찍어서 나중에 매칭하기 좋게
#     print("[DEBUG] saved raw audio to", debug_path, "size=", size_bytes)

#     resp = make_response()
#     user_id, resp, _ = resolve_user_id(resp)
#     if not user_id:
#         return jsonify({"error": "unauthorized"}), 401

#     fname = file.filename or f"audio-{datetime.utcnow().isoformat().replace(':','-').replace('.','-')}.webm"
#     blob_name = f"user-{user_id}/{os.path.basename(fname)}"

#     blob_svc = get_blob_service(
#         current_app.config["AZURE_STORAGE_ACCOUNT_NAME"],
#         current_app.config["AZURE_STORAGE_ACCOUNT_KEY"]
#     )
#     container = current_app.config["VOICE_CONTAINER"]

#     # ⚠️ file.stream 대신 data(bytes)를 바로 업로드
#     blob_svc.get_container_client(container).upload_blob(
#         name=blob_name, data=data, overwrite=True,
#         content_settings=None
#     )

#     # DB에는 우리가 계산한 size_bytes를 기록
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


# scripts/server/routes/upload_audio.py
from flask import Blueprint, request, jsonify, make_response, current_app
from datetime import datetime, timezone
import os, json
from scripts.server.services.azure_clients import get_blob_service
from scripts.server.services import db as dbsvc
from scripts.server.services.pg import get_pg_conn      # 🔹 새로 추가
from scripts.server.utils.auth import resolve_user_id

bp = Blueprint("upload", __name__)

from pathlib import Path
DEBUG_AUDIO_DIR = Path("debug_audio")
DEBUG_AUDIO_DIR.mkdir(exist_ok=True)


@bp.post("/upload-audio")
def upload_audio():
    print("=== /upload-audio DEBUG ===")
    print("content_type:", request.content_type)
    print("files keys:", list(request.files.keys()))
    print("form:", request.form.to_dict())

    file = request.files.get("file")
    if file is None:
        return jsonify({"error": "file field missing"}), 400

    # 🔹 raw bytes
    data = file.read()
    size_bytes = len(data)
    if size_bytes == 0:
        return jsonify({"error": "empty file"}), 400

    # 업로드 시각
    ts_iso = request.form.get("ts") or datetime.utcnow().isoformat()

    # 디버그용 로컬 저장
    debug_name = f"server-{ts_iso.replace(':','-').replace('.','-')}.webm"
    debug_path = DEBUG_AUDIO_DIR / debug_name
    with open(debug_path, "wb") as f:
        f.write(data)
    print("[DEBUG] saved raw audio to", debug_path, "size=", size_bytes)

    resp = make_response()
    user_id, resp, _ = resolve_user_id(resp)
    if not user_id:
        return jsonify({"error": "unauthorized"}), 401

    fname = file.filename or f"audio-{ts_iso.replace(':','-').replace('.','-')}.webm"
    blob_name = f"user-{user_id}/{os.path.basename(fname)}"

    blob_svc = get_blob_service(
        current_app.config["AZURE_STORAGE_ACCOUNT_NAME"],
        current_app.config["AZURE_STORAGE_ACCOUNT_KEY"]
    )
    container = current_app.config["VOICE_CONTAINER"]

    # Azure Blob 업로드
    blob_svc.get_container_client(container).upload_blob(
        name=blob_name, data=data, overwrite=True,
        content_settings=None
    )

    # ✅ Blob URL 만들기 (audio_url로 DB에 저장)
    account = current_app.config["AZURE_STORAGE_ACCOUNT_NAME"]
    audio_url = f"https://{account}.blob.core.windows.net/{container}/{blob_name}"

    # 위치 + peak_db 꺼내기
    lat = request.form.get("lat")
    lon = request.form.get("lon")
    peak_db = request.form.get("peak_db")

    lat_f = float(lat) if lat is not None else None
    lon_f = float(lon) if lon is not None else None
    peak_f = float(peak_db) if peak_db is not None else None

    # 🔸 (옵션) 기존 SQLite 로그 유지 – 필요 없으면 이건 지워도 됨
    dbsvc.log_upload(
        current_app.config["SQLITE_PATH"], user_id, blob_name, ts_iso,
        size_bytes, file.mimetype or "application/octet-stream",
        request.headers.get("X-Forwarded-For", request.remote_addr)
    )

    # ✅ 여기서 PostgreSQL live_uploads에 같이 INSERT
    try:
        conn = get_pg_conn()
        cur = conn.cursor()

        created_at = datetime.fromisoformat(ts_iso.replace("Z", "+00:00")) \
            if "T" in ts_iso else datetime.utcnow().replace(tzinfo=timezone.utc)

        # ⚠️ 이 부분은 live_uploads 실제 컬럼명에 맞춰 수정 필요
        cur.execute(
            """
            INSERT INTO live_uploads (
                user_id,
                lat,
                lng,
                audio_url,
                peak_volume,
                stt_text,
                risk_level,
                created_at,
                processed_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NULL)
            """,
            (
                user_id,
                lat_f,
                lon_f,
                audio_url,
                peak_f,
                None,          # stt_text (whisper_worker가 나중에 UPDATE)
                None,          # risk_level
                created_at,
            )
        )

        conn.commit()
        cur.close()
        conn.close()

        print("[PG] live_uploads inserted for", user_id, audio_url)

    except Exception as e:
        # 일단 에러는 찍고, 업로드 자체는 성공 처리할지/실패 처리할지 정책에 따라 결정
        print("❌ live_uploads insert error:", e)

    # 응답 부분은 기존 로직 유지
    if current_app.config["ALLOW_ANON_UPLOAD"]:
        resp.set_data(json.dumps({"ok": True, "user_id": user_id, "blob": blob_name}))
        resp.mimetype = "application/json"
        return resp
    else:
        return jsonify({"ok": True, "user_id": user_id, "blob": blob_name})
