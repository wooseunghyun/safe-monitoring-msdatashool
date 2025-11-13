# Whisper Worker Pipeline Guide

**음성 업로드 → Blob 저장 → uploads DB 기록 → Whisper STT → Event Hub 전송**

본 문서는 Safe Monitoring 프로젝트에서 **음성 파일을 처리하는 전체 파이프라인 구조**와
**whisper_worker.py 및 관련 스크립트의 사용 방법**을 정리한 가이드입니다.

이 문서는 개발자용 기술 문서이며, 메인 README에서 링크되어야 합니다.

---

## 📌 1. 전체 구조(Flow Overview)

```
[1] Frontend (Web)
     └─ Mic Audio → /upload-audio (POST)

[2] Backend (Flask server)
     ├─ Blob Storage: 오디오 파일 저장
     ├─ uploads.sqlite: 업로드 메타데이터 기록
     └─ /telemetry: 데시벨 데이터 Event Hub 전송

[3] Whisper Worker (독립 프로세스/컨테이너)
     ├─ uploads DB에서 처리 안 된(stt_done=0) 오디오 조회
     ├─ Blob에서 파일 다운로드
     ├─ Whisper STT 실행
     ├─ 결과 텍스트 → Event Hub(transcripts-events) 전송
     └─ uploads DB에 transcript 기록 + stt_done=1 업데이트
```

---

## 📌 2. 필요 환경 변수(.env)

아래 값들은 로컬/도커 환경 모두에서 필요합니다.

### Blob Storage

```
AZURE_STORAGE_ACCOUNT_NAME=xxx
AZURE_STORAGE_ACCOUNT_KEY=yyy
VOICE_CONTAINER=voice-uploads
```

### Event Hub (transcripts-purpose)

```
EH_TRANSCRIPTS_CONN_STRING=Endpoint=sb://...SharedAccessKey=...
EH_TRANSCRIPTS_HUB_NAME=transcripts-events
```

### 기타 옵션

```
# (필요 시)
ALLOW_ANON_UPLOAD=true
```

---

## 📌 3. uploads DB 구조

업로드 기록은 `scripts/server/uploads.db` 에 저장됩니다.

| Column     | Type       | 설명              |
| ---------- | ---------- | --------------- |
| id         | INTEGER PK | 업로드 ID          |
| user_id    | TEXT       | 사용자 식별자         |
| blob_name  | TEXT       | Blob에 저장된 파일 이름 |
| ts         | TEXT(ISO)  | 업로드 시각          |
| size_bytes | INTEGER    | 파일 크기           |
| mime       | TEXT       | MIME 타입         |
| ip         | TEXT       | 요청자 IP          |
| stt_done   | INTEGER    | 0=미완료, 1=완료     |
| transcript | TEXT       | Whisper 결과      |

`whisper_worker.py` 실행 시 자동으로 스키마를 보정하여
누락된 `stt_done`, `transcript` 컬럼을 추가합니다.

---

## 📌 4. Whisper Worker 실행 방법

### 4-1) 로컬에서 실행

```bash
cd safe-monitoring-msdatashool
source .venv/Scripts/activate  # 또는 . venv/bin/activate
python -m scripts.server.whisper_worker
```

Worker는 무한 루프를 돌며:

1. uploads DB에서 stt_done=0 인 row 조회
2. Blob에서 파일 다운로드
3. Whisper 로 transcribe
4. transcripts Event Hub로 전송
5. stt_done=1 업데이트

---

## 📌 5. Worker Docker 이미지 빌드

### 5-1) Dockerfile 위치

Dockerfile 위치는:

```
safe-monitoring-msdatashool/scripts/server/Dockerfile
```

### 5-2) 빌드

```bash
docker build -t safe-whisper-worker scripts/server
```

### 5-3) 실행

```bash
docker run --env-file .env safe-whisper-worker
```

※ `.env` 파일은 프로젝트 루트에 있어야 하며,
컨테이너 내부에서도 Whisper Worker는 그 값을 그대로 읽습니다.

---

## 📌 6. uploads DB 정리(clean-up)

Blob에서 파일을 수동 삭제했다면
DB에는 orphan row(고아 row)가 남아 있게 됩니다.

Whisper Worker는 **DB 기준**으로 계속 처리하려 하기 때문에
Blob이 없을 경우 오류가 반복됩니다.

이 때 다음 툴을 사용합니다:

### 6-1) orphan cleanup 스크립트

```
scripts/server/cleanup_uploads.py
```

### 실행:

```bash
python -m scripts.server.cleanup_uploads
```

### 역할:

* uploads 중 stt_done=0 인 항목 조회
* Blob에서 해당 blob_name 실제 존재 여부 확인
* **존재하지 않으면**

  * `stt_done=1`
  * `transcript='[MISSING_BLOB]'` 으로 마크

이렇게 하면 Worker가 다시 반복적으로 실패하지 않습니다.

---

## 📌 7. 업로드 현황 조회 API (`/uploads`)

서버에서 제공하는 엔드포인트:

```
GET /uploads
GET /uploads?user_id=xxxxx
```

### 예:

```bash
curl http://127.0.0.1:5000/uploads | jq
```

### 반환 예:

```json
[
  {
    "user_id": "feb14949...",
    "blob": "user-feb/audio-2025-11-12T10-16-41.webm",
    "ts": "2025-11-12T10:16:41Z",
    "size": 29382,
    "mime": "audio/webm",
    "ip": "127.0.0.1"
  }
]
```

---

## 📌 8. 시스템 이상 발생 시 체크리스트

### 1) Blob에서 파일이 열리지 않음

→ 웹녹음 설정 문제 / 크롬 codec 문제 / Blob 파일 크기 0 여부 확인
→ 또는 tmp 파일 확장자가 `.webm`인지 체크

### 2) Worker에서 EventHub 권한 오류

→ transcripts Event Hub 정책에 **Send 권한** 부여 필요

### 3) Connection String 불러오지 못함

→ Docker 환경에서 `.env` 경로 확인
→ `--env-file` 옵션 누락 여부 확인

### 4) uploads DB에 남아 있는데 Blob에는 없음

→ cleanup_uploads.py 실행하여 orphan 처리

---

## 📌 9. 메인 README에 어떻게 링크해야 하나?

**메인 README에는 요 정도만 넣으면 됩니다:**

---

### 🎤 Whisper Worker (음성 → STT → EventHub)

이 프로젝트는 음성 업로드 후 Whisper 모델로 STT를 수행하는 Worker 프로세스를 포함합니다.

Whisper Worker 구조 및 실행 방법은 아래 문서를 참고하세요:
👉 **[docs/whisper-worker.md](docs/whisper-worker.md)**

---

## 🔚 마지막 정리

이 문서는 개발자가 시스템을 이해하고 유지보수할 수 있도록:

* 음성 업로드 처리 흐름 전체 설명
* Worker, Docker, DB 스키마, Event Hub 통합 구조
* 오류 발생 시 대응법
* orphan cleanup 방식

모두 포함한 완전한 가이드입니다.