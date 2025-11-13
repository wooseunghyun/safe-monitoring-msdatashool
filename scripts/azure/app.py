# app.py
import os
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient
from datetime import datetime

load_dotenv()  # .env 읽기

app = Flask(__name__)

account_name = os.getenv("AZURE_STORAGE_ACCOUNT_NAME")
account_key = os.getenv("AZURE_STORAGE_ACCOUNT_KEY")

# 계정 이름 + 키로 클라이언트 만들기
blob_service_client = BlobServiceClient(
    account_url=f"https://{account_name}.blob.core.windows.net",
    credential=account_key,
)

# 미리 만들어 둔 컨테이너 이름
CONTAINER_NAME = "voice-uploads"  # 포털에서 만든 이름과 같아야 함

@app.route("/upload-audio", methods=["POST"])
def upload_audio():
    if "file" not in request.files:
        return "file field missing", 400

    file = request.files["file"]
    filename = file.filename

    if not filename:
      iso = datetime.utcnow().isoformat().replace(":", "-").replace(".", "-")
      filename = f"audio-{iso}.webm"

    try:
        container_client = blob_service_client.get_container_client(CONTAINER_NAME)
        blob_client = container_client.get_blob_client(filename)
        blob_client.upload_blob(file, overwrite=True)
        return jsonify({"status": "ok", "blob": filename}), 200
    except Exception as e:
        print("Azure 업로드 오류:", e)
        return "upload failed", 500

if __name__ == "__main__":
    app.run(debug=True)
