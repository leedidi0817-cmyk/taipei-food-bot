"""
台北市餐廳資料採集（Google Places API (New) 版）

使用方式：
    Windows PowerShell： $env:GOOGLE_MAPS_API_KEY="你的key"; python collector_taipei.py
    macOS / Linux：      GOOGLE_MAPS_API_KEY=你的key python collector_taipei.py

只需要 requests 和 pandas，不需要 googlemaps 套件。
"""
import os
import time

import pandas as pd
import requests

# ==========================================
# 1. API 設定（key 從環境變數讀取，不要寫進程式碼）
# ==========================================
API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY")
BASE_URL = os.environ.get("PLACES_BASE_URL", "https://places.googleapis.com/v1")
MAX_PAGES = int(os.environ.get("MAX_PAGES", "1"))  # 每個搜尋最多幾頁（每頁 20 筆，最多 3 頁）

# 只取需要的欄位，可以降低費用
FIELD_MASK = ",".join([
    "places.id",
    "places.displayName",
    "places.formattedAddress",
    "places.location",
    "places.rating",
    "places.userRatingCount",
    "places.priceLevel",
    "places.priceRange",
    "places.businessStatus",
    "nextPageToken",
])

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

# Google 價位等級轉換為約略的單人消費金額（台幣），只在沒有實際價格區間時使用
PRICE_LEVEL_MAP = {
    "PRICE_LEVEL_FREE": (50, 150),             # 免費/極平價
    "PRICE_LEVEL_INEXPENSIVE": (100, 300),     # 平價 ($)
    "PRICE_LEVEL_MODERATE": (300, 700),        # 中等 ($$)
    "PRICE_LEVEL_EXPENSIVE": (700, 1500),      # 中高價 ($$$)
    "PRICE_LEVEL_VERY_EXPENSIVE": (1500, 3000),  # 高檔 ($$$$)
}
DEFAULT_PRICE = (300, 700)


def search_text(query, page_token=None):
    """呼叫 Places API (New) 的 Text Search。"""
    body = {"textQuery": query, "languageCode": "zh-TW", "regionCode": "TW", "pageSize": 20}
    if page_token:
        body["pageToken"] = page_token
    response = requests.post(
        f"{BASE_URL}/places:searchText",
        headers={"X-Goog-Api-Key": API_KEY, "X-Goog-FieldMask": FIELD_MASK},
        json=body,
        timeout=15,
    )
    if response.status_code != 200:
        try:
            message = response.json()["error"]["message"]
        except Exception:
            message = response.text[:200]
        raise RuntimeError(f"HTTP {response.status_code}: {message}")
    return response.json()


def parse_price(place):
    """優先使用 Google 提供的實際價格區間，沒有才用價位等級估算。"""
    price_range = place.get("priceRange") or {}
    start = (price_range.get("startPrice") or {}).get("units")
    end = (price_range.get("endPrice") or {}).get("units")
    if start:
        start = int(start)
        end = int(end) if end else start * 2
        return start, end
    return PRICE_LEVEL_MAP.get(place.get("priceLevel"), DEFAULT_PRICE)


def to_row(place, district, category):
    min_price, max_price = parse_price(place)
    location = place.get("location") or {}
    return {
        "place_id": place.get("id"),
        "name": (place.get("displayName") or {}).get("text"),
        "district": district,
        "category": category,
        "min_price": min_price,
        "max_price": max_price,
        "min_party": 1,     # 預設人數極限
        "max_party": 10,    # 預設人數極限
        "rating": place.get("rating", 4.0),
        "user_ratings_total": place.get("userRatingCount", 0),
        "address": place.get("formattedAddress", ""),
        "lat": location.get("latitude"),
        "lng": location.get("longitude"),
    }


def crawl_restaurants():
    all_restaurants = []
    seen_place_ids = set()  # 避免重複抓取同一家餐廳

    print("🚀 開始採集台北市餐廳資料...")

    for district in DISTRICTS:
        for category in CATEGORIES:
            query = f"台北市 {district} {category}"
            print(f"🔍 正在搜尋：{query} ...")
            page_token = None

            for _ in range(MAX_PAGES):
                try:
                    data = search_text(query, page_token)
                except Exception as e:
                    print(f"❌ 搜尋 {query} 時發生錯誤: {e}")
                    break

                for place in data.get("places", []):
                    place_id = place.get("id")
                    if not place_id or place_id in seen_place_ids:
                        continue
                    # 確保營業狀態為營運中
                    if place.get("businessStatus", "OPERATIONAL") != "OPERATIONAL":
                        continue
                    seen_place_ids.add(place_id)
                    all_restaurants.append(to_row(place, district, category))

                page_token = data.get("nextPageToken")
                time.sleep(1)  # 遵守 API 間隔
                if not page_token:
                    break

    print(f"✅ 採集完成！共收集到 {len(all_restaurants)} 筆獨立餐廳資料。")
    return all_restaurants


if __name__ == "__main__":
    if not API_KEY:
        raise SystemExit("❌ 請先設定環境變數 GOOGLE_MAPS_API_KEY")

    os.makedirs("data", exist_ok=True)
    data = crawl_restaurants()

    # 沒抓到任何資料時不要覆蓋原本的 CSV（例如 API key 錯誤）
    if not data:
        raise SystemExit("❌ 沒有抓到任何餐廳資料，已保留原本的 CSV。請檢查 API key 是否正確。")

    df = pd.DataFrame(data)
    csv_output_path = "data/taipei_all_restaurants.csv"
    df.to_csv(csv_output_path, index=False, encoding="utf-8-sig")
    print(f"🎉 資料已成功儲存至 `{csv_output_path}`！")
