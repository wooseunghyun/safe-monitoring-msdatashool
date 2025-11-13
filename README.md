# 🛡️ Safe Monitoring Project

**도시 치안 데이터 기반 모니터링 및 시각화 시스템**

본 프로젝트는 공공데이터 포털에서 제공하는 범죄·치안 관련 데이터를 자동으로 수집하고,  
CCTV 등 주요 치안 인프라를 카카오맵 기반으로 시각화하는 시스템입니다.  
Selenium을 이용한 자동 다운로드 + Flask 웹서버 + Kakao Map API로 구성되어 있습니다.

---

## 🚀 실행 방법

### 1️⃣  가상환경 활성화
```bash
# (예시)
cd safe-monitoring-msdatashool
.venv\Scripts\activate
````

### 2️⃣  필수 패키지 설치

```bash
pip install -r requirements.txt
```

### 3️⃣  5대 강력범죄 데이터 자동 다운로드

자동 로그인 후 데이터를 다운로드합니다.

```bash
python -m scripts.automate_data_download.automate_download_5primarycrime
```

### 4️⃣  Flask 서버 실행 (CCTV 지도 확인)

CCTV 데이터를 카카오맵에 시각화합니다.

```bash
python -m scripts.server.main
```

서버 실행 후, 웹 브라우저에서
👉 [http://127.0.0.1:5000](http://127.0.0.1:5000) 접속하세요.

---

## 🔑 환경 변수 설정 (`.env`)

`.env` 파일에 다음과 같은 정보를 입력해야 합니다.

```env
PLATFORM_USER=your_username
PLATFORM_PASS=your_password
KAKAO_MAP_API_KEY=your_kakao_api_key
PLATFORM_USER=your_bigdata-policing_id
PLATFORM_PASS=your_bigdata-policing_password
BlobserviceSASURL=
SAS_TOKEN=
ENDPOINT=
AZURE_STORAGE_ACCOUNT_NAME=
AZURE_STORAGE_ACCOUNT_KEY=
AZURE_STORAGE_ACCOUNT_URL=
```

> ⚠️ `.env` 파일은 `.gitignore`에 포함되어 있으므로 GitHub에 업로드되지 않습니다.

---

## 📁 폴더 구조

```
safe-monitoring-msdatashool/
├── dataset/                      # 원본 및 변환된 데이터 파일 (.csv, .xlsx 등)
├── downloads/                    # 자동 다운로드된 파일 저장 위치
├── scripts/
│   ├── automate_data_download/    # Selenium 자동 다운로드 스크립트
│   │   └── automate_download_5primarycrime.py
│   ├── map/                       # (추후 확장용) 지도 관련 로직
│   └── server/
│       └── main.py                # Flask 서버 진입점
├── src/
│   └── download_utils.py          # 공통 다운로드 유틸 함수
├── static/
│   ├── data/                      # cctv.json 등 정적 데이터 파일
│   ├── img/                       # 마커 아이콘 등 이미지
│   └── js/                        # map.js (지도 스크립트)
├── templates/
│   └── index.html                 # Flask 템플릿 (지도 + 체크박스 UI)
├── .env                           # API 키, 로그인 정보
├── .gitignore
├── requirements.txt
└── README.md
```

---

## 🧩 주요 기능

* 🔄 **데이터 자동 다운로드**

  * Selenium 기반 로그인 & 파일 다운로드 자동화
* 🗺️ **지도 시각화**

  * Kakao Map API 기반 CCTV 위치 표시
  * 마커 클러스터링 / CCTV, 경찰시설 등 토글 제어 가능
* ⚙️ **구조적 코드 관리**

  * `scripts`, `src`, `static`, `templates` 등 기능별 모듈 분리
* 🔐 **환경변수 보안 관리**

  * `.env`를 통해 계정정보/API키 안전하게 로드

---

### 🌐 경로탐색(OSRM)
지도 길찾기는 OSRM(Open Source Routing Machine)을 사용합니다.  
로컬 도커 또는 Azure Container Instance 환경에서 실행할 수 있습니다.  
자세한 설정 방법은 [scripts/osrm_setting_server/README.md](scripts/osrm_setting_server/README.md) 참고.


---

## 🧠 참고

* Python 3.9 이상 권장
* 실행 전 ChromeDriver 버전이 로컬 크롬 버전과 일치해야 합니다.
* 데이터 출처: [경찰청 빅데이터 플랫폼](https://www.bigdata-policing.kr)

---

## 💡 향후 확장 계획

* 📊 범죄 유형별 사고 밀도 Heatmap 추가
* 🚨 CCTV 외 경찰서·비상벨·가로등 등 인프라 통합 시각화
* 📈 Flask → FastAPI + React 기반 대시보드로 확장
* ☁️ Azure 또는 AWS 배포 지원

---

> 🧭 **Author:** MS Data School Safe Monitoring Team
> 📅 **Last Updated:** 2025-11-11
> 🧩 **License:** MIT

```

