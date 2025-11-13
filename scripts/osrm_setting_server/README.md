# 🧭 OSRM 경로엔진 사용법 (로컬 Docker ↔ Azure ACI)

이 프로젝트의 길찾기(보행자용)는 **OSRM**을 사용합니다.
두 가지 방식 중 하나를 선택해 사용하세요.

* **A. 로컬 Docker로 실행(개발·실험용)**
* **B. Azure Container Instances(ACI)로 실행(배포·공유용)**

`.env`의 `OSRM_URL` 값만 해당 모드의 주소로 바꾸면 프런트/백엔드가 그대로 동작합니다.

---

## A) 로컬 Docker로 OSRM 실행

### 0) 준비물

* Docker Desktop 실행 중
* 남한 전체 PBF 파일 준비: `data/south-korea-*.osm.pbf` (예: `data/south-korea-251111.osm.pbf`)

### 1) Dockerfile (프로젝트 내 `scripts/osrm_setting_server/` 폴더)

```dockerfile
# scripts/osrm_setting_server/Dockerfile
FROM osrm/osrm-backend:latest
WORKDIR /data

# 실제 파일명에 맞춰 복사 (예시: south-korea-251111.osm.pbf)
COPY data/south-korea-251111.osm.pbf /data/south-korea.osm.pbf

# 도보 프로필로 전처리 (MLD)
RUN osrm-extract -p /opt/foot.lua /data/south-korea.osm.pbf && \
    osrm-partition /data/south-korea.osrm && \
    osrm-customize /data/south-korea.osrm

EXPOSE 5000
CMD ["osrm-routed", "--algorithm", "mld", "/data/south-korea.osrm"]
```

> 파일명이 다르면 `COPY` 라인 오른쪽(좌측은 로컬, 우측은 컨테이너 경로)을 맞춰 수정하세요.

### 2) 빌드 & 실행

```bash
# (폴더) scripts/osrm_setting_server 에서 실행
docker build -t osrm-korea-foot .
docker run -p 5000:5000 osrm-korea-foot
```

### 3) 동작 확인

브라우저로 열기:

```
http://localhost:5000/route/v1/foot/126.978,37.5665;126.990,37.580
```

JSON 응답에 `"code":"Ok"`가 보이면 성공입니다.

### 4) 앱 연동(.env)

```env
OSRM_URL=http://localhost:5000
```

> **중지**: 컨테이너 실행 터미널에서 `Ctrl + C`
> **참고**: 전국 PBF는 메모리 사용량이 큽니다. Docker Desktop → Settings → Resources에서 메모리 6~8GB 권장.

---

## B) Azure Container Instances(ACI)로 OSRM 실행

> 예시는 실제 사용한 값으로 기입되어 있습니다. 필요 시 이름만 바꿔 쓰세요.

### 1) ACR(Registry)에 이미지 올리기

```powershell
# 로그인
az login

# (이미 생성했다면 생략) ACR 생성
# az acr create --resource-group 2dt-1st-team6 --name myosrmregistry --sku Basic

# 도커 로그인
az acr login --name myosrmregistry

# 로컬 이미지를 ACR 경로로 태깅 후 푸시
docker tag osrm-korea-foot myosrmregistry.azurecr.io/osrm-korea-foot:latest
docker push myosrmregistry.azurecr.io/osrm-korea-foot:latest
```

### 2) ACI로 실행 (Admin 계정 방식)

```powershell
# ACR Admin 계정 활성화
az acr update -n myosrmregistry --admin-enabled true

# ACR 자격증명 조회
$ACR_USER = az acr credential show -n myosrmregistry --query "username" -o tsv
$ACR_PASS = az acr credential show -n myosrmregistry --query "passwords[0].value" -o tsv

# 컨테이너 생성 (메모리/CPU는 전국 PBF 기준 권장치)
az container create `
  --resource-group 2dt-1st-team6 `
  --name osrm-korea `
  --image myosrmregistry.azurecr.io/osrm-korea-foot:latest `
  --registry-login-server myosrmregistry.azurecr.io `
  --registry-username $ACR_USER `
  --registry-password $ACR_PASS `
  --os-type Linux `
  --ports 5000 `
  --dns-name-label osrm-korea-demo-2dt022 `
  --memory 8 `
  --cpu 2 `
  --location koreacentral
```

> **대안(보안 강함)**: Admin 없이 **관리형 ID + AcrPull**로도 가능. 필요하면 역할 할당 스크립트 제공 가능.

### 3) 주소 확인 & 테스트

```powershell
az container show -g 2dt-1st-team6 -n osrm-korea `
  --query "{state:instanceView.state,fqdn:ipAddress.fqdn,ip:ipAddress.ip}" -o table
```

브라우저로 테스트:

```
http://<FQDN>:5000/route/v1/foot/126.978,37.5665;126.990,37.580
```

### 4) 앱 연동(.env)

```env
OSRM_URL=http://osrm-korea-demo-2dt022.koreacentral.azurecontainer.io:5000
```

### 5) 운영 명령(요금 절약)

```powershell
# 중지 / 시작
az container stop  -g 2dt-1st-team6 -n osrm-korea
az container start -g 2dt-1st-team6 -n osrm-korea

# 로그 보기
az container logs -g 2dt-1st-team6 -n osrm-korea --follow

# 삭제
az container delete -g 2dt-1st-team6 -n osrm-korea --yes
```

---

## 🔧 프런트/백엔드 연동 요약

* **백엔드(Flask)**: `OSRM_URL` 환경변수 사용하여 OSRM 호출

  ```python
  # 예시
  import os, requests
  OSRM_URL = os.getenv("OSRM_URL", "http://localhost:5000")
  r = requests.get(f"{OSRM_URL}/route/v1/foot/{lon1},{lat1};{lon2},{lat2}",
                   params={"overview":"full","geometries":"geojson"})
  data = r.json()
  ```
* **프런트(JS)**:

  ```javascript
  // 예시
  const OSRM_URL = "<.env에서 가져온 값>";
  const url = `${OSRM_URL}/route/v1/foot/${startLng},${startLat};${endLng},${endLat}?overview=full&geometries=geojson`;
  const res = await fetch(url);
  const json = await res.json();
  ```

---

## ❗️자주 겪는 이슈

* **로컬에서 5000 접속 OK인데 /favicon.ico 400**
  → 정상입니다(브라우저 자동 요청). `/route/v1/...`만 확인하세요.
* **ACI 생성 시 `osType null` 오류**
  → `--os-type Linux` 명시.
* **ACI가 ACR에서 pull 실패**
  → (빠른 해결) ACR Admin 활성화 후 `--registry-username/--registry-password` 사용
  → (대안) 관리형 ID 부여 후 `AcrPull` 역할을 ACR에 할당.
* **메모리 부족**
  → 로컬 Docker 메모리 6~8GB, ACI는 `--memory 8` 이상 추천.
