// static/js/map.js
kakao.maps.load(function () {
  // ===============================
  // 기본 설정
  // ===============================
  const USE_OSRM = true;          // OSRM 먼저 시도
  const OSRM_PROFILE = "foot";    // 서버가 foot 지원하면 foot, 아니면 driving

  // 1) 지도 기본
  const map = new kakao.maps.Map(document.getElementById("map"), {
    center: new kakao.maps.LatLng(37.5665, 126.9780),
    level: 7,
  });

  // =====================================
  // A. CCTV 불러와서 표시 + 전역에 저장
  // =====================================
  let cctvData = [];
  let cctvMarkers = [];
  const cctvClusterer = new kakao.maps.MarkerClusterer({
    map: map,
    averageCenter: true,
    minLevel: 6,
  });
  const cctvIcon = new kakao.maps.MarkerImage(
    "/static/img/cctv.svg",
    new kakao.maps.Size(32, 32)   // 아이콘 크기(px)
  );

  fetch("/static/data/cctv.json")
    .then(res => res.json())
    .then(data => {
      cctvData = data;

      cctvMarkers = data
        .filter(d => d.lat && d.lng)
        .map(d => new kakao.maps.Marker({
          position: new kakao.maps.LatLng(d.lat, d.lng),
          title: d.name || "",
          image: cctvIcon
        }));

      cctvClusterer.addMarkers(cctvMarkers);
      console.log("CCTV loaded:", cctvMarkers.length);
    });

  document.getElementById("toggle-cctv").addEventListener("change", function (e) {
    if (e.target.checked) cctvClusterer.addMarkers(cctvMarkers);
    else cctvClusterer.clear();
  });

  // 🔸 AI 경로 추천용 데이터
  let safetyPOIs = [];   // CCTV + 안심벨 합친 배열
  let aiWaypoints = [];  // Azure OpenAI가 추천한 경유지
  let useSafeRoute = false;  // AI 경로 모드 ON/OFF

  // =====================================
  // C. 안심벨 불러와서 표시 + 전역에 저장
  // =====================================
  let bellData = [];
  let bellMarkers = [];
  const bellIcon = new kakao.maps.MarkerImage(
    "/static/img/bell.svg",
    new kakao.maps.Size(32, 32)   // 아이콘 크기(px)
  );
  const bellClusterer = new kakao.maps.MarkerClusterer({
    map: map,
    averageCenter: true,
    minLevel: 6,
  });

  fetch("/static/data/safe_bells.json")
    .then(res => res.json())
    .then(data => {
      bellData = data;

      bellMarkers = data
        .filter(d => d.lat && d.lng)
        .map(d => new kakao.maps.Marker({
          position: new kakao.maps.LatLng(d.lat, d.lng),
          title: d.name || "",
          image: bellIcon  // 나중에 안심벨 전용 아이콘 쓰고 싶으면 여기 추가
        }));

      bellClusterer.addMarkers(bellMarkers);
      console.log("Bells loaded:", bellMarkers.length);

      // 🔸 CCTV + 안심벨 합쳐서 보관 (AI 경로 추천용)
      safetyPOIs = cctvData.concat(bellData);
    });

  // 체크박스로 on/off
  document.getElementById("toggle-bells").addEventListener("change", function (e) {
    if (e.target.checked) bellClusterer.addMarkers(bellMarkers);
    else bellClusterer.clear();
  });




  // =====================================
  // B. 출발/도착 마커 (드래그로 위치 지정)
  // =====================================

  const startIcon = new kakao.maps.MarkerImage(
    "/static/img/start.svg",
    new kakao.maps.Size(32, 32)   // 아이콘 크기(px)
  );

  const endIcon = new kakao.maps.MarkerImage(
    "/static/img/end.svg",
    new kakao.maps.Size(32, 32)   // 아이콘 크기(px)
  );

  // 출발 마커
  const startMarker = new kakao.maps.Marker({
    position: new kakao.maps.LatLng(37.5665, 126.9780),
    draggable: true,
    map: map,
    image: startIcon
  });

  // 도착 마커
  const endMarker = new kakao.maps.Marker({
    position: new kakao.maps.LatLng(37.5650, 126.9780),
    draggable: true,
    map: map,
    image: endIcon
  });

  // ✅ 여기서 단 한 번만 routeState 선언
  const routeState = {
    start: {
      lat: startMarker.getPosition().getLat(),
      lng: startMarker.getPosition().getLng(),
      name: "start",
    },
    end: {
      lat: endMarker.getPosition().getLat(),
      lng: endMarker.getPosition().getLng(),
      name: "end",
    },
    waypoints: [],
  };

// HTTPS 환경(또는 localhost)에서만 위치 정보 접근이 허용됨
// ✅ 내 GPS 위치를 가져와서 출발지/도착지로 설정 (서울시청 fallback)
if (navigator.geolocation) {
  navigator.geolocation.getCurrentPosition(
    (pos) => {
      // ✅ 위치 가져오기 성공
      const lat = pos.coords.latitude;
      const lng = pos.coords.longitude;
      const myLatLng = new kakao.maps.LatLng(lat, lng);

      // 출발 마커 설정
      startMarker.setPosition(myLatLng);
      map.setCenter(myLatLng);

      // routeState 출발지 갱신
      routeState.start = { lat, lng, name: "내 위치" };

      // 도착지는 내 위치에서 남쪽으로 200m 떨어진 곳
      const offsetMeters = 200;
      const offsetLat = lat - (offsetMeters / 111320);
      const destLatLng = new kakao.maps.LatLng(offsetLat, lng);

      endMarker.setPosition(destLatLng);
      routeState.end = { lat: offsetLat, lng, name: "임시 도착지(200m 남쪽)" };

      refreshRoute();

      console.log("📍 GPS 성공: 현재 위치로 출발지 설정, 200m 남쪽에 도착지 설정");
    },
    (err) => {
      // ⚠️ 위치 접근 실패 시 fallback
      console.warn("⚠️ 위치 접근 실패:", err);
      alert("위치 정보를 불러올 수 없습니다. 서울시청을 기준으로 설정합니다.");

      const lat = 37.5665;  // 서울시청 위도
      const lng = 126.9780; // 서울시청 경도

      const startLatLng = new kakao.maps.LatLng(lat, lng);
      const endLat = lat - (200 / 111320); // 200m 남쪽
      const endLatLng = new kakao.maps.LatLng(endLat, lng);

      // 출발/도착 마커 위치 설정
      startMarker.setPosition(startLatLng);
      endMarker.setPosition(endLatLng);
      map.setCenter(startLatLng);

      // routeState 갱신
      routeState.start = { lat, lng, name: "서울시청(기본값)" };
      routeState.end = { lat: endLat, lng, name: "임시 도착지(200m 남쪽)" };

      refreshRoute();

      console.log("📍 fallback: 서울시청을 기준으로 출발지 설정");
    }
  );
} else {
  alert("이 브라우저는 위치 정보를 지원하지 않습니다. 서울시청을 기준으로 설정합니다.");

  const lat = 37.5665;
  const lng = 126.9780;
  const startLatLng = new kakao.maps.LatLng(lat, lng);
  const endLat = lat - (200 / 111320);
  const endLatLng = new kakao.maps.LatLng(endLat, lng);

  startMarker.setPosition(startLatLng);
  endMarker.setPosition(endLatLng);
  map.setCenter(startLatLng);

  routeState.start = { lat, lng, name: "서울시청(기본값)" };
  routeState.end = { lat: endLat, lng, name: "임시 도착지(200m 남쪽)" };

  refreshRoute();
}


  // 지도에서 그려진 선들 저장용
  let routeSegments = [];

  // 지오코더는 당장 안 써도 일단 만들어둠 (나중에 주소 입력 다시 살릴 때 쓰려고)
  const geocoder = new kakao.maps.services.Geocoder();

  // ---------------------------------------
  // 유틸 함수들
  // ---------------------------------------
  function distanceMeters(lat1, lng1, lat2, lng2) {
    const R = 6378137;
    const dLat = (lat2 - lat1) * Math.PI / 180;
    const dLng = (lng2 - lng1) * Math.PI / 180;
    const a =
      Math.sin(dLat/2) * Math.sin(dLat/2) +
      Math.cos(lat1 * Math.PI/180) * Math.cos(lat2 * Math.PI/180) *
      Math.sin(dLng/2) * Math.sin(dLng/2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
    return R * c;
  }

  function pointToSegmentDistanceMeters(px, py, x1, y1, x2, y2) {
    const A = px - x1;
    const B = py - y1;
    const C = x2 - x1;
    const D = y2 - y1;

    const dot = A * C + B * D;
    const len_sq = C * C + D * D;
    let param = -1;
    if (len_sq !== 0) param = dot / len_sq;

    let xx, yy;
    if (param < 0) { xx = x1; yy = y1; }
    else if (param > 1) { xx = x2; yy = y2; }
    else {
      xx = x1 + param * C;
      yy = y1 + param * D;
    }

    return distanceMeters(py, px, yy, xx);
  }
  const RADIUS = 40;

  function calcCctvScoreNearSegment(p1, p2, radiusMeters) {
    if (!cctvData || cctvData.length === 0) return 0;
    let count = 0;
    for (const c of cctvData) {
      const d = pointToSegmentDistanceMeters(
        c.lng, c.lat,
        p1.lng, p1.lat,
        p2.lng, p2.lat
      );
      if (d <= radiusMeters) count++;
    }
    return count;
  }

  // ✅ CCTV + 안심벨 모두 반영해서 "안전 점수" 계산
function calcSafetyScoreNearSegment(p1, p2, radiusMeters) {
  let score = 0;

  // CCTV 반경 (조금 좁게, 예: 50m)
  const CCTV_RADIUS = 40;

  if (cctvData && cctvData.length) {
    for (const c of cctvData) {
      const d = pointToSegmentDistanceMeters(
        c.lng, c.lat,
        p1.lng, p1.lat,
        p2.lng, p2.lat
      );
      if (d <= CCTV_RADIUS) {
        score += 1;          // CCTV 1점 (원하면 가중치 조절 가능)
      }
    }
  }

  // 안심벨 반경 (조금 더 빡빡하게, 예: 30m)
  const BELL_RADIUS = 30;

  if (bellData && bellData.length) {
    for (const b of bellData) {
      const d = pointToSegmentDistanceMeters(
        b.lng, b.lat,
        p1.lng, p1.lat,
        p2.lng, p2.lat
      );
      if (d <= BELL_RADIUS) {
        score += 2;          // 안심벨은 2점 정도로 더 중요하게 (원하면 변경)
      }
    }
  }

  return score;
}


  function pickColorByScore(score) {
    if (score >= 3) return "#27ae60";
    if (score >= 1) return "#f1c40f";
    return "#e74c3c";
  }

  // ---------------------------------------
  // 기존 직선 그리기 버전
  // ---------------------------------------
  function drawRouteColored(points) {
    routeSegments.forEach(seg => seg.setMap(null));
    routeSegments = [];

    if (!points || points.length < 2) return;

    const bounds = new kakao.maps.LatLngBounds();

    for (let i = 0; i < points.length - 1; i++) {
      const p1 = points[i];
      const p2 = points[i + 1];

      // const score = calcCctvScoreNearSegment(p1, p2, RADIUS);
      const score = calcSafetyScoreNearSegment(p1, p2, RADIUS);
      const color = pickColorByScore(score);

      const line = new kakao.maps.Polyline({
        path: [
          new kakao.maps.LatLng(p1.lat, p1.lng),
          new kakao.maps.LatLng(p2.lat, p2.lng)
        ],
        strokeWeight: 6,
        strokeColor: color,
        strokeOpacity: 0.9,
        strokeStyle: 'solid'
      });
      line.setMap(map);
      routeSegments.push(line);

      bounds.extend(new kakao.maps.LatLng(p1.lat, p1.lng));
      bounds.extend(new kakao.maps.LatLng(p2.lat, p2.lng));
    }

    map.setBounds(bounds);
  }

  // ---------------------------------------
  // OSRM 경로 그리기
  // ---------------------------------------
  async function drawOsrmRoute(start, end, waypoints) {
    const params = new URLSearchParams();
    params.set("start", `${start.lat},${start.lng}`);
    params.set("end", `${end.lat},${end.lng}`);
    if (waypoints && waypoints.length) {
      params.set(
        "via",
        waypoints.map(w => `${w.lat},${w.lng}`).join(";")
      );
    }
    params.set("profile", OSRM_PROFILE);

    const res = await fetch(`/api/route?${params.toString()}`);
    if (!res.ok) throw new Error("OSRM 요청 실패");
    const geojson = await res.json();   // {type:"LineString", coordinates:[ [lng,lat], ... ]}

    routeSegments.forEach(seg => seg.setMap(null));
    routeSegments = [];

    const coords = geojson.coordinates;
    const bounds = new kakao.maps.LatLngBounds();

    for (let i = 0; i < coords.length - 1; i++) {
      const [lng1, lat1] = coords[i];
      const [lng2, lat2] = coords[i + 1];

      const p1 = { lat: lat1, lng: lng1 };
      const p2 = { lat: lat2, lng: lng2 };

      // const score = calcCctvScoreNearSegment(p1, p2, RADIUS);
      const score = calcSafetyScoreNearSegment(p1, p2, RADIUS);
      const color = pickColorByScore(score);

      const line = new kakao.maps.Polyline({
        path: [
          new kakao.maps.LatLng(lat1, lng1),
          new kakao.maps.LatLng(lat2, lng2)
        ],
        strokeWeight: 6,
        strokeColor: color,
        strokeOpacity: 0.9,
        strokeStyle: 'solid'
      });
      line.setMap(map);
      routeSegments.push(line);

      bounds.extend(new kakao.maps.LatLng(lat1, lng1));
      bounds.extend(new kakao.maps.LatLng(lat2, lng2));
    }

    map.setBounds(bounds);
  }

  // ---------------------------------------
  // 라우트 다시 그리기 (OSRM 우선)
  // ---------------------------------------
  async function refreshRoute() {
    if (!routeState.start || !routeState.end) return;

    // 기본: 사용자가 우클릭으로 넣은 경유지
    let finalWaypoints = routeState.waypoints ? [...routeState.waypoints] : [];

    // AI 경로 모드가 켜져 있으면, Azure OpenAI가 추천한 경유지를 추가
    if (useSafeRoute && aiWaypoints.length) {
      finalWaypoints = finalWaypoints.concat(aiWaypoints);
    }

    if (USE_OSRM) {
      try {
        await drawOsrmRoute(
          routeState.start,
          routeState.end,
          finalWaypoints
        );
        return;
      } catch (err) {
        console.warn("OSRM 실패, 직선 fallback:", err);
      }
    }

    const pts = [routeState.start, ...finalWaypoints, routeState.end];
    drawRouteColored(pts);
  }

  // ---------------------------------------
  // 마커 드래그 이벤트 → routeState 갱신
  // ---------------------------------------
  kakao.maps.event.addListener(startMarker, 'dragend', async function () {
    const pos = startMarker.getPosition();
    routeState.start = {
      lat: pos.getLat(),
      lng: pos.getLng(),
      name: "start"
    };
    await refreshRoute();
  });

  kakao.maps.event.addListener(endMarker, 'dragend', async function () {
    const pos = endMarker.getPosition();
    routeState.end = {
      lat: pos.getLat(),
      lng: pos.getLng(),
      name: "end"
    };
    await refreshRoute();
  });

  // ---------------------------------------
  // 경로 초기화 버튼
  // ---------------------------------------
  function clearRoute() {
    routeState.waypoints = [];
    routeSegments.forEach(seg => seg.setMap(null));
    routeSegments = [];
  }

  document.getElementById("btn-reset").addEventListener("click", () => {
    clearRoute();
  });

  // ---------------------------------------
  // 경유지 관련 (기존 그대로)
  // ---------------------------------------
  function orderWaypointsByBestInsertion(start, end, waypoints) {
    if (!start || !end) return waypoints;
    if (!waypoints || waypoints.length === 0) return [];

    const remaining = [...waypoints].sort((a, b) => {
      const da = distanceMeters(start.lat, start.lng, a.lat, a.lng);
      const db = distanceMeters(start.lat, start.lng, b.lat, b.lng);
      return da - db;
    });

    const path = [start, end];

    while (remaining.length > 0) {
      const wp = remaining.shift();
      let bestPos = 1;
      let bestCost = Infinity;

      for (let i = 0; i < path.length - 1; i++) {
        const a = path[i];
        const b = path[i + 1];

        const before = distanceMeters(a.lat, a.lng, b.lat, b.lng);
        const after =
          distanceMeters(a.lat, a.lng, wp.lat, wp.lng) +
          distanceMeters(wp.lat, wp.lng, b.lat, b.lng);

        const extra = after - before;
        if (extra < bestCost) {
          bestCost = extra;
          bestPos = i + 1;
        }
      }

      path.splice(bestPos, 0, wp);
    }

    return path.slice(1, path.length - 1);
  }

  function refine2opt(points) {
    let improved = true;
    while (improved) {
      improved = false;
      for (let i = 1; i < points.length - 2; i++) {
        for (let j = i + 1; j < points.length - 1; j++) {
          const d1 =
            distanceMeters(points[i - 1].lat, points[i - 1].lng, points[i].lat, points[i].lng) +
            distanceMeters(points[j].lat, points[j].lng, points[j + 1].lat, points[j + 1].lng);
          const d2 =
            distanceMeters(points[i - 1].lat, points[i - 1].lng, points[j].lat, points[j].lng) +
            distanceMeters(points[i].lat, points[i].lng, points[j + 1].lat, points[j + 1].lng);

          if (d2 + 0.01 < d1) {
            const sub = points.slice(i, j + 1).reverse();
            points.splice(i, j - i + 1, ...sub);
            improved = true;
          }
        }
      }
    }
    return points;
  }

  document.getElementById("btn-sort").addEventListener("click", async () => {
    if (!routeState.start || !routeState.end) return;
    if (!routeState.waypoints.length) return;

    const ordered = orderWaypointsByBestInsertion(
      routeState.start,
      routeState.end,
      routeState.waypoints
    );

    const full = [routeState.start, ...ordered, routeState.end];
    const refined = refine2opt(full);

    routeState.waypoints = refined.slice(1, refined.length - 1);

    await refreshRoute();
  });

  // ---------------------------------------
  // AI 안전 경로 토글 버튼
  // ---------------------------------------
  const safeRouteBtn = document.getElementById("btn-safe-route");

  if (safeRouteBtn) {
    safeRouteBtn.addEventListener("click", async () => {
      console.log("🟢 safe-route 버튼 클릭됨");   // ← 이 한 줄 추가
      if (!routeState.start || !routeState.end) {
        alert("출발지와 도착지가 먼저 설정되어야 합니다.");
        return;
      }

      // 👇 OFF → ON 으로 바꾸는 순간에만 서버(Azure OpenAI)에게 요청
      if (!useSafeRoute) {
        if (!safetyPOIs.length) {
          alert("CCTV/안심벨 데이터가 아직 로딩되지 않았습니다. 잠시 후 다시 시도해 주세요.");
          return;
        }

        try {
          safeRouteBtn.textContent = "🔄 AI 경로 계산 중...";
          safeRouteBtn.disabled = true;

          const payload = {
            start: routeState.start,
            end: routeState.end,
            safety_pois: safetyPOIs,   // CCTV + 안심벨
          };

          const res = await fetch("/api/safe_route_ai", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
          });

          if (!res.ok) {
            console.error("safe_route_ai 실패:", await res.text());
            alert("AI 경로 계산에 실패했습니다.");
            safeRouteBtn.textContent = "🔒 AI 경로 OFF";
            safeRouteBtn.disabled = false;
            return;
          }

          const data = await res.json();
          aiWaypoints = data.waypoints || [];
          console.log("AI가 추천한 경유지:", aiWaypoints);

          useSafeRoute = true;
          safeRouteBtn.textContent = "🔒 AI 경로 ON";
          safeRouteBtn.disabled = false;

          await refreshRoute();
        } catch (e) {
          console.error("safe_route_ai 호출 오류:", e);
          alert("AI 경로 호출 중 오류가 발생했습니다.");
          safeRouteBtn.textContent = "🔒 AI 경로 OFF";
          safeRouteBtn.disabled = false;
        }
      } else {
        // 👇 이미 ON인 상태 → OFF로 전환
        useSafeRoute = false;
        aiWaypoints = [];
        safeRouteBtn.textContent = "🔒 AI 경로 OFF";
        await refreshRoute();
      }
    });
  }



  // 지도 우클릭으로 경유지 추가
  kakao.maps.event.addListener(map, "rightclick", async (mouseEvent) => {
    const latlng = mouseEvent.latLng;
    routeState.waypoints.push({
      lat: latlng.getLat(),
      lng: latlng.getLng(),
      name: "waypoint"
    });
    await refreshRoute();
  });

  // =====================================
  //  출발지 초기화 버튼
  // =====================================

// ✅ 내 위치 버튼
document.getElementById("btn-my-location").addEventListener("click", () => {
  goToMyLocation();
});

// ✅ 실제로 내 위치로 이동하는 함수
async function goToMyLocation() {
  if (!navigator.geolocation) {
    alert("이 브라우저는 위치 정보를 지원하지 않습니다. 서울시청으로 이동합니다.");
    setFallbackToCityHall();
    return;
  }

  navigator.geolocation.getCurrentPosition(
    (pos) => {
      const lat = pos.coords.latitude;
      const lng = pos.coords.longitude;
      const myLatLng = new kakao.maps.LatLng(lat, lng);

      // 출발지 마커 이동
      startMarker.setPosition(myLatLng);
      map.setCenter(myLatLng);

      // routeState 갱신
      routeState.start = { lat, lng, name: "내 위치" };

      // 도착지는 200m 남쪽 (필요 없으면 이 부분 지워도 됨)
      const offsetMeters = 200;
      const offsetLat = lat - (offsetMeters / 111320);
      const destLatLng = new kakao.maps.LatLng(offsetLat, lng);
      endMarker.setPosition(destLatLng);
      routeState.end = { lat: offsetLat, lng, name: "임시 도착지(200m 남쪽)" };

      // 경로 다시 그림
      refreshRoute();
    },
    (err) => {
      console.warn("위치 접근 실패:", err);
      alert("위치 정보를 불러올 수 없습니다. 서울시청으로 이동합니다.");
      setFallbackToCityHall();
    }
  );
}

// ✅ fallback을 함수로 빼둠
function setFallbackToCityHall() {
  const lat = 37.5665;
  const lng = 126.9780;
  const startLatLng = new kakao.maps.LatLng(lat, lng);
  const endLat = lat - (200 / 111320);
  const endLatLng = new kakao.maps.LatLng(endLat, lng);

  startMarker.setPosition(startLatLng);
  endMarker.setPosition(endLatLng);
  map.setCenter(startLatLng);

  routeState.start = { lat, lng, name: "서울시청(기본값)" };
  routeState.end = { lat: endLat, lng, name: "임시 도착지(200m 남쪽)" };

  refreshRoute();
}

  // =====================================
  // 🚨 신고 배너 UI + 상태 조회 + 신고 취소
  // =====================================
  const alertBanner = document.getElementById("alert-banner");
  const alertCancelBtn = document.getElementById("alert-cancel-btn");

  function setAlertUI(isAlerting) {
    if (!alertBanner) return;  // 템플릿에 없으면 무시
    alertBanner.style.display = isAlerting ? "flex" : "none";
  }

  async function fetchAlertStatus() {
    try {
      const res = await fetch("/api/alerts/status");
      if (!res.ok) return;

      const data = await res.json();
      if (!data || typeof data.alerting === "undefined") return;

      setAlertUI(data.alerting);
    } catch (err) {
      console.error("alert status error", err);
    }
  }

  if (alertCancelBtn) {
    alertCancelBtn.addEventListener("click", async () => {
      if (!confirm("정말 신고를 중지하시겠습니까?")) return;

      try {
        const res = await fetch("/api/alerts/cancel", { method: "POST" });
        if (res.ok) {
          setAlertUI(false);
        }
      } catch (err) {
        console.error("alert cancel error", err);
      }
    });
  }

  // =====================================
  // 🎙 음성 녹음 & 업로드 (서버 경유 버전) + user_id 포함
  // =====================================
  const recordBtn = document.getElementById("btn-record");
  const recordStatus = document.getElementById("rec-status");

  let mediaRecorder = null;
  let audioStream = null;
  let isRecording = false;

  // dB 측정을 위한 오디오 분석용
  let audioCtx = null;
  let analyser = null;
  let dataBuf = null;
  let dbInterval = null;

  // 세그먼트 녹음을 위한 변수
  let chunks = [];          // 한 세그먼트(파일)의 조각들
  let segmentTimer = null;  // N초 뒤에 stop() 호출 타이머

  // 한 파일 길이 (ms 단위) – 원하면 5000(5초), 60000(1분) 등으로 조절
  const SEGMENT_MS = 5_000;   // 10초마다 완전한 webm 파일 1개씩 생성

  // 0) user_id 생성/보관 (브라우저 최초 1회)
  function getOrCreateUserId() {
    const KEY = "safe_user_id";
    let uid = window.localStorage.getItem(KEY);
    if (!uid) {
      uid = (crypto && crypto.randomUUID)
        ? crypto.randomUUID()
        : "uid-" + Math.random().toString(36).slice(2);
      window.localStorage.setItem(KEY, uid);
    }
    return uid;
  }
  const USER_ID = getOrCreateUserId(); // 전역 보관

  recordBtn.addEventListener("click", async () => {
    if (!isRecording) {
      await startRecording();
    } else {
      stopRecording();
    }
  });

  // ✅ 텔레메트리 전송 함수
  async function sendTelemetry(evt) {
    try {
      await fetch("/telemetry", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(evt)
      });
    } catch (e) {
      console.warn("telemetry send failed", e);
    }
  }

  // dB 기준 잡기 (원하면 버튼 따로 만들어서 호출)
  async function calibrateSilence() {
    if (!analyser || !dataBuf) {
      alert("녹음이 시작된 상태에서만 캘리브레이션 가능합니다.");
      return;
    }
    const samples = [];
    const start = performance.now();
    while (performance.now() - start < 3000) { // 3초
      analyser.getFloatTimeDomainData(dataBuf);
      let peak = 0;
      for (let i = 0; i < dataBuf.length; i++) {
        const v = Math.abs(dataBuf[i]);
        if (v > peak) peak = v;
      }
      samples.push(20 * Math.log10(peak || 1e-8));
      await new Promise(r => setTimeout(r, 200)); // 0.2초 간격
    }
    const avg = samples.reduce((a, b) => a + b, 0) / samples.length;
    localStorage.setItem("baseline_db", avg.toFixed(1));
    alert(`기준 소음 레벨: ${avg.toFixed(1)} dBFS`);
  }


  // 🔸 10초 동안 측정한 피크 dB를 live_uploads에 보내는 함수
  async function sendPeakToLiveUploads(peakDb) {
    try {
      // 위치는 우선 routeState.start 기준으로 보냄 (GPS → 출발지에 이미 반영되어 있음)
      const start = routeState.start || {};
      const lat = start.lat ?? null;
      const lng = start.lng ?? null;

      const payload = {
        user_id: USER_ID,
        ts: new Date().toISOString(),
        peak_db: peakDb,
        lat,
        lng,
        window_sec: 10   // 대략 10초짜리 윈도우라는 뜻
      };

      const res = await fetch("/api/live_peak", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        console.warn("live_peak 전송 실패:", await res.text());
      } else {
        console.log("✅ live_peak 전송 완료:", peakDb.toFixed(1), "dB");
      }
    } catch (e) {
      console.warn("live_peak 전송 중 오류:", e);
    }
  }

  // 🔄 계속 측정하면서, 10초마다 "그 구간의 피크 dB"만 서버로 보내는 루프
  // function startDbLoop() {
  //   if (dbInterval) clearInterval(dbInterval);

  //   let windowPeakDb = -1000;          // 현재 10초 구간에서의 최대값
  //   let windowStart = performance.now();

  //   dbInterval = setInterval(async () => {
  //     if (!analyser || !dataBuf) return;

  //     // 1) 지금 시점의 instantaneous peak dB 계산
  //     analyser.getFloatTimeDomainData(dataBuf);
  //     let peak = 0;
  //     for (let i = 0; i < dataBuf.length; i++) {
  //       const v = Math.abs(dataBuf[i]);
  //       if (v > peak) peak = v;
  //     }
  //     const currentDb = 20 * Math.log10(peak || 1e-8);

  //     // 2) windowPeakDb 갱신
  //     if (currentDb > windowPeakDb) {
  //       windowPeakDb = currentDb;
  //     }

  //     // 3) 10초 지났으면 서버로 전송하고 윈도우 초기화
  //     const now = performance.now();
  //     const elapsed = (now - windowStart) / 1000.0;

  //     if (elapsed >= 10) {
  //       if (windowPeakDb > -900) {  // 유효한 값이 있을 때만 전송
  //         await sendPeakToLiveUploads(windowPeakDb);
  //       }
  //       // 새 윈도우 시작
  //       windowPeakDb = -1000;
  //       windowStart = now;
  //     }

  //   }, 300); // 0.3초마다 한 번씩 샘플링 (너무 자주 말고, 적당히 자주)
  // }

  // ✅ 현재 위치를 한 번만 가져오는 Promise 함수
  function getCurrentPositionOnce(timeoutMs = 3000) {
    return new Promise((resolve) => {
      if (!navigator.geolocation) {
        console.warn("이 브라우저는 위치 정보를 지원하지 않습니다.");
        resolve(null);
        return;
      }

      let done = false;

      function ok(pos) {
        if (done) return;
        done = true;
        resolve({
          lat: pos.coords.latitude,
          lng: pos.coords.longitude,
        });
      }

      function err(e) {
        if (done) return;
        console.warn("getCurrentPositionOnce 에러:", e);
        done = true;
        resolve(null); // 실패하면 null로 넘기고, 나중에 fallback 쓰게 함
      }

      navigator.geolocation.getCurrentPosition(ok, err, {
        enableHighAccuracy: true,
        timeout: timeoutMs,
        maximumAge: 5000, // 최근 위치 5초 이내면 재사용
      });
    });
  }


  //데시벨 저장
  let windowPeakDb = -1000;

  function startDbLoop() {
    if (dbInterval) clearInterval(dbInterval);

    dbInterval = setInterval(() => {
      if (!analyser || !dataBuf) return;

      analyser.getFloatTimeDomainData(dataBuf);
      let peak = 0;
      for (let i = 0; i < dataBuf.length; i++) {
        peak = Math.max(peak, Math.abs(dataBuf[i]));
      }

      const db = 20 * Math.log10(peak || 1e-8);
      if (!isNaN(db)) {
        windowPeakDb = Math.max(windowPeakDb, db);
      }

    }, 250);
  }



  // 🎙 녹음 시작(사용자가 버튼 누를 때 한 번만 호출)
  async function startRecording() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      audioStream = stream;

      // dB 측정을 위한 AudioContext 초기화
      audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      const src = audioCtx.createMediaStreamSource(stream);
      analyser = audioCtx.createAnalyser();
      analyser.fftSize = 2048;
      src.connect(analyser);
      dataBuf = new Float32Array(analyser.fftSize);

      startDbLoop();

      isRecording = true;
      recordBtn.textContent = "⏹ 녹음 중지";
      recordStatus.textContent = "녹음 중...";

      // ✅ 첫 번째 세그먼트 시작
      startNewSegment();

    } catch (err) {
      console.error("녹음 시작 실패:", err);
      recordStatus.textContent = "녹음 시작 실패(콘솔 확인)";
    }
  }

  // 🎙 세그먼트(한 덩어리) 녹음 시작
  function startNewSegment() {
    if (!audioStream) return;

    chunks = [];

    const preferredType = "audio/webm; codecs=opus";
    if (MediaRecorder.isTypeSupported(preferredType)) {
      mediaRecorder = new MediaRecorder(audioStream, { mimeType: preferredType });
    } else {
      mediaRecorder = new MediaRecorder(audioStream);
    }

    console.log("opus 지원 여부:", MediaRecorder.isTypeSupported("audio/webm; codecs=opus"));
    console.log("실제 mediaRecorder.mimeType:", mediaRecorder.mimeType);

    // 조각 저장
    mediaRecorder.ondataavailable = (event) => {
      if (event.data && event.data.size > 0) {
        chunks.push(event.data);
      }
    };

    // 한 세그먼트가 끝났을 때(완전한 파일 하나가 완성될 때)
    mediaRecorder.onstop = async () => {
      try {
        const blob = new Blob(chunks, {
          type: mediaRecorder.mimeType || "audio/webm"
        });

        await uploadToServer(blob);

        // 전체 녹음이 아직 켜져 있다면 다음 세그먼트 시작
        if (isRecording) {
          startNewSegment();
        }
      } catch (e) {
        console.error("세그먼트 업로드 중 오류:", e);
      }
    };

    // 🔴 중요: timeslice 없이 start()
    mediaRecorder.start();

    // SEGMENT_MS 후에 stop() 호출해서 세그먼트 종료
    if (segmentTimer) clearTimeout(segmentTimer);
    segmentTimer = setTimeout(() => {
      if (mediaRecorder && mediaRecorder.state === "recording") {
        mediaRecorder.stop();
      }
    }, SEGMENT_MS);
  }

  // 🎙 녹음 중지 (사용자가 버튼 누를 때)
  function stopRecording() {
    isRecording = false;   // ✅ 더 이상 새 세그먼트 시작하지 않도록

    if (dbInterval) {
      clearInterval(dbInterval);
      dbInterval = null;
    }

    if (segmentTimer) {
      clearTimeout(segmentTimer);
      segmentTimer = null;
    }

    if (mediaRecorder && mediaRecorder.state === "recording") {
      mediaRecorder.stop();   // 마지막 세그먼트 하나 더 만들고 끝
    }

    if (audioStream) {
      audioStream.getTracks().forEach(t => t.stop());
      audioStream = null;
    }

    if (audioCtx) {
      // 일부 브라우저는 close() 필요, 일부는 없어도 되지만 있으면 깔끔
      try { audioCtx.close(); } catch (e) {}
      audioCtx = null;
    }

    recordBtn.textContent = "🎙 녹음 시작";
    recordStatus.textContent = "녹음 중지됨.";
  }

  // 서버 업로드 (기존 것 거의 그대로 사용)
  async function uploadToServer(blob) {
    const iso = new Date().toISOString().replace(/[:.]/g, "-");
    const fileName = `audio-${iso}.webm`;

    const formData = new FormData();
    formData.append("file", blob, fileName);
    formData.append("user_id", USER_ID);
    formData.append("ts", new Date().toISOString());

    // 🔥 세그먼트 동안 측정된 peak_db
    formData.append("peak_db", windowPeakDb.toString());

    // 🔹 ① 우선: 이 순간의 실제 GPS 위치를 가져와 본다
    const geo = await getCurrentPositionOnce();
    if (geo && geo.lat && geo.lng) {
      // ✅ 현재 위치를 그대로 저장
      formData.append("lat", geo.lat);
      formData.append("lon", geo.lng);
    } else if (routeState.start && routeState.start.lat && routeState.start.lng) {
      // 🔁 GPS 실패하면 fallback: 현재 routeState 출발지
      formData.append("lat", routeState.start.lat);
      formData.append("lon", routeState.start.lng);
  }
  // 둘 다 없으면 위치 없이 저장

    try {
      const res = await fetch("/upload-audio", {
        method: "POST",
        body: formData
      });

      if (!res.ok) {
        console.error("서버 업로드 실패", await res.text());
        recordStatus.textContent = "서버 업로드 실패";
      } else {
        recordStatus.textContent = `서버 업로드 성공: ${fileName}`;
      }
    } catch (err) {
      console.error("서버 전송 오류:", err);
      recordStatus.textContent = "서버 전송 오류";
    }
    
    // 🔥 파일 1개 업로드 후 peak_db 리셋
    windowPeakDb = -1000;
  }
  // 페이지 로드 시 한 번 상태 확인
  fetchAlertStatus();

  // 이후 10초마다 한 번씩 상태 다시 확인 (필요하면 간격 조절 가능)
  setInterval(fetchAlertStatus, 5000);
});
