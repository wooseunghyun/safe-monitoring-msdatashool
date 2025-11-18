import logging
import requests


# ▒▒ 서울시 API (CCTV용) ▒▒
def fetch_paged_data(base_url, api_key, service_name):
    start = 1
    end = 1000
    all_data = []

    while True:
        url = f"{base_url}/{api_key}/json/{service_name}/{start}/{end}/"
        logging.info(f"➡ 서울시 API 요청: {start}~{end}")

        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            logging.error(f"❌ 서울시 API 요청 실패: {e}")
            break

        rows = data.get(service_name, {}).get("row", [])
        if not rows:
            logging.info("데이터 없음. 종료.")
            break

        all_data.extend(rows)

        if len(rows) < 1000:
            break

        start += 1000
        end += 1000

    return all_data



# ▒▒ ODCloud API (가로등용) ▒▒
def odcloud_fetch_all(base_url, api_key, per_page=1000):
    page = 1
    all_data = []

    while True:
        url = f"{base_url}?page={page}&perPage={per_page}&serviceKey={api_key}"
        logging.info(f"➡ ODCloud API 요청: page={page}")

        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            logging.error(f"❌ ODCloud 요청 실패: {e}")
            break

        rows = data.get("data", [])
        if not rows:
            logging.info("데이터 없음. 종료.")
            break

        all_data.extend(rows)

        if len(rows) < per_page:
            break

        page += 1

    return all_data
