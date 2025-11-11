// static/js/map.js
kakao.maps.load(function () {
  // 0) 필요하면 여기서 on/off 할 수 있음
  const USE_OSRM = true;  // false로 두면 지금처럼 직선만 그림

    // 👇 여기 추가: 어떤 프로필로 OSRM에 요청할지
  // 서버가 foot을 지원하면 "foot", 자전거면 "bicycle"
  // 지금 공개 OSRM이면 "driving" 그대로 두기
  const OSRM_PROFILE = "foot";   // <-- 여기만 바꾸면 됨

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
        .map(d => new kakao.maps.Marker({
          position: new kakao.maps.LatLng(d.lat, d.lng),
          title: d.name || ""
        }));

      cctvClusterer.addMarkers(cctvMarkers);
      console.log("CCTV loaded:", cctvMarkers.length);
    });

  document.getElementById("toggle-cctv").addEventListener("change", function (e) {
    if (e.target.checked) cctvClusterer.addMarkers(cctvMarkers);
    else cctvClusterer.clear();
  });

  // =====================================
  // B. 경로 상태
  // =====================================
  const geocoder = new kakao.maps.services.Geocoder();

  const routeState = {
    start: null,
    end: null,
    waypoints: []
  };
  let routeSegments = [];

  // ---------------------------------------
  // 유틸
  // ---------------------------------------
  function addressToLatLng(address) {
    return new Promise((resolve, reject) => {
      geocoder.addressSearch(address, (result, status) => {
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

  function pickColorByScore(score) {
    if (score >= 10) return "#27ae60";
    if (score >= 5) return "#f1c40f";
    return "#e74c3c";
  }

  // 기존 “직선으로 그리는” 버전
  function drawRouteColored(points) {
    routeSegments.forEach(seg => seg.setMap(null));
    routeSegments = [];

    if (!points || points.length < 2) return;

    const bounds = new kakao.maps.LatLngBounds();

    for (let i = 0; i < points.length - 1; i++) {
      const p1 = points[i];
      const p2 = points[i + 1];

      const score = calcCctvScoreNearSegment(p1, p2, 80);
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

  // -----------------------------
  // OSRM 경로 그리기용 함수 추가
  // -----------------------------
  async function drawOsrmRoute(start, end, waypoints) {
    // /api/route?start=lat,lng&end=lat,lng&via=lat,lng;lat,lng ...
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

      const score = calcCctvScoreNearSegment(p1, p2, 80);
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

  // 👉 여기만 바뀜: OSRM 먼저, 안 되면 기존 직선
  async function refreshRoute() {
    if (!routeState.start || !routeState.end) return;

    if (USE_OSRM) {
      try {
        await drawOsrmRoute(
          routeState.start,
          routeState.end,
          routeState.waypoints
        );
        return;  // 성공했으면 여기서 끝
      } catch (err) {
        console.warn("OSRM 실패, 직선 fallback:", err);
      }
    }

    // 실패하거나 USE_OSRM=false 면 기존 방식
    const pts = [routeState.start, ...routeState.waypoints, routeState.end];
    drawRouteColored(pts);
  }

  // ---------------------------------------
  // 1) 경로 초기화
  // ---------------------------------------
  function clearRoute() {
    routeState.start = null;
    routeState.end = null;
    routeState.waypoints = [];
    routeSegments.forEach(seg => seg.setMap(null));
    routeSegments = [];
  }

  document.getElementById("btn-reset").addEventListener("click", () => {
    clearRoute();
  });

  // ---------------------------------------
  // 2) 삽입 + 2-opt 정렬
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
  // 버튼: 주소 -> 좌표 -> 상태 저장
  // ---------------------------------------
  document.getElementById("btn-route").addEventListener("click", async () => {
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
      await refreshRoute();
    } catch (err) {
      alert(err);
    }
  });

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
// =======================
// 🎙 음성 녹음 & 업로드 (서버 경유 버전)
// =======================
const recordBtn = document.getElementById("btn-record");
const recordStatus = document.getElementById("rec-status");

let mediaRecorder = null;
let audioStream = null;
let isRecording = false;

recordBtn.addEventListener("click", async () => {
  if (!isRecording) {
    await startRecording();
  } else {
    stopRecording();
  }
});

async function startRecording() {
  try {
    // 1) 마이크 권한
    audioStream = await navigator.mediaDevices.getUserMedia({ audio: true });

    // 2) MediaRecorder
    mediaRecorder = new MediaRecorder(audioStream);

    // 3) 1분마다 블롭 나오면 서버로 전송
    mediaRecorder.addEventListener("dataavailable", async (event) => {
      if (event.data && event.data.size > 0) {
        await uploadToServer(event.data);
      }
    });

    // 60,000ms = 1분마다 dataavailable
    mediaRecorder.start(60_000);

    isRecording = true;
    recordBtn.textContent = "⏹ 녹음 중지";
    recordStatus.textContent = "녹음 중... 1분마다 서버로 전송합니다.";
  } catch (err) {
    console.error("녹음 시작 실패:", err);
    recordStatus.textContent = "녹음 시작 실패(콘솔 확인)";
  }
}

function stopRecording() {
  if (mediaRecorder && mediaRecorder.state !== "inactive") {
    mediaRecorder.stop();
  }
  if (audioStream) {
    audioStream.getTracks().forEach(t => t.stop());
  }
  isRecording = false;
  recordBtn.textContent = "🎙 녹음 시작";
  recordStatus.textContent = "녹음 중지됨.";
}

// ✅ 이 부분이 Azure 직접 업로드 → 서버로 업로드로 바뀐 곳
async function uploadToServer(blob) {
  const iso = new Date().toISOString().replace(/[:.]/g, "-");
  const fileName = `audio-${iso}.webm`;

  const formData = new FormData();
  formData.append("file", blob, fileName);

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
}

});
