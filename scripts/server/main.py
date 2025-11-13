# from flask import Flask, render_template
# from dotenv import load_dotenv
# import os
# import pathlib

# # .env 읽기
# load_dotenv()

# # 현재 파일 기준으로 프로젝트 루트 계산
# BASE_DIR = pathlib.Path(__file__).resolve().parents[2]  # .../safe-monitoring-msdatashool

# app = Flask(
#     __name__,
#     template_folder=str(BASE_DIR / "templates"),
#     static_folder=str(BASE_DIR / "static"),
# )

# @app.route("/")
# def index():
#     kakao_key = os.getenv("KAKAO_MAP_API_KEY", "")
#     return render_template("index.html", kakao_key=kakao_key)

# if __name__ == "__main__":
#     # 0.0.0.0 으로 띄우면 나중에 다른 장치에서도 볼 수 있음
#     app.run(debug=True)


# scripts/server/main.py
from flask import Flask, render_template, request, jsonify
import json, os
import requests
from dotenv import load_dotenv
import pathlib
from azure.eventhub import EventHubProducerClient, EventData

load_dotenv()

# 현재 파일 기준으로 프로젝트 루트 계산
BASE_DIR = pathlib.Path(__file__).resolve().parents[2]  # .../safe-monitoring-msdatashool

EH_CONN = os.getenv("EH_CONN_STRING")      # Event Hubs 네임스페이스/허브의 연결 문자열
EH_NAME = os.getenv("EH_HUB_NAME")         # 예: "safe-telemetry"

app = Flask(
    __name__,
    template_folder=str(BASE_DIR / "templates"),
    static_folder=str(BASE_DIR / "static"),
)

# OSRM 서버 주소 (직접 띄운 걸 쓰는 게 제일 좋음)
OSRM_URL = os.getenv("OSRM_URL", "http://router.project-osrm.org")

@app.route("/")
def index():
    kakao_key = os.getenv("KAKAO_MAP_API_KEY")
    return render_template("index.html", kakao_key=kakao_key)

@app.route("/api/route")
def api_route():
    start = request.args.get("start")
    end = request.args.get("end")
    via = request.args.get("via")
    # ?profile=foot 같은 식으로 받기, 기본은 driving
    profile = request.args.get("profile", "driving")

    if not start or not end:
        return jsonify({"error": "start and end required"}), 400

    def flip(s):
        lat, lng = s.split(",")
        return f"{lng},{lat}"

    coords = [flip(start)]
    if via:
        for v in via.split(";"):
            coords.append(flip(v))
    coords.append(flip(end))

    coords_str = ";".join(coords)

    # ⚠️ 여기서 profile 변수를 사용
    url = f"{OSRM_URL}/route/v1/{profile}/{coords_str}"
    params = {
        "overview": "full",
        "geometries": "geojson"
    }
    try:
        r = requests.get(url, params=params, timeout=5)
        r.raise_for_status()
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    data = r.json()
    if not data.get("routes"):
        return jsonify({"error": "no route"}), 500

    return jsonify(data["routes"][0]["geometry"])

from azure.storage.blob import BlobServiceClient
from datetime import datetime
import os, re, sqlite3

# (1) Azure 설정
account_name = os.getenv("AZURE_STORAGE_ACCOUNT_NAME")
account_key = os.getenv("AZURE_STORAGE_ACCOUNT_KEY")
blob_service_client = BlobServiceClient(
    account_url=f"https://{account_name}.blob.core.windows.net",
    credential=account_key,
)
CONTAINER_NAME = "voice-uploads"


# -----------------------------
# 2️⃣ SQLite 초기화 (main.py에 직접 포함)
# -----------------------------
DB_PATH = os.path.join(os.path.dirname(__file__), "uploads.db")

