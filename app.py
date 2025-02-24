#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
請注意：
  - 本程式使用 requests 模組進行 HTTP 請求
  - 若尚未安裝 requests 模組，請先執行： pip install requests
"""

import os
import json
import requests
import datetime
import time
from zoneinfo import ZoneInfo
import pytz


# --------------------------
# 定義共用常數
# --------------------------
CHANNEL_ACCESS_TOKEN = "DS4xuDmTEm1JdSjB4nicpJSCWEFfkoK71AgNDslimzElHInP/irAjQ0RjeBzZuZ4kk3cZrOyQGYMMA5wnKoML0N+0L9SZSWt3Kuv+1e4QD4c9LuJahduzJ44VGu1wPbbKL6zBe9M7TiCA7nPzJqOxQdB04t89/1O/w1cDnyilFU="
GROUP_ID = "C538d8773e17d6697fac0175c4077fd73"
LINE_PUSH_URL = 'https://api.line.me/v2/bot/message/push'
tz_tw = pytz.timezone('Asia/Taipei')

weather_url = ('https://opendata.cwa.gov.tw/api/v1/rest/datastore/W-C0033-002'
               '?Authorization=CWA-BAD98D16-5AC9-46D7-80AB-F96CB1286F16'
               '&phenomena=%E5%A4%A7%E9%9B%A8,%E8%B1%AA%E9%9B%A8,'
               '%E5%A4%A7%E8%B1%AA%E9%9B%A8,%E8%B6%85%E5%A4%A7%E8%B1%AA%E9%9B%A8')



weather_location_url = ('https://opendata.cwa.gov.tw/api/v1/rest/datastore/W-C0033-001'
                   '?Authorization=CWA-BAD98D16-5AC9-46D7-80AB-F96CB1286F16'
                   '&phenomena=%E5%A4%A7%E9%9B%A8,%E8%B1%AA%E9%9B%A8,'
                   '%E5%A4%A7%E8%B1%AA%E9%9B%A8,%E8%B6%85%E5%A4%A7%E8%B1%AA%E9%9B%A8')

# 測試用天氣 API 資料
# weather_url = ('https://raw.githubusercontent.com/boatman3132/line-weather-bot-ntu/refs/heads/main/test_weather_data.json?token=GHSAT0AAAAAAC25HZ4YYPRHTPXGFUMCP55KZ5JL4DQ')


# --------------------------
# 定義 ScriptProperties 類別
# 此類別負責讀取與寫入同一資料夾內的 script_properties.json 檔案
# --------------------------
class ScriptProperties:
    def __init__(self, file_path='script_properties.json'):
        self.file_path = file_path
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    self.properties = json.load(f)
            except Exception as e:
                print("讀取 properties 檔案失敗，使用空的設定：", e)
                self.properties = {}
        else:
            self.properties = {}

    def get_property(self, key):
        return self.properties.get(key)

    def set_property(self, key, value):
        self.properties[key] = value
        try:
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(self.properties, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print("寫入 properties 檔案失敗：", e)

# 建立全域 script_properties 物件
script_properties = ScriptProperties()

# --------------------------
# 主函式：檢查天氣 API 資料、組合警報訊息、查找圖片並發送 LINE 訊息
# --------------------------

def sendBroadcastMessage():
    # 取得現在時間
    now = datetime.datetime.now(tz_tw)
    formatted_now = now.strftime("%Y-%m-%d %H:%M:%S")

    # 讀取上次發送的資訊
    last_sent_info = script_properties.get_property("lastSentInfo")
    if isinstance(last_sent_info, str):
        try:
            last_sent_info = json.loads(last_sent_info)
        except json.JSONDecodeError:
            print("lastSentInfo 格式錯誤，重置為空字典")
            last_sent_info = {}
    elif last_sent_info is None:
        last_sent_info = {}

    last_sent_time = last_sent_info.get("lastSentTime")

    # 讀取氣象資訊
    weatherData = script_properties.get_property("weatherData")
    if isinstance(weatherData, str):
        try:
            weatherData = json.loads(weatherData)
        except json.JSONDecodeError:
            weatherData = {}
    elif weatherData is None:
        weatherData = {}

    last_update_time = weatherData.get("update")
    if last_update_time:
        try:
            # 解析字串為 datetime 物件（仍是 offset-naive）
            last_update_time = datetime.datetime.strptime(last_update_time, "%Y-%m-%d %H:%M:%S")
            # 轉換為 offset-aware（加上台灣時區）
            last_update_time = last_update_time.replace(tzinfo=tz_tw)
        except ValueError:
            print("時間格式錯誤，重置 update")
            last_update_time = now - datetime.timedelta(hours=3)

    # 計算時間差（現在 - 上次發送時間）
    time_diff = (now - last_update_time).total_seconds() / 60  # 轉換為分鐘

    # 新增判斷 lastSentTime 是否在過去 30 分鐘內
    if last_sent_time:
        try:
            last_sent_time = datetime.datetime.strptime(last_sent_time, "%Y-%m-%d %H:%M:%S")
            last_sent_time = last_sent_time.replace(tzinfo=tz_tw)
            last_sent_diff = (now - last_sent_time).total_seconds() / 60  # 轉換為分鐘

            if last_sent_diff <= 30:
                print("過去已發送過警報，不重複發送")
                # 更新 lastSentTime
                last_sent_info.update({"lastSentTime": formatted_now})
                script_properties.set_property("lastSentInfo", last_sent_info)
                return
        except ValueError:
            print("lastSentTime 時間格式錯誤，無法進行比較")

    # 更新 lastSentTime
    last_sent_info.update({"lastSentTime": formatted_now})
    script_properties.set_property("lastSentInfo", last_sent_info)

    warning_messages = []

    # 取得並解析天氣警報資料，同時根據取得的 JSON 資料更新 script_properties.json
    try:
        response = requests.get(weather_url)
        weather_data = response.json()

        if (weather_data.get("success") == "true" and
            weather_data.get("records") and
            weather_data["records"].get("record")):

            records = weather_data["records"]["record"]

            # 取第一筆資料，並從中解析所需欄位
            first_record = records[0]
            datasetInfo = first_record.get("datasetInfo", {})

            # 若 issueTime 與 update 缺失或空值，則填入當前時間
            issueTime = datasetInfo.get("issueTime")
            if not issueTime:
                issueTime = formatted_now
            update_time = datasetInfo.get("update")
            if not update_time:
                update_time = formatted_now

            # 解析 hazard 資料取得 phenomena 與 location
            phenomena = ""
            locations = []
            hazard_conditions = first_record.get("hazardConditions", {})
            if (hazard_conditions and
                hazard_conditions.get("hazards") and
                hazard_conditions["hazards"].get("hazard")):
                hazards = hazard_conditions["hazards"]["hazard"]
                if hazards:
                    first_hazard = hazards[0]
                    phenomena = first_hazard.get("info", {}).get("phenomena")
                    if not phenomena:
                        phenomena = "無數據"
                    affectedAreas = first_hazard.get("info", {}).get("affectedAreas", {})
                    if affectedAreas and affectedAreas.get("location"):
                        locations = [loc.get("locationName", "") for loc in affectedAreas["location"] if loc.get("locationName")]
                    if not locations:
                        locations = ["無數據"]
                else:
                    phenomena = "無數據"
                    locations = ["無數據"]
            else:
                phenomena = "無數據"
                locations = ["無數據"]

            # 新增功能：比對舊的與新的警報區域
            # 若先前的 weatherData 有設定過 location，則進行比對
            old_locations = weatherData.get("location", [])
            if old_locations:
                added_locations = list(set(locations) - set(old_locations))
                removed_locations = list(set(old_locations) - set(locations))
                change_message = ""
                if added_locations:
                    change_message += "新增警報區域：" + ", ".join(added_locations)
                if removed_locations:
                    if change_message:
                        change_message += "\n"
                    change_message += "減少警報區域：" + ", ".join(removed_locations)
                if change_message:
                    # 將變化訊息放在警報訊息的最前面
                    warning_messages.insert(0, change_message)

            # 將 lastSentTime、phenomena、location、issueTime 與 update 存入 script_properties.json
            weather_info = {
                "lastSentTime": formatted_now,
                "phenomena": phenomena,
                "location": locations,
                "issueTime": issueTime,
                "update": update_time
            }
            script_properties.set_property("weatherData", weather_info)

            # 解析所有符合條件的警報訊息
            for record in records:
                hazard_conditions = record.get("hazardConditions")
                if (hazard_conditions and
                    hazard_conditions.get("hazards") and
                    hazard_conditions["hazards"].get("hazard")):
                    hazards = hazard_conditions["hazards"]["hazard"]
                    for hazard in hazards:
                        phenomenon = hazard.get("info", {}).get("phenomena", "無數據")
                        content_text = record.get("contents", {}).get("content", {}).get("contentText", "").strip()
                        locations_msg = []
                        if (hazard.get("info", {}).get("affectedAreas") and
                            hazard.get("info", {}).get("affectedAreas").get("location")):
                            locations_msg = [loc.get("locationName", "") for loc in hazard["info"]["affectedAreas"]["location"]]
                        if not locations_msg:
                            locations_msg = ["無數據"]
                        message_text = (f"⚠️ 最新{phenomenon}特報 ⚠️\n{content_text}\n\n"
                                        f"特報發佈時間：{update_time}\n\n"
                                        f"📍 {phenomenon}特報地區：\n" + "\n".join(locations_msg))
                        warning_messages.append(message_text)
    except Exception as error:
        print("天氣 API 請求失敗：", error)
        return

    if not warning_messages:
        print("沒有符合條件的警報，不發送訊息")
        return

    # 設定基準時間（將分鐘、秒、毫秒歸零）
    base_time = now.replace(minute=0, second=0, microsecond=0)

    radar_image_url = ""
    warning_image_url = ""
    max_attempts = 2
    attempt_time = now

    # 嘗試取得雷達與累積雨量圖片，最多嘗試 max_attempts 次
    for i in range(max_attempts):
        year = attempt_time.year
        month = f"{attempt_time.month:02d}"
        day = f"{attempt_time.day:02d}"
        hours = f"{attempt_time.hour:02d}"

        minutes_floored = (attempt_time.minute // 10) * 10
        formatted_minutes = f"{minutes_floored:02d}"
        radar_url = f"https://www.cwa.gov.tw/Data/radar/CV1_TW_3600_{year}{month}{day}{hours}{formatted_minutes}.png"

        warning_minutes_floored = (attempt_time.minute // 30) * 30
        formatted_warning_minutes = f"{warning_minutes_floored:02d}"
        daily_accumulated_rainfall_url = f"https://www.cwa.gov.tw/Data/rainfall/{year}-{month}-{day}_{hours}{formatted_warning_minutes}.QZJ8.jpg"

        try:
            res_radar = requests.get(radar_url)
            if res_radar.status_code == 200:
                radar_image_url = radar_url
        except Exception as e:
            pass

        try:
            res_warning = requests.get(daily_accumulated_rainfall_url)
            if res_warning.status_code == 200:
                warning_image_url = daily_accumulated_rainfall_url
        except Exception as e:
            pass

        if radar_image_url and warning_image_url:
            break

        attempt_time = attempt_time - datetime.timedelta(minutes=10)

    # 建構 LINE 訊息內容
    # 建構 LINE 訊息內容，將所有警報文字訊息合併成一個
    
    # 將所有警報文字訊息合併成一個
    if warning_messages:
        combined_warning_text = "\n\n".join(warning_messages)
    else:
        combined_warning_text = ""
    
    # 取得累積雨量報告訊息（改成回傳字串的函式）
    rainfall_report_text = getMaximumAccumulatedRainfallReport()
    
    # 將兩個文字訊息合併
    if combined_warning_text and rainfall_report_text:
        final_text = combined_warning_text + "\n\n" + rainfall_report_text
    else:
        final_text = combined_warning_text or rainfall_report_text
    
    # 建構 LINE 訊息內容
    messages = []
    if final_text:
        messages.append({"type": "text", "text": final_text})
    
    # 若有圖片，也照原本方式加入
    if warning_image_url:
        messages.append({
            "type": "image",
            "originalContentUrl": "https://www.cwa.gov.tw/Data/warning/W26_C.png?",
            "previewImageUrl": "https://www.cwa.gov.tw/Data/warning/W26_C.png?"
        })
    if radar_image_url:
        messages.append({
            "type": "image",
            "originalContentUrl": radar_image_url,
            "previewImageUrl": radar_image_url
        })
    if warning_image_url:
        messages.append({
            "type": "image",
            "originalContentUrl": warning_image_url,
            "previewImageUrl": warning_image_url
        })
    
    message_payload = {
        "to": GROUP_ID,
        "messages": messages
    }
    
    sendLineMessage(message_payload)



# --------------------------
# 發送 LINE 訊息的共用函式
# --------------------------
def sendLineMessage(payload):
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + CHANNEL_ACCESS_TOKEN
    }
    try:
        response = requests.post(LINE_PUSH_URL, headers=headers, json=payload)
        if response.status_code == 200:
            print("LINE 訊息發送成功")
        else:
            print("LINE 訊息發送失敗，狀態碼：", response.status_code, response.text)
    except Exception as error:
        print("LINE 訊息發送失敗：", error)


# --------------------------
# 以下為被註解掉的測試用 log 版本，原本是不會發送 LINE 訊息，只是記錄訊息內容
# --------------------------
# def sendLineMessage(payload):
#     # 遍歷所有訊息，記錄內容
#     for message in payload.get("messages", []):
#         if message.get("type") == "text":
#             print("[訊息內容] " + message.get("text", ""))
#         elif message.get("type") == "image":
#             print("[圖片網址] " + message.get("originalContentUrl", ""))


# --------------------------
# 發送各縣市最高累積雨量資訊
# --------------------------

def getMaximumAccumulatedRainfallReport():
    rainfall_url = ('https://opendata.cwa.gov.tw/api/v1/rest/datastore/O-A0002-001'
                    '?Authorization=CWA-BAD98D16-5AC9-46D7-80AB-F96CB1286F16'
                    '&RainfallElement=Past1hr,Past3hr,Past24hr'
                    '&GeoInfo=CountyName,TownName')

    alert_counties = set()

    try:
        response = requests.get(weather_location_url)
        weather_data = response.json()
        if (weather_data.get("success") == "true" and
            weather_data.get("records") and
            weather_data["records"].get("location")):
            for location in weather_data["records"]["location"]:
                if (location.get("hazardConditions") and
                    location["hazardConditions"].get("hazards") and
                    len(location["hazardConditions"]["hazards"]) > 0):
                    alert_counties.add(location.get("locationName"))
    except Exception as error:
        print("天氣警報 API 請求失敗：", error)
        return ""

    if len(alert_counties) == 0:
        print("沒有符合條件的警報，不執行任何操作")
        return ""

    highest_rainfall_stations = {}

    try:
        response = requests.get(rainfall_url)
        rainfall_data = response.json()
        if (rainfall_data.get("success") == "true" and
            rainfall_data.get("records") and
            rainfall_data["records"].get("Station")):
            for station in rainfall_data["records"]["Station"]:
                county = station["GeoInfo"]["CountyName"]
                if county in alert_counties:
                    try:
                        past1hr = float(station["RainfallElement"]["Past1hr"]["Precipitation"])
                    except:
                        past1hr = 0
                    try:
                        past3hr = float(station["RainfallElement"]["Past3hr"]["Precipitation"])
                    except:
                        past3hr = 0
                    try:
                        past24hr = float(station["RainfallElement"]["Past24hr"]["Precipitation"])
                    except:
                        past24hr = 0

                    if (county not in highest_rainfall_stations or
                        past24hr > highest_rainfall_stations[county]["past24hr"]):
                        highest_rainfall_stations[county] = {
                            "county": county,
                            "town": station["GeoInfo"]["TownName"],
                            "station": station["StationName"],
                            "past1hr": past1hr,
                            "past3hr": past3hr,
                            "past24hr": past24hr
                        }
    except Exception as error:
        print("雨量 API 請求失敗：", error)
        return ""

    report_messages = ['當地1小時/3小時/24小時累積雨量']
    for station_data in highest_rainfall_stations.values():
        report_messages.append(f"{station_data['county']} {station_data['town']} {station_data['station']} "
                               f"{station_data['past1hr']}mm/{station_data['past3hr']}mm/{station_data['past24hr']}mm")

    if len(report_messages) == 0:
        print("沒有可報告的雨量數據")
        return ""

    combined_message = "\n".join(report_messages)
    return combined_message


# --------------------------
# 主程式進入點
# --------------------------
if __name__ == '__main__':
    sendBroadcastMessage()
