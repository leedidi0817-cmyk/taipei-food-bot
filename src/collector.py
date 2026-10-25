import os
import json
import requests
import pandas as pd

def fetch_taipei_open_data():
    """從政府開放資料平台取得臺北市餐飲店家基礎資料"""
    url = "https://data.taipei/api/v1/dataset/12837367-9d7a-426b-801a-cb3239e9921f?scope=resourceAquire&limit=100"
    
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        results = data['result']['results']
        
        restaurants = []
        for item in results:
            restaurants.append({
                "id": item.get("_id"),
                "name": item.get("Display_Name", item.get("Title", "未知餐廳")),
                "address": item.get("Address", "臺北市"),
                "lat": float(item.get("Latitude", 25.0330)) if item.get("Latitude") else 25.0330,
                "lng": float(item.get("Longitude", 121.5654)) if item.get("Longitude") else 121.5654,
                "category": item.get("Category", "綜合餐飲")
            })
        return pd.DataFrame(restaurants)
    except Exception as e:
        print(f"開放資料抓取失敗或網路連線問題，改用基礎模擬資料庫: {e}")
        return generate_mock_data()

def generate_mock_data():
    """提供包含預算與人數屬性的標準台北餐廳資料庫"""
    mock_data = [
        {"id": "R001", "name": "鼎泰豐 信義店", "address": "臺北市大安區信義路二段194號", "lat": 25.0334, "lng": 121.5298, "category": "中式/小籠包", "min_price": 400, "max_price": 800, "min_party": 1, "max_party": 10, "rating": 4.7},
        {"id": "R002", "name": "馬辣頂級麻辣鴛鴦火鍋 公館店", "address": "臺北市中正區汀州路三段295號", "lat": 25.0152, "lng": 121.5331, "category": "火鍋/吃到飽", "min_price": 700, "max_price": 1000, "min_party": 2, "max_party": 12, "rating": 4.4},
        {"id": "R003", "name": "薩莉亞 西門店", "address": "臺北市萬華區峨嵋街37號", "lat": 25.0432, "lng": 121.5073, "category": "義式/平價", "min_price": 150, "max_price": 350, "min_party": 1, "max_party": 6, "rating": 4.1},
        {"id": "R004", "name": "屋馬燒肉 台北模擬店", "address": "臺北市中山區南京東路二段", "lat": 25.0521, "lng": 121.5330, "category": "燒肉/聚餐", "min_price": 800, "max_price": 1800, "min_party": 2, "max_party": 8, "rating": 4.6},
        {"id": "R005", "name": "一蘭拉麵 台北本店", "address": "臺北市信義區松仁路97號", "lat": 25.0352, "lng": 121.5681, "category": "日式/拉麵", "min_price": 300, "max_price": 500, "min_party": 1, "max_party": 2, "rating": 4.5},
        {"id": "R006", "name": "橘色涮涮屋 ㄧ館", "address": "臺北市大安區大安路一段135號", "lat": 25.0411, "lng": 121.5472, "category": "火鍋/高檔", "min_price": 1200, "max_price": 3000, "min_party": 2, "max_party": 8, "rating": 4.8}
    ]
    return pd.DataFrame(mock_data)

if __name__ == "__main__":
    # 確保 data 資料夾存在
    os.makedirs("data", exist_ok=True)
    
    df = fetch_taipei_open_data()
    
    # 補齊必要推薦屬性
    if "min_price" not in df.columns:
        df["min_price"] = 200
        df["max_price"] = 800
        df["min_party"] = 1
        df["max_party"] = 8
        df["rating"] = 4.2
    
    # 儲存 CSV 檔案至 data 目錄下
    output_path = "data/raw_restaurants.csv"
    df.to_csv(output_path, index=False, encoding="utf-8-sig")
    print(f"✅ 成功產出資料集！檔案已儲存至：{output_path}")