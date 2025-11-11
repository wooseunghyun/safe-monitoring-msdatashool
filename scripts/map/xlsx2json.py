# import pandas as pd

# df = pd.read_excel("D:/azure_code/safe-monitoring-msdatashool/downloads/생활방범_CCTV_필터 1.xlsx")
# # 컬럼명이 정확히 뭐였는지 모르니 아래는 네가 실제 컬럼명으로 바꿔
# df = df.rename(columns={
#     "WGS84위도": "lat",
#     "WGS84경도": "lng",
#     "소재지도로명주소": "name"
# })

# # 필요한 컬럼만
# out = df[["name", "lat", "lng"]].to_dict(orient="records")

# import json
# with open("cctv.json", "w", encoding="utf-8") as f:
#     json.dump(out, f, ensure_ascii=False, indent=2)

import pandas as pd
import json
import os

# 1. 엑셀 불러오기
df = pd.read_excel("D:/azure_code/safe-monitoring-msdatashool/downloads/생활방범_CCTV_필터 1.xlsx")

records = []
for _, row in df.iterrows():
    # 위도/경도 없는 건 스킵
    if pd.isna(row["WGS84위도"]) or pd.isna(row["WGS84경도"]):
        continue

    road_addr = row.get("소재지도로명주소", "")
    jibun_addr = row.get("소재지지번주소", "")
    purpose = row.get("설치목적구분", "")
    cnt = row.get("카메라대수", "")

    # 주소 우선순위: 도로명 → 지번
    addr = road_addr if isinstance(road_addr, str) and road_addr.strip() else jibun_addr

    # name 구성
    name_parts = []
    if addr:
        name_parts.append(addr)
    if purpose:
        name_parts.append(purpose)
    if cnt:
        name_parts.append(f"{int(cnt)}대" if not pd.isna(cnt) else "")
    name = " / ".join([p for p in name_parts if p])

    records.append({
        "name": name,
        "lat": float(row["WGS84위도"]),
        "lng": float(row["WGS84경도"]),
        # 혹시 나중에 쓰려고 몇 개 더 넣어둘 수도 있음
        "agency": row.get("관리기관명", ""),
        "installed_at": str(row.get("설치연월", "")),
    })

# 2. 저장 경로 (Flask에서 읽기 쉽게)
os.makedirs("static/data", exist_ok=True)
with open("static/data/cctv.json", "w", encoding="utf-8") as f:
    json.dump(records, f, ensure_ascii=False, indent=2)

print(f"{len(records)} rows saved to static/data/cctv.json")
