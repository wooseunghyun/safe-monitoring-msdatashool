# scripts/server/main.py
from flask import Flask, render_template, redirect, url_for
from config import Settings                  # repo root의 config.py 사용
from scripts.server.routes.route_osrm import bp as osrm_bp
from scripts.server.routes.upload_audio import bp as upload_bp
from scripts.server.routes.telemetry import bp as telemetry_bp
from scripts.server.routes.live_peak import bp as live_peak_bp
from scripts.server.services import db as dbsvc
from scripts.server.routes.alerts import bp as alerts_bp
from scripts.server.routes.safe_route_ai import bp as safe_route_ai_bp

import pathlib

def create_app():
    app = Flask(
        __name__,
        template_folder=str(pathlib.Path(__file__).resolve().parents[2] / "templates"),
        static_folder=str(pathlib.Path(__file__).resolve().parents[2] / "static"),
    )
    app.config.from_object(Settings())
    dbsvc.init(app.config["SQLITE_PATH"])

    # 🔹 여기서 kakao_key를 템플릿에 항상 넣어주기
    @app.context_processor
    def inject_kakao_key():
        return {
            "kakao_key": app.config.get("KAKAO_MAP_API_KEY", "")
        }

    app.register_blueprint(osrm_bp)
    app.register_blueprint(upload_bp)
    app.register_blueprint(telemetry_bp)
    app.register_blueprint(live_peak_bp)
    app.register_blueprint(alerts_bp)
    app.register_blueprint(safe_route_ai_bp)

    # 1) /map : 우리가 만든 지도 페이지
    @app.route("/map")
    def map_page():
        return render_template("map_page.html", active_page="map")

    # 2) / : 접속하면 자동으로 /map 으로 보내기
    @app.route("/")
    def index():
        return redirect(url_for("map_page"))

    # 3) /dashboard : 대시보드
    @app.route("/dashboard")
    def dashboard_page():
        return render_template("dashboard_page.html", active_page="dashboard")


    @app.route("/login")
    def firebase_login():
        return render_template("login.html")

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
