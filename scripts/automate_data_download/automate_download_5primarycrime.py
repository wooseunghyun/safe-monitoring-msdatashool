# scripts/automate_download_5primarycrime.py
import os
import time
from dotenv import load_dotenv
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC

from src.download_utils import (
    make_driver,
    login_bigdata,
    wait_for_download_complete,
    click_js,
    accept_alert_if_any,
)

load_dotenv()
USER = os.getenv("PLATFORM_USER")
PW = os.getenv("PLATFORM_PASS")

DOWNLOAD_DIR = "./downloads"
PRODUCT_URL = "https://www.bigdata-policing.kr/product/view?product_id=PRDT_374"  # 5대 강력 사건사고

driver = make_driver(download_dir=DOWNLOAD_DIR, headless=False)

try:
    # 1) 로그인
    login_bigdata(driver, USER, PW)

    # 2) 상품 페이지로 이동
    driver.get(PRODUCT_URL)
    wait = driver.wait

    # 3) 릴리즈 테이블에서 첫 번째 행 체크
    table_body = wait.until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "table[summary='릴리즈 데이터'] tbody"))
    )
    first_row = table_body.find_elements(By.CSS_SELECTOR, "tr")[0]
    checkbox = first_row.find_element(By.CSS_SELECTOR, "td.center.type-check input[type='checkbox']")
    driver.execute_script("arguments[0].click();", checkbox)

    # 4) 아래 '구매하기' 버튼 클릭
    buy_btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button.btn.btn-checkout.square")))
    click_js(driver, buy_btn)

    # 5) 첫 번째 alert 처리 ("선택한 데이터를 구매하시겠습니까?")
    accept_alert_if_any(driver, timeout=5)

    # 6) /purchase/branch 로 이동 기다리기
    wait.until(EC.url_contains("/purchase/branch"))

    # 7) 최종 구매 버튼 클릭
    final_buy_btn = wait.until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, "button#checkout_button.btn.btn-checkout.square"))
    )
    final_buy_btn.click()

    # 8) 두 번째 alert 처리
    accept_alert_if_any(driver, timeout=5)

    # 9) 주문 목록으로 이동
    driver.get("https://www.bigdata-policing.kr/product/order/list")
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "table.cart-item-list tbody")))

    # 10) 가장 위 주문의 주문상세 클릭
    detail_btns = wait.until(
        EC.presence_of_all_elements_located((By.CSS_SELECTOR, "button.btn-view-order-detail"))
    )
    detail_btns[0].click()

    # 11) 상세 페이지에서 다운로드 버튼들 중 첫 번째 클릭
    dl_btns = wait.until(
        EC.presence_of_all_elements_located((By.CSS_SELECTOR, "button.btn-download"))
    )
    dl_btns[0].click()

    # 12) 다운로드 완료 대기
    downloaded = wait_for_download_complete(DOWNLOAD_DIR, timeout=90)
    print("✅ downloaded:", downloaded)

finally:
    driver.quit()
