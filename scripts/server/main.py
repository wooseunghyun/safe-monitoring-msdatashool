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
import os
import requests
from dotenv import load_dotenv
import pathlib

load_dotenv()

# 현재 파일 기준으로 프로젝트 루트 계산
BASE_DIR = pathlib.Path(__file__).resolve().parents[2]  # .../safe-monitoring-msdatashool

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
import os

# (1) Azure 설정
account_name = os.getenv("AZURE_STORAGE_ACCOUNT_NAME")
account_key = os.getenv("AZURE_STORAGE_ACCOUNT_KEY")
blob_service_client = BlobServiceClient(
    account_url=f"https://{account_name}.blob.core.windows.net",
    credential=account_key,
)
CONTAINER_NAME = "voice-uploads"

# (2) 오디오 업로드 라우트
@app.route("/upload-audio", methods=["POST"])
def upload_audio():
    if "file" not in request.files:
        return "file field missing", 400

    file = request.files["file"]
    filename = file.filename or f"audio-{datetime.utcnow().isoformat()}.webm"

    try:
        container_client = blob_service_client.get_container_client(CONTAINER_NAME)
        blob_client = container_client.get_blob_client(filename)
        blob_client.upload_blob(file, overwrite=True)
        print(f"[✅ 업로드 완료] {filename}")
        return jsonify({"status": "ok", "blob_name": filename}), 200
    except Exception as e:
        print("[❌ 업로드 오류]", e)
        return jsonify({"error": str(e)}), 500



if __name__ == "__main__":
    app.run(debug=True)
