import os
import time
import googlemaps
import pandas as pd

# ==========================================
# 1. 設定你的 Google Places API Key
# ==========================================
API_KEY = "AIzaSyCZNaua5C_0kjV9R5hzqjvb3ML3FAyg124"  # 👈 請在此處替換成你剛剛複製的 API 金鑰

gmaps = googlemaps.Client(key=API_KEY)

# 台北市 12 個行政區
DISTRICTS = [
    "大安區", "信義區", "中山區", "中正區", "萬華區", "松山區",
    "士林區", "北投區", "內湖區", "南港區", "文山區", "大同區"
]

# 採集的熱門料理關鍵字/類型
CATEGORIES = [
    "火鍋", "燒肉", "日式料理", "拉麵", "義式料理", "平價小吃",
    "中式餐廳", "小籠包", "美式餐廳", "早午餐", "韓式料理", "泰式料理", "酒吧", "甜點"
]

# Google Price Level (0~4) 轉換為約略的單人消費金額上限與下限 (台幣)
PRICE_LEVEL_MAP = {
    0: (50, 150),    # 免費/極平價
    1: (100, 300),   # 平價 ($)
    2: (300, 700),   # 中等 ($$)     3: (700, 1500),  # 中高價 ($$$)     4: (1500, 3000)  # 高檔 ($$$$)
}

def crawl_restaurants():
    all_restaurants = []
    seen_place_ids = set()  # 用來避免重複抓取同一家餐廳

    print("🚀 開始採集台北市餐廳資料...")

    for district in DISTRICTS:
        for category in CATEGORIES:
            query = f"台北市 {district} {category}"
            print(f"🔍 正在搜尋：{query} ...")

            try:
                # 呼叫 Places API 文字搜尋
                response = gmaps.places(query=query, language="zh-TW")
                results = response.get("results", [])

                for place in results:
                    place_id = place.get("place_id")
                    
                    # 判斷是否重複抓取
                    if place_id in seen_place_ids:
                        continue
                    
                    # 確保營業狀態為營運中
                    if place.get("business_status") != "OPERATIONAL":
                        continue

                    seen_place_ids.add(place_id)

                    # 解析 Google 價位等級 (若沒有紀錄預設為 2)
                    price_level = place.get("price_level", 2)
                    min_price, max_price = PRICE_LEVEL_MAP.get(price_level, (300, 700))

                    # 整理資料欄位
                    restaurant_info = {
                        "place_id": place_id,
                        "name": place.get("name"),
                        "district": district,
                        "category": category,
                        "min_price": min_price,
                        "max_price": max_price,
                        "min_party": 1,     # 預設人數極限
                        "max_party": 10,    # 預設人數極限
                        "rating": place.get("rating", 4.0),
                        "user_ratings_total": place.get("user_ratings_total", 0),
                        "address": place.get("formatted_address", ""),
                        "lat": place.get("geometry", {}).get("location", {}).get("lat"),
                        "lng": place.get("geometry", {}).get("location", {}).get("lng")
                    }
                    all_restaurants.append(restaurant_info)

                # 遵守 API 間隔
                time.sleep(1)

            except Exception as e:
                print(f"❌ 搜尋 {query} 時發生錯誤: {e}")

    print(f"✅ 採集完成！共收集到 {len(all_restaurants)} 筆獨立餐廳資料。")
    return all_restaurants

if __name__ == "__main__":
    # 建立 data 資料夾（如果不存在）
    os.makedirs("data", exist_ok=True)

    # 執行採集
    data = crawl_restaurants()

    # 轉為 DataFrame 並導出 CSV
    df = pd.DataFrame(data)
    csv_output_path = "data/taipei_all_restaurants.csv"
    df.to_csv(csv_output_path, index=False, encoding="utf-8-sig")

    print(f"🎉 資料已成功儲存至 `{csv_output_path}`！")