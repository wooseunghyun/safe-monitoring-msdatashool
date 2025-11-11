from flask import Flask, render_template
from dotenv import load_dotenv
import os
import pathlib

# .env 읽기
load_dotenv()

# 현재 파일 기준으로 프로젝트 루트 계산
BASE_DIR = pathlib.Path(__file__).resolve().parents[2]  # .../safe-monitoring-msdatashool

app = Flask(
    __name__,
    template_folder=str(BASE_DIR / "templates"),
    static_folder=str(BASE_DIR / "static"),
)

@app.route("/")
def index():
    kakao_key = os.getenv("KAKAO_MAP_API_KEY", "")
    return render_template("index.html", kakao_key=kakao_key)

if __name__ == "__main__":
    # 0.0.0.0 으로 띄우면 나중에 다른 장치에서도 볼 수 있음
    app.run(debug=True)
