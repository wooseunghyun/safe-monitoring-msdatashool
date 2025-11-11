# src/download_utils.py
import os
import time
import glob
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC


def make_driver(download_dir="./downloads", headless=False):
    os.makedirs(download_dir, exist_ok=True)

    chrome_options = Options()
    if headless:
        chrome_options.add_argument("--headless")
    chrome_options.add_experimental_option("prefs", {
        "download.default_directory": os.path.abspath(download_dir),
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True,
    })
    driver = webdriver.Chrome(options=chrome_options)
    driver.wait = WebDriverWait(driver, 10)  # 편하게 쓰라고 붙여줌
    return driver


def login_bigdata(driver, user, pw):
    driver.get("https://www.bigdata-policing.kr/login")
    wait = driver.wait

    try:
        id_box = wait.until(EC.presence_of_element_located((By.ID, "userId")))
        pw_box = driver.find_element(By.ID, "userPw")
    except:
        id_box = wait.until(EC.presence_of_element_located((By.NAME, "username")))
        pw_box = driver.find_element(By.NAME, "password")

    id_box.send_keys(user)
    pw_box.send_keys(pw)

    try:
        login_btn = driver.find_element(By.CSS_SELECTOR, "button.btn.positive.lar.shadow[type='submit']")
    except:
        login_btn = driver.find_element(By.CSS_SELECTOR, "button[type=submit]")

    login_btn.click()
    time.sleep(1)  # 로그인 후 살짝 대기


def wait_for_download_complete(download_dir, timeout=60):
    start = time.time()
    last_size = -1
    while time.time() - start < timeout:
        files = glob.glob(os.path.join(download_dir, "*.csv"))
        if files:
            latest = max(files, key=os.path.getctime)
            size = os.path.getsize(latest)
            if size == last_size:
                return latest
            last_size = size
        time.sleep(1)
    raise TimeoutError("Download did not complete in time.")


def click_js(driver, element):
    driver.execute_script("arguments[0].scrollIntoView(true);", element)
    driver.execute_script("window.scrollBy(0, -150);")
    driver.execute_script("arguments[0].click();", element)


def accept_alert_if_any(driver, timeout=5):
    try:
        alert = WebDriverWait(driver, timeout).until(EC.alert_is_present())
        alert.accept()
        return True
    except:
        return False
