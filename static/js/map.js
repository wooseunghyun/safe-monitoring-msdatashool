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
  // B. 출발/도착 마커 (드래그로 위치 지정)
  // =====================================
  // 출발 마커
  const startMarker = new kakao.maps.Marker({
    position: new kakao.maps.LatLng(37.5665, 126.9780),
    draggable: true,
    map: map,
  });

  // 도착 마커
  const endMarker = new kakao.maps.Marker({
    position: new kakao.maps.LatLng(37.5650, 126.9780),
    draggable: true,
    map: map,
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

  // ---------------------------------------
  // 라우트 다시 그리기 (OSRM 우선)
  // ---------------------------------------
  async function refreshRoute() {
    if (!routeState.start || !routeState.end) return;

    if (USE_OSRM) {
      try {
        await drawOsrmRoute(
          routeState.start,
          routeState.end,
          routeState.waypoints
        );
        return;
      } catch (err) {
        console.warn("OSRM 실패, 직선 fallback:", err);
      }
    }

    const pts = [routeState.start, ...routeState.waypoints, routeState.end];
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
  const SEGMENT_MS = 30_000;   // 30초마다 완전한 webm 파일 1개씩 생성

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

  // 2초마다 peak dB 보내는 루프
  function startDbLoop() {
    if (dbInterval) clearInterval(dbInterval);
    dbInterval = setInterval(() => {
      if (!analyser || !dataBuf) return;

      analyser.getFloatTimeDomainData(dataBuf);
      let peak = 0;
      for (let i = 0; i < dataBuf.length; i++) {
        const v = Math.abs(dataBuf[i]);
        if (v > peak) peak = v;
      }
      const peakDb = 20 * Math.log10(peak || 1e-8);

      sendTelemetry({
        user_id: USER_ID,
        ts: new Date().toISOString(),
        peak_db: peakDb,
        baseline_db: Number(localStorage.getItem("baseline_db")) || -50,
        chunk_ms: 2000
      });
    }, 2000);
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



// // =====================================
// // 🎙 음성 녹음 & 업로드 (서버 경유 버전) + user_id 포함
// // =====================================
// const recordBtn = document.getElementById("btn-record");
// const recordStatus = document.getElementById("rec-status");

// let mediaRecorder = null;
// let audioStream = null;
// let isRecording = false;

// // 0) user_id 생성/보관 (브라우저 최초 1회)
// function getOrCreateUserId() {
//   const KEY = "safe_user_id";
//   let uid = window.localStorage.getItem(KEY);
//   if (!uid) {
//     uid = (crypto && crypto.randomUUID) ? crypto.randomUUID() 
//                                         : 'uid-' + Math.random().toString(36).slice(2);
//     window.localStorage.setItem(KEY, uid);
//   }
//   return uid;
// }
// const USER_ID = getOrCreateUserId(); // 전역 보관

// recordBtn.addEventListener("click", async () => {
//   if (!isRecording) {
//     await startRecording();
//   } else {
//     stopRecording();
//   }
// });

// let audioCtx, analyser, dataBuf;

// // ✅✅ 여기에 넣으세요: 텔레메트리 전송 함수 (startDbLoop보다 위)
// async function sendTelemetry(evt) {
//   try {
//     await fetch("/telemetry", {
//       method: "POST",
//       headers: {"Content-Type": "application/json"},
//       body: JSON.stringify(evt)
//     });
//   } catch (e) {
//     console.warn("telemetry send failed", e);
//   }
// }

// async function startRecording() {
//   try {
//     const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
//     audioStream = stream;
    
//     const preferredType = "audio/webm; codecs=opus";
//     if (MediaRecorder.isTypeSupported(preferredType)) {
//       mediaRecorder = new MediaRecorder(stream, { mimeType: preferredType });
//     } else {
//       mediaRecorder = new MediaRecorder(stream); // fallback
//     }
//     console.log("opus 지원 여부:", MediaRecorder.isTypeSupported("audio/webm; codecs=opus"));
//     console.log("실제 mediaRecorder.mimeType:", mediaRecorder.mimeType);
    
//     // ---- dB 측정 파이프 ----
//     audioCtx = new (window.AudioContext || window.webkitAudioContext)();
//     const src = audioCtx.createMediaStreamSource(stream);
//     analyser = audioCtx.createAnalyser();
//     analyser.fftSize = 2048;
//     src.connect(analyser);
//     dataBuf = new Float32Array(analyser.fftSize);

//     // 1~2초 마다 peak dB 계산해서 서버로 전송
//     startDbLoop();

//     // 1분마다 blob → 서버 전송
//     // mediaRecorder.addEventListener("dataavailable", async (event) => {
//     //   if (event.data && event.data.size > 0) {
//     //     await uploadToServer(event.data);
//     //   }
//     // });
//     let chunkCounter = 0;
//     mediaRecorder.addEventListener("dataavailable", async (event) => {
//       chunkCounter += 1;

//       console.log(
//         `[DEBUG] chunk #${chunkCounter}`,
//         "type =", event.data.type,
//         "size =", event.data.size
//       );

//       // 🔍 1) 디버그용: 앞으로 생성되는 각 chunk를 브라우저에서 바로 다운로드해보기
//       //    (너무 많으면 첫 3개만 저장하게 조건 걸어도 됨)
//       if (event.data && event.data.size > 0) {
//         const url = URL.createObjectURL(event.data);
//         const a = document.createElement("a");
//         a.href = url;
//         a.download = `from-browser-chunk${chunkCounter}-${new Date().toISOString().replace(/[:.]/g, "-")}.webm`;
//         document.body.appendChild(a);
//         a.click();
//         a.remove();
//         console.log(`[DEBUG] 브라우저에서 chunk #${chunkCounter} 다운로드 트리거`);
//       }

//       // 🔄 2) 서버로 업로드 (기존 로직 유지)
//       if (event.data && event.data.size > 0) {
//         await uploadToServer(event.data);
//       }
//     });

//     mediaRecorder.start(10_000); // 5초마다 청크

//     isRecording = true;
//     recordBtn.textContent = "⏹ 녹음 중지";
//     recordStatus.textContent = "녹음 중... 1분마다 서버로 전송합니다.";
//   } catch (err) {
//     console.error("녹음 시작 실패:", err);
//     recordStatus.textContent = "녹음 시작 실패(콘솔 확인)";
//   }
// }

// async function calibrateSilence() {
//   const samples = [];
//   const start = performance.now();
//   while (performance.now() - start < 3000) { // 3초
//     analyser.getFloatTimeDomainData(dataBuf);
//     let peak = 0;
//     for (let i = 0; i < dataBuf.length; i++) {
//       const v = Math.abs(dataBuf[i]);
//       if (v > peak) peak = v;
//     }
//     samples.push(20 * Math.log10(peak || 1e-8));
//     await new Promise(r => setTimeout(r, 200)); // 0.2초 간격
//   }
//   const avg = samples.reduce((a,b)=>a+b,0)/samples.length;
//   localStorage.setItem("baseline_db", avg.toFixed(1));
//   alert(`기준 소음 레벨: ${avg.toFixed(1)} dBFS`);
// }


// let dbInterval = null;
// function startDbLoop() {
//   if (dbInterval) clearInterval(dbInterval);
//   dbInterval = setInterval(() => {
//     //마이크 입력을 -1.0 ~ +1.0 사이의 디지털 진폭값으로 제공
//     analyser.getFloatTimeDomainData(dataBuf);
//     //각 사용자의 마이크 장치에서 상대적인 세기
//     // peak amplitude 계산
//     let peak = 0;
//     for (let i = 0; i < dataBuf.length; i++) {
//       const v = Math.abs(dataBuf[i]);
//       if (v > peak) peak = v;
//     }
//     // 20*log10(peak). 0에 가까우면 -∞ → 아주 작은 바닥값 처리
//     const peakDb = 20 * Math.log10(peak || 1e-8);

//     sendTelemetry({
//       user_id: USER_ID,               // 앞서 만든 localStorage 기반
//       ts: new Date().toISOString(),
//       peak_db: peakDb,                // 예: -10 ~ -60dB 근처(마이크 게인/환경에 따라 다름)
//       baseline_db: Number(localStorage.getItem("baseline_db")) || -50,
//       chunk_ms: 2000                  // 샘플링 간격(여기선 2초)
//     });
//   }, 2000);
// }

// // ASA 예시

// // SELECT
// //   user_id,
// //   MAX(peak_db - baseline_db) AS delta_db,
// //   System.Timestamp AS wnd_end
// // INTO alerts
// // FROM telemetry TIMESTAMP BY ts
// // GROUP BY user_id, TumblingWindow(second, 60)
// // HAVING MAX(peak_db - baseline_db) > 30;  -- 기준보다 30dB 이상 상승 시 경보


// function stopRecording() {
//   if (dbInterval) clearInterval(dbInterval);
//   if (mediaRecorder && mediaRecorder.state !== "inactive") {
//     mediaRecorder.stop();
//   }
//   if (audioStream) {
//     audioStream.getTracks().forEach(t => t.stop());
//   }
//   isRecording = false;
//   recordBtn.textContent = "🎙 녹음 시작";
//   recordStatus.textContent = "녹음 중지됨.";
// }

// async function uploadToServer(blob) {
//   const iso = new Date().toISOString().replace(/[:.]/g, "-");
//   const fileName = `audio-${iso}.webm`;

//   const formData = new FormData();
//   formData.append("file", blob, fileName);
//   formData.append("user_id", USER_ID);         // ✅ 필수
//   formData.append("ts", new Date().toISOString()); // 업로드 시각
//   // formData.append("room_id", "team6");       // 필요하면 추가 메타

//   try {
//     const res = await fetch("/upload-audio", {
//       method: "POST",
//       body: formData
//     });

//     if (!res.ok) {
//       console.error("서버 업로드 실패", await res.text());
//       recordStatus.textContent = "서버 업로드 실패";
//     } else {
//       recordStatus.textContent = `서버 업로드 성공: ${fileName}`;
//     }
//   } catch (err) {
//     console.error("서버 전송 오류:", err);
//     recordStatus.textContent = "서버 전송 오류";
//   }
// }


});
