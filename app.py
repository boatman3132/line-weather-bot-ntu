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

# --------------------------
# 定義共用常數
# --------------------------

# DS4xuDmTEm1JdSjB4nicpJSCWEFfkoK71AgNDslimzElHInP/irAjQ0RjeBzZuZ4kk3cZrOyQGYMMA5wnKoML0N+0L9SZSWt3Kuv+1e4QD4c9LuJahduzJ44VGu1wPbbKL6zBe9M7TiCA7nPzJqOxQdB04t89/1O/w1cDnyilFU= 新的line帳號
# m7mL7uj+S4utCL4fzeHcz7YebNzUWoncm+jsEcFoqXa3UzEmlgTLaRFyFEshKi6XJeXCth/v4Zj1vGpPxPAPVvSFky7hvMPDncXsmPdnrNgQEjqP4nbixNPeRuXdkY4hKQeQnx9quTC22aDkuIkCTwdB04t89/1O/w1cDnyilFU= 舊的line帳號

CHANNEL_ACCESS_TOKEN = "DS4xuDmTEm1JdSjB4nicpJSCWEFfkoK71AgNDslimzElHInP/irAjQ0RjeBzZuZ4kk3cZrOyQGYMMA5wnKoML0N+0L9SZSWt3Kuv+1e4QD4c9LuJahduzJ44VGu1wPbbKL6zBe9M7TiCA7nPzJqOxQdB04t89/1O/w1cDnyilFU="

# 測試群組id C1744d43a6e011fb9e2819c43974ead95
# 正式群組id C538d8773e17d6697fac0175c4077fd73

GROUP_ID = "C538d8773e17d6697fac0175c4077fd73"


LINE_PUSH_URL = 'https://api.line.me/v2/bot/message/push'
weather_url = ('https://opendata.cwa.gov.tw/api/v1/rest/datastore/W-C0033-002'
                '?Authorization=CWA-BAD98D16-5AC9-46D7-80AB-F96CB1286F16'
                '&phenomena=%E5%A4%A7%E9%9B%A8,%E8%B1%AA%E9%9B%A8,'
                '%E5%A4%A7%E8%B1%AA%E9%9B%A8,%E8%B6%85%E5%A4%A7%E8%B1%AA%E9%9B%A8')



# --------------------------
# 定義 ScriptProperties 類別
# 這個類別負責讀取、寫入 script_properties.json 檔案
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


def get_weather_metadata():
    """
    獲取天氣 API 的元數據，包括：
    - startTime: 警報開始時間
    - endTime: 警報結束時間
    - update: 最新更新時間
    - affectedLocations: 受影響的地區（列表）

    回傳:
    - dict: 包含以上數據的字典，如果發生錯誤則回傳 None
    """
    try:
        response = requests.get(weather_url)
        weather_data = response.json()

        if (weather_data.get("success") == "true" and
            weather_data.get("records") and
            weather_data["records"].get("record")):
            records = weather_data["records"]["record"]

            affected_locations = set()
            last_start_time = None
            last_end_time = None
            last_update_time = None

            for record in records:
                dataset_info = record.get("datasetInfo", {})
                last_start_time = dataset_info.get("validTime", {}).get("startTime")
                last_end_time = dataset_info.get("validTime", {}).get("endTime")
                last_update_time = dataset_info.get("update")

                hazard_conditions = record.get("hazardConditions", {})
                if (hazard_conditions and
                    hazard_conditions.get("hazards") and
                    hazard_conditions["hazards"].get("hazard")):
                    hazards = hazard_conditions["hazards"]["hazard"]
                    for hazard in hazards:
                        if hazard["info"].get("affectedAreas") and hazard["info"]["affectedAreas"].get("location"):
                            locations = [loc.get("locationName", "") for loc in hazard["info"]["affectedAreas"]["location"]]
                            affected_locations.update(locations)

            return {
                "lastStartTime": last_start_time,
                "lastEndTime": last_end_time,
                "lastUpdateTime": last_update_time,
                "affectedLocations": list(affected_locations)
            }

    except Exception as error:
        print("天氣 API 請求失敗：", error)
        return None


# --------------------------
# 主函式：檢查天氣 API 資料、組合警報訊息、查找各項圖片並發送 LINE 訊息
# 這個函式將會檢查天氣資料並發送警報訊息到 LINE 群組。
# --------------------------
def sendBroadcastMessage():
    now = datetime.datetime.now() + datetime.timedelta(hours=8)

    # 讀取上次發送的資訊
    last_sent_info = script_properties.get_property("lastSentInfo")

    # 如果 last_sent_info 是字串，則轉換為字典
    if isinstance(last_sent_info, str):
        try:
            last_sent_info = json.loads(last_sent_info)  # 只有字串才執行解析
        except json.JSONDecodeError:
            print("lastSentInfo 格式錯誤，重置為空字典")
            last_sent_info = {}
    elif last_sent_info is None:
        last_sent_info = {}

    last_sent_time = last_sent_info.get("lastSentTime")

    if last_sent_time:
        try:
            # 確保讀取後轉換成 datetime 物件
            last_sent_date = datetime.datetime.strptime(last_sent_time, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            print("時間格式錯誤，重置 lastSentTime")
            last_sent_date = now - datetime.timedelta(hours=3)  # 設定為 3 小時前，避免影響判斷

        time_diff = (now - last_sent_date).total_seconds() / 60  # 轉換為分鐘
        if time_diff <= 780 :  # 5 小時內不重複發送
            print("過去 5 小時內已發送過警報，不重複發送")
            return

    # 更新 lastSentTime 並確保格式統一
    formatted_last_sent_time = now.strftime("%Y-%m-%d %H:%M:%S")
    last_sent_info.update({
        "lastSentTime": formatted_last_sent_time
    })

    script_properties.set_property("lastSentInfo", last_sent_info)

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

    # 發送 LINE 訊息
    sendLineMessage(message_payload)

    sendBroadcastMessage_maximum_accumulated_rainfall()


# --------------------------
# 發送 LINE 訊息的共用函式
# 這個函式負責構建訊息並發送到 LINE 的群組。
# @param payload 要發送的訊息內容
# --------------------------
def sendLineMessage(payload):
    # 設定發送 HTTP 請求的參數
    headers = {
        "Content-Type": "application/json",  # 設定為 JSON 格式
        "Authorization": "Bearer " + CHANNEL_ACCESS_TOKEN  # 授權使用 Channel Access Token
    }

    try:
        # 使用 requests 發送 POST 請求到 LINE API
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

    # 將所有報告訊息合併成一個字串
    combined_message = "\n".join(report_messages)

    # 建立 payload
    payload = {
        "to": GROUP_ID,
        "messages": [{"type": "text", "text": combined_message}]
    }

    # 發送合併後的訊息
    sendLineMessage(payload)

# --------------------------
# 主程式進入點
# --------------------------
if __name__ == '__main__':
    # 可依需求執行 sendBroadcastMessage() 來啟動整個流程
    sendBroadcastMessage()
