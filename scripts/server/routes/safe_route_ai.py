# scripts/server/routes/safe_route_ai.py
import os
import math
import json
from flask import Blueprint, request, jsonify

# -----------------------
# Azure OpenAI 클라이언트
# -----------------------
from openai import AzureOpenAI

# 환경변수에서 설정 불러오기
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ROUTE_ENDPOINT")
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_ROUTE_API_KEY")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_ROUTE_API_VERSION", "2025-03-01-preview")

# 🔽 경로 추천에 쓸 모델/디플로이 이름
#    따로 ROUTE용 디플로이를 안 만들었다면,
#    일단은 TRANSCRIBE_DEPLOYMENT를 그대로 써도 됩니다. (추측입니다)
AZURE_OPENAI_ROUTE_DEPLOYMENT = (
    os.getenv("AZURE_OPENAI_ROUTE_DEPLOYMENT")
    or os.getenv("AZURE_OPENAI_TRANSCRIBE_DEPLOYMENT")
)

aoai_client = AzureOpenAI(
    azure_endpoint=AZURE_OPENAI_ENDPOINT,
    api_key=AZURE_OPENAI_API_KEY,
    api_version=AZURE_OPENAI_API_VERSION,
)

bp = Blueprint("safe_route_ai", __name__)


# -----------------------
# 거리 계산 유틸
# -----------------------
def distance_m(lat1, lng1, lat2, lng2):
    R = 6378137
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlng / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

# 🔹 start → wp1 → ... → end 의 총 직선거리(m)를 대략 계산
def path_length_m(start, end, waypoints):
    points = [start] + waypoints + [end]
    total = 0.0
    for i in range(len(points) - 1):
        a = points[i]
        b = points[i + 1]
        total += distance_m(a["lat"], a["lng"], b["lat"], b["lng"])
    return total

# -----------------------
# /api/safe_route_ai
# -----------------------
@bp.post("/api/safe_route_ai")
def safe_route_ai():
    """
    프론트에서 start/end + safety_pois(cctv+안심벨) 을 받으면,
    Azure OpenAI에게 '안전 경유지'를 추천받아 반환하는 엔드포인트.
    """
    data = request.get_json(force=True) or {}
    print("[safe_route_ai] input json:", data)  # ✅ 들어온 payload 확인

    start = data.get("start")
    end = data.get("end")
    pois = data.get("safety_pois") or []

    print("[safe_route_ai] start:", start, "end:", end)  # ✅ start/end
    print("[safe_route_ai] safety_pois 개수:", len(pois))  # ✅ POI 개수

    if not start or not end or not pois:
        # 입력이 불완전하면 그냥 빈 리스트 반환
        return jsonify({"waypoints": []}), 200

    try:
        s_lat = float(start["lat"])
        s_lng = float(start["lng"])
        e_lat = float(end["lat"])
        e_lng = float(end["lng"])
    except (KeyError, ValueError, TypeError):
        return jsonify({"waypoints": []}), 200

    base_dist = distance_m(s_lat, s_lng, e_lat, e_lng)

    # 1) 너무 먼 POI는 먼저 걸러서 토큰/연산 줄이기 (휴리스틱, 조정 가능)
    candidates = []
    for p in pois:
        try:
            plat = float(p["lat"])
            plng = float(p["lng"])
        except (KeyError, ValueError, TypeError):
            continue

        d_start = distance_m(s_lat, s_lng, plat, plng)
        d_end = distance_m(plat, plng, e_lat, e_lng)

        # 직선 거리의 1.6배 이상 detour는 제외 (추측값, 필요하면 조정)
        if d_start + d_end > base_dist * 1.6:
            continue

        candidates.append(
            {
                "name": p.get("name", ""),
                "type": p.get("type", ""),
                "lat": plat,
                "lng": plng,
                "d_start": round(d_start),
                "d_end": round(d_end),
            }
        )

    # 너무 많으면 출발지에서 가까운 것 50개만 사용
    candidates.sort(key=lambda x: x["d_start"])
    candidates = candidates[:50]

    user_desc = {
        "start": {"lat": s_lat, "lng": s_lng},
        "end": {"lat": e_lat, "lng": e_lng},
        "base_distance_m": round(base_dist),
        "candidates": candidates,
    }

    system_msg = (
        "You are a route-planning assistant for safe walking at night.\n"
        "Given a start point, an end point, and a list of candidate safety points "
        "(CCTV, emergency bells, etc.), choose up to 4 waypoints that make the route "
        "safer without causing a long detour.\n"
        "The total path length via the waypoints should be reasonably close to the "
        "straight-line distance between start and end (no huge loops).\n"
        "Return ONLY valid JSON with this exact schema:\n"
        '{\"waypoints\":[{\"lat\": number, \"lng\": number}]}\n'
        "Do not include any extra text or comments."
    )

    waypoints = []
    try:
        resp = aoai_client.chat.completions.create(
            model=AZURE_OPENAI_ROUTE_DEPLOYMENT,
            messages=[
                {"role": "system", "content": system_msg},
                {
                    "role": "user",
                    "content": "Here is the route and safety points:\n"
                    + json.dumps(user_desc, ensure_ascii=False),
                },
            ],
            temperature=0.2,
        )

        content = resp.choices[0].message.content
        print("[safe_route_ai] raw LLM content:", content)  # ✅ LLM 응답 전체

        parsed = json.loads(content)
        raw_wps = parsed.get("waypoints", []) or []

        # 🔸 lat/lng 없는 항목 정리 + 최대 3개로 제한
        cleaned = []
        for w in raw_wps:
            try:
                lat = float(w["lat"])
                lng = float(w["lng"])
            except (KeyError, ValueError, TypeError):
                continue
            cleaned.append({"lat": lat, "lng": lng})
        cleaned = cleaned[:3]

        # 🔸 전체 경로 길이 계산해서, 직선거리 대비 허용 비율 안이면 채택
        base_len = base_dist            # start~end 직선 거리(이미 위에서 계산)
        full_len = path_length_m(
            {"lat": s_lat, "lng": s_lng},
            {"lat": e_lat, "lng": e_lng},
            cleaned,
        )
        ratio = full_len / base_len if base_len > 0 else 999
        print(f"[safe_route_ai] base={base_len:.1f}m, full={full_len:.1f}m, ratio={ratio:.2f}")

        MAX_DETOUR_RATIO = 1.3  # 🔧 “너무 안 돌아가게” 싶으면 1.2~1.3 정도로 조절

        if ratio <= MAX_DETOUR_RATIO:
            waypoints = cleaned
        else:
            print("[safe_route_ai] detour too large → 경유지 사용 안 함")
            waypoints = []

        print("[safe_route_ai] final waypoints:", waypoints)

    except Exception as e:
        print("[safe_route_ai] OpenAI error:", e)
        waypoints = []

    return jsonify({"waypoints": waypoints}), 200
