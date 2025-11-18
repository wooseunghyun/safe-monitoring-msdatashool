# scripts/server/main.py
from flask import Flask
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

    app.register_blueprint(osrm_bp)
    app.register_blueprint(upload_bp)
    app.register_blueprint(telemetry_bp)
    app.register_blueprint(live_peak_bp)
    app.register_blueprint(alerts_bp)
    app.register_blueprint(safe_route_ai_bp)

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
