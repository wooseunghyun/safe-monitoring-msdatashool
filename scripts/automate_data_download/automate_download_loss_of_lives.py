from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import os
from dotenv import load_dotenv
import glob

def wait_for_download_complete(download_dir, timeout=60):
    start = time.time()
    last_size = -1
    filename = None

    while time.time() - start < timeout:
        files = glob.glob(os.path.join(download_dir, "*.csv"))
        if files:
            latest = max(files, key=os.path.getctime)
            size = os.path.getsize(latest)
            # 파일 크기가 일정 시간 동안 변하지 않으면 다운로드 완료로 간주
            if size == last_size:
                return latest
            last_size = size
        time.sleep(1)
    raise TimeoutError("Download did not complete in time.")


load_dotenv()
USER = os.getenv("PLATFORM_USER")
PW = os.getenv("PLATFORM_PASS")

chrome_options = Options()
# chrome_options.add_argument("--headless")
chrome_options.add_experimental_option("prefs", {
    "download.default_directory": os.path.abspath("./downloads"),
    "download.prompt_for_download": False,
    "download.directory_upgrade": True,
    "safebrowsing.enabled": True,
})

driver = webdriver.Chrome(options=chrome_options)

try:
    # 1) 로그인 페이지 진입
    driver.get("https://www.bigdata-policing.kr/login")
    wait = WebDriverWait(driver, 10)

    # 2) 아이디/비번 입력
    # 사이트마다 name/id가 조금 다를 수 있어서 둘 다 시도
    try:
        id_box = wait.until(EC.presence_of_element_located((By.ID, "userId")))
        pw_box = driver.find_element(By.ID, "userPw")
    except:
        id_box = wait.until(EC.presence_of_element_located((By.NAME, "username")))
        pw_box = driver.find_element(By.NAME, "password")

    id_box.send_keys(USER)
    pw_box.send_keys(PW)

    # 로그인 버튼 클릭
    # 버튼 셀렉터는 실제 페이지에서 한 번만 확인해서 맞춰주세요.
    try:
        login_btn = driver.find_element(By.CSS_SELECTOR, "button.btn.positive.lar.shadow[type='submit']")
    except:
        login_btn = driver.find_element(By.CSS_SELECTOR, "button[type=submit]")
    login_btn.click()

    # 로그인 완료 대기
    time.sleep(1)

    #국내 인명피해 사건 페이지
    driver.get("https://www.bigdata-policing.kr/product/view?product_id=PRDT_230")
    # 릴리즈 테이블이 나올 때까지 대기
    table_body = wait.until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "table[summary='릴리즈 데이터'] tbody"))
    )


    # 3) 첫 번째 릴리즈 데이터 체크박스 선택
    rows = table_body.find_elements(By.CSS_SELECTOR, "tr")
    if not rows:
        raise RuntimeError("릴리즈 데이터 행을 찾지 못했습니다.")
    first_row = rows[0]
    # 첫 번째 칸이 체크박스 있는 td
    checkbox = first_row.find_element(By.CSS_SELECTOR, "td.center.type-check input[type='checkbox']")
    driver.execute_script("arguments[0].click();", checkbox)  # 가끔 가려져 있어서 JS로 클릭

    # 4) 아래 파란바의 '구매하기' 버튼 클릭
    # 4) 아래 파란바의 '구매하기' 버튼 클릭
    buy_btn = wait.until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, "button.btn.btn-checkout.square"))
    )

    # 가려지는 문제 때문에 JS로 강제 클릭
    driver.execute_script("arguments[0].scrollIntoView(true);", buy_btn)
    driver.execute_script("window.scrollBy(0, -150);")
    time.sleep(0.3)
    driver.execute_script("arguments[0].click();", buy_btn)


    #5 🔴 여기서 바로 alert 뜨니까 먼저 처리
    try:
        alert = WebDriverWait(driver, 5).until(EC.alert_is_present())
        alert.accept()  # "확인" 누름
        print("alert accepted: 선택한 데이터를 구매하시겠습니까?")
    except:
        # alert 안 뜨면 그냥 넘어감
        pass

    # 이제 다음 페이지로 넘어가는 걸 기다림
    wait.until(EC.url_contains("/purchase/branch"))

    # 실제 구매 버튼은 이렇게 생겼음: <button id="checkout_button" class="btn btn-checkout square">
    final_buy_btn = wait.until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, "button#checkout_button.btn.btn-checkout.square"))
    )
    final_buy_btn.click()

    # 6) "데이터를 구매하시겠습니까?" alert 확인
    alert = wait.until(EC.alert_is_present())
    alert.accept()
    # 구매가 성공하면 보통 주문이 생성됨

    # 3) 주문 내역 페이지로 이동
    driver.get("https://www.bigdata-policing.kr/product/order/list")
    # 페이지 로딩 대기
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "table.cart-item-list")))

    # 4) 주문상세 버튼 클릭
    # <button class="btn btn-view-order-detail" data-order-no="OM....">주문상세</button>
    detail_btns = wait.until(
        EC.presence_of_all_elements_located((By.CSS_SELECTOR, "button.btn-view-order-detail"))
        # EC.element_to_be_clickable(
        #     (By.CSS_SELECTOR, f"button.btn-view-order-detail[data-order-no='{ORDER_NO}']")
        # )
    )
    if detail_btns:
        detail_btns[0].click()
    else:
        print("❌ detail_btn 버튼을 찾을 수 없습니다.")

    # 5) 상세 페이지 로딩 대기
    # 상세 페이지에서 다운로드 버튼이 나타날 때까지 기다림
    # 실제 버튼 클래스/텍스트를 여기서 맞춰주세요.
    dl_btns = wait.until(
        EC.presence_of_all_elements_located((By.CSS_SELECTOR, "button.btn-download"))
        # EC.element_to_be_clickable(
        #     (
        #         By.CSS_SELECTOR,
        #         f"button.btn-download[data-odmaster='{ORDER_NO}']"
        #     )
        # )
    )
    if dl_btns:
        dl_btns[0].click()
    else:
        print("❌ detail_btn 버튼을 찾을 수 없습니다.")

    # 6) 다운로드 완료 기다리기
    download_dir = "./downloads"
    os.makedirs(download_dir, exist_ok=True)
    timeout = 60
    start = time.time()
    downloaded = wait_for_download_complete(download_dir, timeout=90)
    while time.time() - start < timeout:
        files = [f for f in os.listdir(download_dir) if not f.endswith(".crdownload")]
        if files:
            print("Downloaded:", files)
            break
        time.sleep(1)

finally:
    driver.quit()