def init_db():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS uploads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            blob_name TEXT,
            ts TEXT,
            size_bytes INTEGER,
            mime TEXT,
            ip TEXT
        );
    """)
    con.commit()
    con.close()

init_db()

def log_upload(user_id, blob_name, ts, size_bytes, mime, ip):
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("""
        INSERT INTO uploads (user_id, blob_name, ts, size_bytes, mime, ip)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (user_id, blob_name, ts, size_bytes, mime, ip))
    con.commit()
    con.close()



def ensure_container():
    try:
        blob_service_client.create_container(CONTAINER_NAME)
    except Exception:
        pass  # 이미 있으면 무시

ensure_container()

# --- (선택) user_id 간단 검증/정제 ---
_SAFE = re.compile(r"[^a-zA-Z0-9_\-]")
def sanitize_user_id(uid: str) -> str:
    if not uid:
        return "anonymous"
    return _SAFE.sub("-", uid)[:64]  # 너무 길면 컷

# (2) 오디오 업로드 라우트
@app.route("/upload-audio", methods=["POST"])
def upload_audio():
    if "file" not in request.files:
        return "file field missing", 400

    raw_user_id = request.form.get("user_id", "anonymous")
    user_id = sanitize_user_id(raw_user_id)
    ts_iso = request.form.get("ts") or datetime.utcnow().isoformat()

    file = request.files["file"]
    orig_filename = file.filename or f"audio-{datetime.utcnow().isoformat().replace(':','-').replace('.','-')}.webm"

    # 👉 여기서 경로 강제: user-<id>/파일명
    #    (클라이언트가 경로를 넣어 보내도, 서버에서 다시 보장)
    blob_name = f"user-{user_id}/{os.path.basename(orig_filename)}"

    try:
        container_client = blob_service_client.get_container_client(CONTAINER_NAME)
        blob_client = container_client.get_blob_client(blob_name)

        # 컨텐츠 타입도 같이 저장(편의)
        content_type = file.mimetype or "application/octet-stream"
        blob_client.upload_blob(file.stream, overwrite=True, content_type=content_type)

        size_bytes = request.content_length or 0

        # 업로드 로그 DB 기록 (아래 2) 참고)
        log_upload(user_id=user_id,
                   blob_name=blob_name,
                   ts=ts_iso,
                   size_bytes=size_bytes,
                   mime=content_type,
                   ip=request.headers.get("X-Forwarded-For", request.remote_addr))

        print(f"[UPLOAD OK] user={user_id} blob={blob_name}")
        return jsonify({"ok": True, "user_id": user_id, "blob": blob_name}), 200

    except Exception as e:
        print("[UPLOAD ERROR]", e)
        return jsonify({"ok": False, "error": str(e)}), 500

# 누가 뭘 올렸는지 확인
@app.route("/uploads", methods=["GET"])
def list_uploads():
    user_id = request.args.get("user_id")
    q = "SELECT user_id, blob_name, ts, size_bytes, mime, ip FROM uploads"
    args = []
    if user_id:
        q += " WHERE user_id=?"
        args.append(user_id)
    q += " ORDER BY ts DESC LIMIT 100"
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    rows = cur.execute(q, args).fetchall()
    con.close()
    return jsonify([
        {"user_id": r[0], "blob": r[1], "ts": r[2], "size": r[3], "mime": r[4], "ip": r[5]}
        for r in rows
    ])


eh_producer = EventHubProducerClient.from_connection_string(conn_str=EH_CONN, eventhub_name=EH_NAME)

@app.route("/telemetry", methods=["POST"])
def telemetry():
  try:
    evt = request.get_json(force=True)
    # 최소 필드 검증
    if not evt or "user_id" not in evt or "ts" not in evt or "peak_db" not in evt:
      return "bad payload", 400

    # Event Hubs에 전송
    batch = eh_producer.create_batch()
    batch.add(EventData(json.dumps(evt)))
    eh_producer.send_batch(batch)
    print("[Telemetry → EH] ✅", evt)
    return jsonify({"ok": True})
  except Exception as e:
    print("[telemetry error]", e)
    return jsonify({"ok": False, "error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True)
