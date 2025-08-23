import xml.etree.ElementTree as ET
import time
import requests
from functools import partial
import json
from datetime import datetime, timezone, timedelta
import os

max_timestamp = int(datetime.now().timestamp())# 앱 실행시점 시간


chat_id =''
telebotUrl =''
def telegramMsg(msg):    
    global bot_token
    global chat_id
    
    payload = {
        'chat_id': chat_id,
        'text': msg
    }

    requests.post(telebotUrl, data=payload)
    
def load_max_timestamp():
    global max_timestamp, first
    if os.path.exists("max_timestamp.txt"):
        with open("max_timestamp.txt", "r") as f:
            try:
                data = json.load(f)
                max_timestamp = int(data.get("max_timestamp", 0))
                first = bool(data.get("first", True))  # 기본값 True
            except (ValueError, json.JSONDecodeError):
                max_timestamp = 0
                first = True
                
def save_max_timestamp():
    data = {
        "max_timestamp": max_timestamp,
        "first": first
    }
    with open("max_timestamp.txt", "w") as f:
        json.dump(data, f)

def parse_trans_data(data, check_amount):
    #data = json.loads(response_text)    
    global max_timestamp #글로벌 변수로 알림
        
    has_newer = True
    

    for item in data.get("results", []):
        dt_str = item["datetime"]
        dt_obj = datetime.strptime(dt_str, "%Y-%m-%dT%H:%M:%S.000Z")
        dt_obj = dt_obj.replace(tzinfo=timezone.utc)  # UTC 지정
            

        dt_unix = int(dt_obj.timestamp())
        dt_amount = int(float(item["amount"]))
        
        
        if  max_timestamp >= dt_unix:
            has_newer  = False
            continue
        
        kst = timezone(timedelta(hours=9))
        dt_kst = dt_obj.astimezone(kst)
        
        print(f'{dt_kst} -  blockId:{item["block_id"]} transaction_hash:{item["transaction_hash"]} amount: {item["amount"]}')
            
        if check_amount <= dt_amount:#알림            
            telegramMsg(f'[이동감지] {dt_kst} - blockId:{item["block_id"]} transaction_hash:{item["transaction_hash"]}  amount: {item["amount"]}' )
            print(f'[이동감지] {dt_kst} -blockId:{item["block_id"]} transaction_hash:{item["transaction_hash"]} amount: {item["amount"]}')

        # 새로운 데이터 → max_timestamp 갱신
        if  max_timestamp < dt_unix:                       
            max_timestamp = dt_unix
            readable_time = datetime.fromtimestamp(max_timestamp).strftime("%Y-%m-%d %H:%M:%S")
            
            print(f"기준 시간 변경:{readable_time}")
                
    
    #save_max_timestamp()
    return has_newer
    

def read_settings(xml_file):
    tree = ET.parse(xml_file)
    root = tree.getroot()    
    global telebotUrl
    global chat_id

    api_key = root.find('apiKey').text
    bot_token = root.find('bot_token').text
    chat_id = root.find('chat_id').text
    refresh_sec = int(root.find('refreshSec').text)
    amount= int(root.find('amount').text)
    tokenAddress = root.find('tokenAddress').text


    telebotUrl = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    
    return {
        'apiKey': api_key,        
        'refreshSec': refresh_sec,
        'tokenAddress':tokenAddress,
        'amount':amount
    }


def my_function(api_key,  tokenAddress,checkAmount, max_pages=50):
    
    readable_time = datetime.fromtimestamp(max_timestamp).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[탐지중..]")
    print(f"기준 시간:{readable_time}")
    print(f"개 수:{checkAmount}")

    payload = {}
    headers = {
        'Accept': '*/*',
        'Authorization': 'Bearer '+api_key
    }
    
    page = 1
    
    while page <= max_pages:
        url = f"https://mainnet-oapi.kaiascan.io/api/v1/tokens/{tokenAddress}/transfers?page={page}&size=2000"
        headers = {
            'Accept': '*/*',
            'Authorization': 'Bearer ' + api_key
        }
        response = requests.request("GET", url, headers=headers, data=payload)
    
        if response.status_code != 200:
            print(f"API 요청 실패: {response.status_code}")
            telegramMsg(f"API 요청 실패: {response.status_code}")
            return
        
       
    
        data = response.json()
        results = data.get("results", [])

        if not results:# 더 이상 데이터 없음 → 루프 종료
            break

        # 오래된 데이터부터 처리
        results.reverse()
        
        has_newer = parse_trans_data({"results": results}, checkAmount)
        
         # 이번 페이지에서 max_timestamp보다 큰 데이터가 있었다면 → 다음 페이지 확인
        if has_newer:
            page += 1
        else:
            break  # 더 이상 새 데이터 없음 → 종료        

        #print(response.text)    

def run_periodically(refresh_sec, func):
    interval_sec = refresh_sec
    last_notify_time = time.time()
    while True:
        func()
        
        now = time.time()
        # 1시간(3600초)마다 메시지 전송
        if now - last_notify_time >= 3600:
            telegramMsg("working")  # <- 여기에 보냄
            print("working")
            last_notify_time = now
            
        time.sleep(interval_sec)

if __name__ == "__main__":
    #load_max_timestamp() 필요없음
    settings = read_settings('setting.xml')    
    refresh_sec = settings['refreshSec']

    print(f"{refresh_sec}초마다 함수 실행을 시작합니다...")
    wrapped_function = partial(my_function, settings['apiKey'], settings['tokenAddress'],settings['amount'])
    run_periodically(refresh_sec, wrapped_function)
