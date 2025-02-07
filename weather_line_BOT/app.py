#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
轉換自 Google Apps Script 程式碼

原始程式碼功能：
  - 檢查天氣 API 資料、組合警報訊息、查找各項圖片並發送 LINE 訊息
  - 同時也會發送各縣市最高累積雨量資訊

請注意：
  - 本程式使用 requests 模組進行 HTTP 請求
  - 為了模擬 Google Apps Script 的 PropertiesService，本程式使用檔案儲存方式儲存全域變數 (例如 lastSentTime)
  - 若尚未安裝 requests 模組，請先執行： pip install requests
"""

import os
import json
import requests
import datetime
import time

# --------------------------
# 定義共用常數
# --------------------------
CHANNEL_ACCESS_TOKEN = "m7mL7uj+S4utCL4fzeHcz7YebNzUWoncm+jsEcFoqXa3UzEmlgTLaRFyFEshKi6XJeXCth/v4Zj1vGpPxPAPVvSFky7hvMPDncXsmPdnrNgQEjqP4nbixNPeRuXdkY4hKQeQnx9quTC22aDkuIkCTwdB04t89/1O/w1cDnyilFU="
GROUP_ID = "C1744d43a6e011fb9e2819c43974ead95"
LINE_PUSH_URL = 'https://api.line.me/v2/bot/message/push'

# --------------------------
# 模擬 Google Apps Script 的 PropertiesService
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
                json.dump(self.properties, f)
        except Exception as e:
            print("寫入 properties 檔案失敗：", e)

# 建立全域 script_properties 物件
script_properties = ScriptProperties()

# --------------------------
# 主函式：檢查天氣 API 資料、組合警報訊息、查找各項圖片並發送 LINE 訊息
# 這個函式將會檢查天氣資料並發送警報訊息到 LINE 群組。
# --------------------------
def sendBroadcastMessage():
    weather_url = ('https://opendata.cwa.gov.tw/api/v1/rest/datastore/W-C0033-002'
                   '?Authorization=CWA-BAD98D16-5AC9-46D7-80AB-F96CB1286F16'
                   '&phenomena=%E5%A4%A7%E9%9B%A8,%E8%B1%AA%E9%9B%A8,'
                   '%E5%A4%A7%E8%B1%AA%E9%9B%A8,%E8%B6%85%E5%A4%A7%E8%B1%AA%E9%9B%A8')
    # 取得 script properties
    last_sent_time = script_properties.get_property("lastSentTime")
    now = datetime.datetime.now()

    # 檢查是否已發送過
    if last_sent_time:
        try:
            last_sent_date = datetime.datetime.fromisoformat(last_sent_time)
        except Exception as e:
            print("解析 lastSentTime 失敗：", e)
            last_sent_date = now - datetime.timedelta(minutes=9999)
        time_diff = (now - last_sent_date).total_seconds() / 60  # 轉換為分鐘

        # 如果小於 120 分鐘 ，則不發送
        # 注意：原程式判斷條件為 timeDiff <= 0.02，雖然註解寫「過去 2 小時內」
        if time_diff <= 0.02:
            print("過去 2 小時內已發送過警報，不重複發送")
            return

    warning_messages = []

    # 取得並解析天氣警報資料
    try:
        response = requests.get(weather_url)
        weather_data = response.json()

        if (weather_data.get("success") == "true" and
            weather_data.get("records") and
            weather_data["records"].get("record")):
            records = weather_data["records"]["record"]

            for record in records:
                # 檢查是否有 hazard 資料
                hazard_conditions = record.get("hazardConditions")
                if (hazard_conditions and
                    hazard_conditions.get("hazards") and
                    hazard_conditions["hazards"].get("hazard")):
                    hazards = hazard_conditions["hazards"]["hazard"]
                    for hazard in hazards:
                        phenomenon = hazard["info"]["phenomena"]
                        content_text = record["contents"]["content"]["contentText"].strip()
                        # 若沒有 affectedAreas.location 則預設為空陣列
                        locations = []
                        if hazard["info"].get("affectedAreas") and hazard["info"]["affectedAreas"].get("location"):
                            locations = [loc.get("locationName", "") for loc in hazard["info"]["affectedAreas"]["location"]]
                        message_text = (f"⚠️ 最新{phenomenon}特報 ⚠️\n{content_text}\n\n"
                                        f"📍 {phenomenon}特報地區：\n" + "\n".join(locations))
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
    messages = [{"type": "text", "text": text} for text in warning_messages]

    if warning_image_url:
        messages.append({
            "type": "image",
            "originalContentUrl": "https://www.cwa.gov.tw/Data/warning/W26_C.png?",
            "previewImageUrl": "https://www.cwa.gov.tw/Data/warning/W26_C.png?"
        })

    # 加入圖片訊息（如果有找到圖片）
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

    # 記錄發送時間
    script_properties.set_property("lastSentTime", now.isoformat())

    # 發送 LINE 訊息
    sendLineMessage(message_payload)

    sendBroadcastMessage_maximum_accumulated_rainfall()




# --------------------------
# 發送 LINE 訊息的共用函式
# 這個函式負責構建訊息並發送到 LINE 的群組。
# @param payload 要發送的訊息內容
# --------------------------
# def sendLineMessage(payload):
#     # 設定發送 HTTP 請求的參數
#     headers = {
#         "Content-Type": "application/json",  # 設定為 JSON 格式
#         "Authorization": "Bearer " + CHANNEL_ACCESS_TOKEN  # 授權使用 Channel Access Token
#     }

#     try:
#         # 使用 requests 發送 POST 請求到 LINE API
#         response = requests.post(LINE_PUSH_URL, headers=headers, json=payload)
#         if response.status_code == 200:
#             print("LINE 訊息發送成功")
#         else:
#             print("LINE 訊息發送失敗，狀態碼：", response.status_code, response.text)
#     except Exception as error:
#         print("LINE 訊息發送失敗：", error)


# --------------------------
# 以下為被註解掉的測試用 log 版本，原本是不會發送 LINE 訊息，只是記錄訊息內容
# --------------------------
def sendLineMessage(payload):
    # 遍歷所有訊息，記錄內容
    for message in payload.get("messages", []):
        if message.get("type") == "text":
            print("[訊息內容] " + message.get("text", ""))
        elif message.get("type") == "image":
            print("[圖片網址] " + message.get("originalContentUrl", ""))


# --------------------------
# 發送各縣市最高累積雨量資訊
# 該函式查詢並發送當前各縣市的降雨量資訊。
# --------------------------
def sendBroadcastMessage_maximum_accumulated_rainfall():
    weather_url = ('https://opendata.cwa.gov.tw/api/v1/rest/datastore/W-C0033-001'
                   '?Authorization=CWA-BAD98D16-5AC9-46D7-80AB-F96CB1286F16'
                   '&phenomena=%E5%A4%A7%E9%9B%A8,%E8%B1%AA%E9%9B%A8,'
                   '%E5%A4%A7%E8%B1%AA%E9%9B%A8,%E8%B6%85%E5%A4%A7%E8%B1%AA%E9%9B%A8')
    rainfall_url = ('https://opendata.cwa.gov.tw/api/v1/rest/datastore/O-A0002-001'
                    '?Authorization=CWA-BAD98D16-5AC9-46D7-80AB-F96CB1286F16'
                    '&RainfallElement=Past1hr,Past3hr,Past24hr'
                    '&GeoInfo=CountyName,TownName')

    # 收集有警報的縣市
    alert_counties = set()

    try:
        response = requests.get(weather_url)
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
        return

    # 如果沒有警報縣市，則不發送任何訊息
    if len(alert_counties) == 0:
        print("沒有符合條件的警報，不執行任何操作")
        return

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
                    # 轉為數值型態，避免非數值情況
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

                    # 如果該縣尚未記錄或 24 小時降雨量更高則更新
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
        return

    # 建構報告訊息
    report_messages = []
    for station_data in highest_rainfall_stations.values():
        report_messages.append(f"{station_data['county']} {station_data['town']} {station_data['station']} "
                               f"{station_data['past1hr']}mm {station_data['past3hr']}mm {station_data['past24hr']}mm")

    # 若沒有報告的雨量數據，則不發送任何訊息
    if len(report_messages) == 0:
        print("沒有可報告的雨量數據")
        return

    # 先發送前置訊息
    header_payload = {
        "to": GROUP_ID,
        "messages": [
            {
                "type": "text",
                "text": "當地1小時/3小時/24小時累積雨量"
            }
        ]
    }
    sendLineMessage(header_payload)

    # 分批發送其他報告訊息，避免超過最大訊息數
    max_messages_per_push = 4  # 4 + 1 前置訊息剛好 5 則
    for i in range(0, len(report_messages), max_messages_per_push):
        batch = report_messages[i:i+max_messages_per_push]
        payload = {
            "to": GROUP_ID,
            "messages": [{"type": "text", "text": text} for text in batch]
        }
        sendLineMessage(payload)  # 發送每一批報告訊息


# --------------------------
# 主程式進入點
# --------------------------
if __name__ == '__main__':
    # 可依需求執行 sendBroadcastMessage() 來啟動整個流程
    sendBroadcastMessage()
