from flask import Blueprint, request, jsonify, current_app, render_template
import requests

bp = Blueprint("osrm", __name__)

@bp.get("/")
def index():
    return render_template("index.html", kakao_key=current_app.config["KAKAO_MAP_API_KEY"])

@bp.get("/api/route")
def api_route():
    start = request.args.get("start"); end = request.args.get("end")
    via = request.args.get("via"); profile = request.args.get("profile", "driving")
    if not start or not end:
        return jsonify({"error":"start and end required"}), 400

    def flip(s):
        lat, lng = s.split(","); return f"{lng},{lat}"

    coords = [flip(start)]
    if via: coords += [flip(v) for v in via.split(";")]
    coords.append(flip(end))
    coords_str = ";".join(coords)

    url = f"{current_app.config['OSRM_URL']}/route/v1/{profile}/{coords_str}"
    r = requests.get(url, params={"overview":"full","geometries":"geojson"}, timeout=5)
    r.raise_for_status()
    data = r.json()
    if not data.get("routes"): return jsonify({"error":"no route"}), 500
    return jsonify(data["routes"][0]["geometry"])
