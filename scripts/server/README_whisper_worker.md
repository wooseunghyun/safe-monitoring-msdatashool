# 🎧 Whisper Worker (STT 자동 처리기)

**Azure Container Instances에서 구동되는 Whisper 기반 STT 처리 Worker**

Whisper Worker는 다음 역할을 수행합니다:

1. **live_uploads** 테이블에서

   * `stt_text IS NULL`
   * `audio_url IS NOT NULL`
     인 레코드를 5초마다 조회
2. Blob Storage에서 음성 파일 다운로드
3. Whisper 모델(Small)로 **한국어 STT 수행**
4. 위험도 분석(risk_level) 수행
5. 결과를 다시 PostgreSQL로 업데이트
6. (옵션) Event Hub 로 전송

---

# 📁 동작 구조

```
Frontend → /upload-audio → live_uploads(audio_url 저장됨)
Backend 서버: 업로드 처리 / live_peak 저장
Whisper Worker: live_uploads 읽고 → STT → DB 업데이트
```

Whisper Worker는 백엔드 서버와는 독립적으로 실행됨.
**파일 업로드만 되면 Worker가 자동으로 처리**합니다.

---

# 🛠 Whisper Worker 환경 변수

ACI 컨테이너 실행 시 다음 환경 변수가 반드시 필요합니다:

| Name                       | 설명                          |
| -------------------------- | --------------------------- |
| PG_HOST                    | PostgreSQL 서버 호스트           |
| PG_DB                      | 데이터베이스 이름                   |
| PG_USER                    | DB 사용자                      |
| PG_PASSWORD                | DB 패스워드                     |
| AZURE_STORAGE_ACCOUNT_NAME | Blob Storage 계정 이름          |
| AZURE_STORAGE_ACCOUNT_KEY  | Blob Storage 키              |
| VOICE_CONTAINER            | 음성 파일 저장되는 컨테이너 이름          |
| EH_TRANSCRIPTS_CONN_STRING | (선택) STT 결과 EventHub 연결 문자열 |
| EH_TRANSCRIPTS_HUB_NAME    | (선택) Hub 이름                 |

---

# 🚀 1. Docker 이미지 빌드

프로젝트 루트에서 실행:

```powershell
docker build -t whisper-worker -f scripts/server/Dockerfile.whisper .
```

이미지 확인:

```powershell
docker images
```

---

# 📦 2. Azure Container Registry(ACR)에 푸시

ACR 이름: **safeacrteam6**
로그인:

```powershell
az acr login -n safeacrteam6
```

Docker 이미지 태깅:

```powershell
docker tag whisper-worker:latest safeacrteam6.azurecr.io/whisper-worker:latest
```

ACR로 push:

```powershell
docker push safeacrteam6.azurecr.io/whisper-worker:latest
```

---

# ☁ 3. Azure Container Instance(ACI)에서 실행

PowerShell 버전:

```powershell
$ACR_USER = az acr credential show -n safeacrteam6 --query "username" -o tsv
$ACR_PASS = az acr credential show -n safeacrteam6 --query "passwords[0].value" -o tsv

az container create `
  -g "2dt-1st-team6" `
  -n "whisper-worker" `
  --image "safeacrteam6.azurecr.io/whisper-worker:latest" `
  --registry-login-server "safeacrteam6.azurecr.io" `
  --registry-username $ACR_USER `
  --registry-password $ACR_PASS `
  --restart-policy Always `
  --os-type Linux `
  --cpu 2 --memory 4 `
  --environment-variables `
      PG_HOST="<pg-host>" `
      PG_DB="safe_monitoring" `
      PG_USER="<pg-user>" `
      PG_PASSWORD="<pg-password>" `
      AZURE_STORAGE_ACCOUNT_NAME="<stg-name>" `
      AZURE_STORAGE_ACCOUNT_KEY="<stg-key>" `
      VOICE_CONTAINER="voice-uploads" `
      EH_TRANSCRIPTS_CONN_STRING="" `
      EH_TRANSCRIPTS_HUB_NAME=""
```

---

# 🔍 4. Whisper Worker 로그 확인

```powershell
az container logs -g "2dt-1st-team6" -n "whisper-worker"
```

로그 예시:

```
[EH] transcripts EventHub 활성화됨
[Whisper] loading model 'small' ...
100%|██████████████████| 461M/461M [00:04]
[Worker] processing id=42 ...
[STT] text: 살려주세요 제발 도와주세요...
[DONE] id=42, risk=HIGH
```

---

# ⏹ 5. Whisper Worker 중지 / 시작

ACI는 삭제하지 않아도 **중지(stop)만 하면 과금 거의 없음**.

### 중지:

```powershell
az container stop -g 2dt-1st-team6 -n whisper-worker
```

### 다시 시작:

```powershell
az container start -g 2dt-1st-team6 -n whisper-worker
```

---

# 🗑 6. Whisper Worker 완전 삭제

```powershell
az container delete -g 2dt-1st-team6 -n whisper-worker --yes
```

삭제하면 환경변수/설정 모두 날아감.

---

# 🙋‍♂️ 7. 문제 해결 FAQ

### Q. 로그가 동작하는데 STT 결과가 DB에 안 들어간다?

* DB 접속 정보(PG_HOST / USER / PASSWORD) 확인
* audio_url이 NULL이면 worker가 무시함
* Whisper 모델이 파일을 읽을 수 없는 경우 tmp 파일이 깨졌을 수 있음

### Q. 모델 로딩이 너무 느리다

* 현재 Whisper Small 사용 중
* tiny / base 모델로 바꾸면 빠르게 가능

---

# 📘 결론

이 README를 따라하면
**음성 파일 업로드 → Azure Storage 저장 → Whisper Worker 자동 처리 → DB 업데이트**
까지 전체 파이프라인이 완성됩니다.
