지금 `python -m scripts.server.main` 으로 돌리는 거 그대로 **컨테이너로 감싸서 ACR → ACI** 에 띄우면 됩니다.
순서대로 한 번에 정리해볼게요.

---

## 0. main.py 조금만 수정하기 (컨테이너에서 외부접속 가능하게)

지금은:

```python
if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
```

일 거라서, **host/port 를 열어줘야** ACI에서 접속이 됩니다.

```python
# scripts/server/main.py
import os
# ... 위쪽은 그대로 ...

if __name__ == "__main__":
    app = create_app()
    # 컨테이너에서 외부로 열리도록 0.0.0.0 + 포트 환경변수
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", "5000")),
        debug=False
    )
```

---

## 1. Dockerfile 만들기

프로젝트 루트(`safe-monitoring-msdatashool`)에 `Dockerfile` 하나 만들어요.

> ⚠ requirements 파일 이름은 제가 100% 알 수 없어서 **확실하지 않음**
> 아래 예시는 `requirements.txt` 기준입니다. 없으면
> `pip freeze > requirements.txt` 해서 하나 만들고 쓰면 됩니다.

```dockerfile
# Dockerfile (프로젝트 루트)
FROM python:3.11-slim

# 필수 패키지 약간 (psycopg2, whisper 빌드용)
RUN apt-get update && apt-get install -y \
    build-essential ffmpeg curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 1) 파이썬 라이브러리 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 2) 소스 코드 전체 복사
COPY . .

# 3) 환경변수 기본값 (필요하면 수정)
ENV PYTHONUNBUFFERED=1
ENV PORT=5000

# 4) Flask 서버가 리스닝할 포트
EXPOSE 5000

# 5) 서버 실행
CMD ["python", "-m", "scripts.server.main"]
```

나중에 gunicorn 쓰고 싶으면 CMD만 바꾸면 되는데, 지금은 **로컬에서 돌리던 그대로** 가는 게 편해요.

---

## 2. 로컬에서 컨테이너 빌드 & 테스트

### 2-1) 이미지 빌드

```powershell
# 프로젝트 루트에서
docker build -t safe-api .
```

### 2-2) 로컬에서 한 번 돌려보기

> `.env`에 있는 설정을 그대로 써야 하니까 `--env-file` 를 쓰는 게 제일 편합니다.

```powershell
docker run --env-file .env -p 5000:5000 safe-api
```

* 브라우저에서 `http://localhost:5000` 접속해서
  기존이랑 똑같이 뜨면 OK.

---

## 3. ACR에 푸시

이미 `safeacrteam6` 만들어 놨으니까, whisper-worker랑 거의 똑같이 하면 됩니다.

### 3-1) ACR 로그인

```powershell
az acr login -n safeacrteam6
```

### 3-2) 태그 붙이고 푸시

```powershell
docker tag safe-api safeacrteam6.azurecr.io/safe-api:latest
docker push safeacrteam6.azurecr.io/safe-api:latest
```

잘 올라갔는지 확인:

```powershell
az acr repository show-tags -n safeacrteam6 --repository safe-api -o table
```

`latest` 보이면 성공.

---

## 4. ACI(컨테이너 인스턴스)로 웹 서버 띄우기

whisper-worker 만들었던 것처럼, 이번엔 웹 서버용 컨테이너를 하나 더 만듭니다.

### 4-1) ACR 계정/비번 변수 만들기 (PowerShell용)

```powershell
$ACR_USER = az acr credential show -n safeacrteam6 --query "username" -o tsv
$ACR_PASS = az acr credential show -n safeacrteam6 --query "passwords[0].value" -o tsv
```

### 4-2) 컨테이너 만들기 (PowerShell 백틱 버전)

> `<pg-host>`, `<pg-user>`, `<stg-name>` 자리에 실제 값 넣어야 합니다.
> 로컬 `.env`에 있는 변수 그대로 가져오면 됩니다.
> (EH_TRANSCRIPTS_* 는 웹서버에서 안 쓰면 빈 값 넣어도 됨)

```powershell
az container create `
  --resource-group "2dt-1st-team6" `
  --name "safe-api" `
  --image "safeacrteam6.azurecr.io/safe-api:latest" `
  --os-type Linux `
  --ports 5000 `
  --ip-address Public `
  --registry-login-server "safeacrteam6.azurecr.io" `
  --registry-username $ACR_USER `
  --registry-password $ACR_PASS `
  --restart-policy Always `
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
      EH_TRANSCRIPTS_HUB_NAME="" `
      JWT_SECRET="아무거나_길게" `
      ALLOW_ANON_UPLOAD="true" `
      OSRM_SERVER_URL="<osrm-aci-url-있으면>"
```

* `OSRM_SERVER_URL` / `EH_*` / `JWT_SECRET` 같은 이름은 **config.py / .env에서 실제 쓰는 키랑 맞춰야** 합니다.
  → 정확한 키 이름은 제가 지금 코드 전체를 볼 수 없어서 **확실하지 않음**이라서,
  사용 중인 `.env`를 그대로 참고해서 맞춰 주세요.

---

## 5. 배포된 웹 서버 URL 확인

컨테이너 생성 후:

```powershell
az container show `
  -g "2dt-1st-team6" `
  -n "safe-api" `
  --query "ipAddress.fqdn" -o tsv
```

예를 들어 결과가 `safe-api.koreacentral.azurecontainer.io` 이런 식으로 나오면,

브라우저에서:

```text
http://safe-api.koreacentral.azurecontainer.io:5000/
```

로 접속하면 됩니다.

---

## 6. 중지 / 시작 / 로그 보는 법 (요금 관리)

whisper-worker랑 똑같이:

```powershell
# 중지
az container stop -g 2dt-1st-team6 -n safe-api

# 다시 시작
az container start -g 2dt-1st-team6 -n safe-api

# 로그 보기
az container logs -g 2dt-1st-team6 -n safe-api
```

완전히 삭제하고 싶으면:

```powershell
az container delete -g 2dt-1st-team6 -n safe-api
```

---

## 정리

1. `main.py` 에 `host="0.0.0.0"` / `PORT` 지원 추가
2. Dockerfile 작성 → `docker build -t safe-api .`
3. `docker run --env-file .env -p 5000:5000 safe-api` 로 로컬 테스트
4. ACR에 `safe-api` 푸시
5. `az container create` 로 ACI에 띄우기 (포트 5000 + 환경변수)
6. `az container show` 로 FQDN 확인해서 접속

지금 단계에서 **.env 내용이랑 config.py에 있는 환경변수 키**만 한 번 맞춰주면,
지금 로컬에서 보이는 그대로 Azure에서도 돌아가게 만들 수 있습니다.

원하면 **네 .env 안에 있는 키 목록** 보내주면,
그걸 기준으로 `az container create` 명령어에 들어갈 `--environment-variables` 블록을 딱 맞춰서 작성해드릴게요.
