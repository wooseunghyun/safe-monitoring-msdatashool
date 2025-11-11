// static/js/map.js
kakao.maps.load(function () {
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

  fetch("/static/data/cctv.json")
    .then(res => res.json())
    .then(data => {
      cctvData = data;

      cctvMarkers = data
        .filter(d => d.lat && d.lng)
        .map(d => {
          return new kakao.maps.Marker({
            position: new kakao.maps.LatLng(d.lat, d.lng),
            title: d.name || ""
          });
        });

      cctvClusterer.addMarkers(cctvMarkers);
      console.log("CCTV loaded:", cctvMarkers.length);
    });

  // 토글
  document.getElementById("toggle-cctv").addEventListener("change", function (e) {
    if (e.target.checked) {
      cctvClusterer.addMarkers(cctvMarkers);
    } else {
      cctvClusterer.clear();
    }
  });

  // =====================================
  // B. 경로 상태
  // =====================================
  const geocoder = new kakao.maps.services.Geocoder();

  let routeState = {
    start: null,      // {lat, lng, name}
    end: null,
    waypoints: []     // [{lat,lng,name}]
  };

  let routeSegments = [];  // 지도에 그려진 polyline들

  // 주소 -> 좌표
  function addressToLatLng(address) {
    return new Promise((resolve, reject) => {
      geocoder.addressSearch(address, function (result, status) {
        if (status === kakao.maps.services.Status.OK) {
          resolve({
            lat: parseFloat(result[0].y),
            lng: parseFloat(result[0].x),
            name: address
          });
        } else {
          reject("주소를 찾을 수 없습니다: " + address);
        }
      });
    });
  }

  // 거리 계산 (m)
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

  // 점-선분 거리
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

    // px,py => cctv (lng,lat), yy,xx => segment point (lat,lng)
    return distanceMeters(py, px, yy, xx);
  }

  // 이 선분 주변 CCTV 개수 세기
  function calcCctvScoreNearSegment(p1, p2, radiusMeters) {
    if (!cctvData || cctvData.length === 0) return 0;
    let count = 0;
    for (const c of cctvData) {
      const d = pointToSegmentDistanceMeters(
        c.lng, c.lat,
        p1.lng, p1.lat,
        p2.lng, p2.lat
      );
      if (d <= radiusMeters) {
        count++;
      }
    }
    return count;
  }

  function pickColorByScore(score) {
    if (score >= 10) return "#27ae60";  // 안전
    if (score >= 5) return "#f1c40f";   // 보통
    return "#e74c3c";                   // 취약
  }

  // 실제로 색깔 경로 그리기
  function drawRouteColored(points) {
    // 이전 거 지우기
    routeSegments.forEach(seg => seg.setMap(null));
    routeSegments = [];

    if (!points || points.length < 2) return;

    const bounds = new kakao.maps.LatLngBounds();

    for (let i = 0; i < points.length - 1; i++) {
      const p1 = points[i];
      const p2 = points[i + 1];

      const score = calcCctvScoreNearSegment(p1, p2, 80); // 80m 안 CCTV
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

  // 출발/경유/도착을 상태에서 점 배열로 변환
  function refreshRoute() {
    if (!routeState.start || !routeState.end) return;
    const pts = [];
    pts.push(routeState.start);
    (routeState.waypoints || []).forEach(wp => pts.push(wp));
    pts.push(routeState.end);
    drawRouteColored(pts);
  }

  // 버튼: 주소 → 좌표 → 상태 저장 → 그리기
  document.getElementById("btn-route").addEventListener("click", async function () {
    const s = document.getElementById("start-input").value.trim();
    const e = document.getElementById("end-input").value.trim();
    if (!s || !e) {
      alert("출발지와 도착지를 입력하세요.");
      return;
    }
    try {
      const sCoord = await addressToLatLng(s);
      const eCoord = await addressToLatLng(e);
      routeState.start = sCoord;
      routeState.end = eCoord;
      refreshRoute();
    } catch (err) {
      alert(err);
    }
  });

  // 지도 우클릭 시 경유지 추가 (테스트용)
  kakao.maps.event.addListener(map, "rightclick", function (mouseEvent) {
    const latlng = mouseEvent.latLng;
    routeState.waypoints.push({
      lat: latlng.getLat(),
      lng: latlng.getLng(),
      name: "waypoint"
    });
    refreshRoute();
  });
function clearRoute() {
  // 상태 초기화
  routeState.start = null;
  routeState.end = null;
  routeState.waypoints = [];

  // 지도 위 선들 제거
  routeSegments.forEach(seg => seg.setMap(null));
  routeSegments = [];
}

document.getElementById("btn-reset").addEventListener("click", function () {
  clearRoute();
});

function sortWaypointsByDistanceFromStart() {
  if (!routeState.start) return;
  if (!routeState.waypoints || routeState.waypoints.length === 0) return;

  const s = routeState.start;
  routeState.waypoints.sort((a, b) => {
    const da = distanceMeters(s.lat, s.lng, a.lat, a.lng);
    const db = distanceMeters(s.lat, s.lng, b.lat, b.lng);
    return da - db;
  });

  // 정렬됐으니까 다시 그리기
  refreshRoute();   // 아래에 있음
}

document.getElementById("btn-sort").addEventListener("click", function () {
  sortWaypointsByDistanceFromStart();
});


  
});
