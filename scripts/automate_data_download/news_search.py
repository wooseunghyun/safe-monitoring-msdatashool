import os
import sys
import urllib.request
import datetime
import time
import json
import pandas as pd
import datetime
import re
from dotenv import load_dotenv

load_dotenv()

# 환경변수에서 불러오기
client_id = os.getenv("NAVER_CLIENT_ID")
client_secret = os.getenv("NAVER_CLIENT_SECRET")

#검색 키워드
search_keyword = '1기 신도시'

# 네이버 검색 API
client_id = "본인의 client_id"
client_secret = "본인의 client_secret"

encText = urllib.parse.quote(str(search_keyword))
today = datetime.datetime.now().strftime('%Y-%m-%d')

# 테스트용 첫 페이지만 가져오기
url = "https://openapi.naver.com/v1/search/news.json?query=" + encText + "&start=" + str(1) + "&display=100"

request = urllib.request.Request(url)
request.add_header("X-Naver-Client-Id",client_id)
request.add_header("X-Naver-Client-Secret",client_secret)

response = urllib.request.urlopen(request)
rescode = response.getcode()

if(rescode==200):
    response_body = response.read()
    print('request Success')
    # print(response_body.decode('utf-8'))
else:
    print("Error Code:" + rescode)


response_result = response_body.decode('utf-8')
response_result = json.loads(response_result)