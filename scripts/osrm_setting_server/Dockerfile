FROM osrm/osrm-backend:latest

# 작업 디렉터리는 절대경로로 지정
WORKDIR /data

# 실제 파일 경로/이름에 맞춰 복사
# (좌측은 빌드 컨텍스트의 상대경로, 우측은 컨테이너 내부 경로)
COPY data/south-korea-251111.osm.pbf /data/south-korea.osm.pbf

# OSRM 전처리 (foot 프로필)
RUN osrm-extract -p /opt/foot.lua /data/south-korea.osm.pbf && \
    osrm-partition /data/south-korea.osrm && \
    osrm-customize /data/south-korea.osrm

EXPOSE 5000
CMD ["osrm-routed", "--algorithm", "mld", "/data/south-korea.osrm"]
