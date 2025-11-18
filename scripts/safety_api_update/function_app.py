import azure.functions as func
from streetlight_api import run as run_streetlight
from cctv_api import run as run_cctv


app = func.FunctionApp()

# CCTV ─ 매월 1일 00:00 실행
@app.schedule(schedule="0 0 0 1 * *", arg_name="myTimer",run_on_startup=True)
def cctv_timer(myTimer: func.TimerRequest):
    run_cctv(myTimer)

# 가로등 ─ 매월 1일 00:05 실행
@app.schedule(
    schedule="0 5 0 1 * *", arg_name="myTimer",run_on_startup=True)
def streetlight_timer(myTimer: func.TimerRequest):
    run_streetlight(myTimer)