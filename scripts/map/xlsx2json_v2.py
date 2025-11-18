import pandas as pd
import json
import os
import re
import math
import numpy as np


def safe_str(v):
    # NaN, None → 빈 문자열
    if v is None:
        return ""
    if isinstance(v, (float, np.floating)) and math.isnan(v):
        return ""
    return str(v)

# 1. 엑셀 불러오기 (이 파일 경로만 당신 환경에 맞게 수정)
df = pd.read_excel(
    "D:/azure_code/safe-monitoring-msdatashool/downloads/서울시 안심 귀갓길 시설물_fixed - 복사.xlsx",
    header=1,   # 엑셀의 2번째 줄이 실제 헤더라서 header=1
)

# 2. 시설명(보안등/CCTV/안심벨...)별로 records를 모을 딕셔너리
by_type = {}  # { "보안등": [...], "CCTV": [...], ... }

for _, row in df.iterrows():
    # 위도/경도 없는 건 스킵
    if pd.isna(row["위도"]) or pd.isna(row["경도"]):
        continue

    facility = row.get("시설명", "")
    if not isinstance(facility, str) or not facility.strip():
        facility = "기타"

    # name 구성 (주소 느낌으로)
    name_parts = []

    # 시군구명 / 읍면동명 / 세부위치설명 / 시설명 / 설치대수 를 합쳐서 name 만들기
    for col in ["시군구명", "읍면동명", "세부위치설명", "시설명"]:
        val = row.get(col, "")
        if isinstance(val, str) and val.strip():
            name_parts.append(val.strip())

    cnt = row.get("설치대수", "")
    # 숫자이면 "n대" 붙이기
    if isinstance(cnt, (int, float, np.integer, np.floating)) and not math.isnan(cnt):
        name_parts.append(f"{int(cnt)}대")

    name = " / ".join(name_parts)

    record = {
        "name": name,
        "lat": float(row["위도"]),
        "lng": float(row["경도"]),
        "agency": safe_str(row.get("관리기관", "")),
        "installed_at": safe_str(row.get("조성년월", "")),
        # 완전히 동일한 형식만 필요하면 아래 'type' 키는 삭제해도 됩니다.
        "type": facility,
    }

    by_type.setdefault(facility, []).append(record)


# 3. 시설명 → 파일명 매핑 함수
def make_filename(facility: str) -> str:
    # 주요 3개는 영어로 고정
    custom = {
        "보안등": "lights",
        "CCTV": "cctv",
        "안심벨": "bells",
    }

    if facility in custom:
        slug = custom[facility]
    else:
        # 나머지는 한글 포함 허용, 공백/특수문자는 '_' 로 치환
        slug = re.sub(r"[^0-9A-Za-z가-힣]+", "_", facility).strip("_")

    return f"safe_{slug}.json"


# 4. 분류별 JSON 파일로 저장
os.makedirs("static/data", exist_ok=True)

for facility, records in by_type.items():
    filename = make_filename(facility)
    out_path = os.path.join("static/data", filename)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    print(f"{facility}: {len(records)} rows saved to {out_path}")
