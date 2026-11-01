import os
import math
from urllib.parse import quote

import pandas as pd

# 資料庫路徑（以專案根目錄為準，從任何資料夾執行都找得到）
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DF_PATH = os.path.join(BASE_DIR, "data", "taipei_all_restaurants.csv")

# 加權評分的權重（加總為 1，可依需求調整）
W_RATING = 0.6      # 評分可信度
W_POPULARITY = 0.25  # 人氣（評論數）
W_BUDGET = 0.15     # 預算吻合度

# 貝氏平均的門檻：評論數少於這個數字時，評分會被拉向全體平均
BAYES_M = 100


def compute_scores(df, budget=None):
    """計算每家餐廳的推薦指數 (0~100)。"""
    reviews = df["user_ratings_total"].fillna(0)
    rating = df["rating"].fillna(df["rating"].mean())

    # 1. 評分可信度：貝氏平均，避免「5 則評論 4.9 分」贏過「8000 則評論 4.8 分」
    c = rating.mean()
    bayes = (reviews / (reviews + BAYES_M)) * rating + (BAYES_M / (reviews + BAYES_M)) * c
    rating_score = bayes / 5

    # 2. 人氣：評論數取 log 後正規化到 0~1
    log_reviews = reviews.apply(lambda x: math.log10(x + 1))
    max_log = log_reviews.max() or 1
    popularity_score = log_reviews / max_log

    # 3. 預算吻合度：整個價格區間都在預算內 = 1，部分在內則依比例
    if budget:
        span = (df["max_price"] - df["min_price"]).clip(lower=1)
        budget_score = ((budget - df["min_price"]) / span).clip(0, 1)
    else:
        budget_score = pd.Series(1.0, index=df.index)

    score = W_RATING * rating_score + W_POPULARITY * popularity_score + W_BUDGET * budget_score
    return (score * 100).round(1)


def maps_link(row):
    """產生 Google Maps 連結，點了直接開啟該餐廳。"""
    url = f"https://www.google.com/maps/search/?api=1&query={quote(str(row['name']))}"
    if isinstance(row.get("place_id"), str) and row["place_id"]:
        url += f"&query_place_id={row['place_id']}"
    return url


def filter_restaurants(district=None, category=None, party_size=None, budget=None, top_n=5):
    if not os.path.exists(DF_PATH):
        return f"❌ 找不到資料庫檔案：{DF_PATH}，請確認是否已執行採集腳本。"

    try:
        df = pd.read_csv(DF_PATH)
    except Exception as e:
        return f"❌ 資料庫讀取失敗: {e}"

    # 1. 行政區篩選
    if district and district != "全區":
        df = df[df['district'].str.contains(district, na=False)]

    # 2. 料理類別篩選
    if category and category != "不限":
        df = df[df['category'].str.contains(category, na=False)]

    # 3. 人數篩選
    if party_size:
        df = df[(df['min_party'] <= party_size) & (df['max_party'] >= party_size)]

    # 4. 預算篩選
    if budget:
        df = df[df['min_price'] <= budget]

    if df.empty:
        return "⚠️ 沒有找到完全符合條件的餐廳，建議放寬預算或地區條件！"

    # 5. 依加權推薦指數排序
    df = df.copy()
    df["score"] = compute_scores(df, budget)
    df = df.sort_values(by="score", ascending=False)

    results = df.head(top_n)

    output = []
    for _, row in results.iterrows():
        output.append(
            f"📍 **{row['name']}** ({row['district']} - {row['category']})\n"
            f"🏆 推薦指數: {row['score']} / 100\n"
            f"⭐ 評分: {row['rating']} ({int(row['user_ratings_total'])} 則評論)\n"
            f"💰 約略預算: ${row['min_price']} - ${row['max_price']} / 人\n"
            f"🏠 地址: {row['address']}\n"
            f"🗺️ [在 Google Maps 開啟]({maps_link(row)})\n"
        )

    return "\n---\n".join(output)


if __name__ == "__main__":
    print("🧪 測試篩選結果（大安區、燒肉、2人、預算 1000 元）：\n")
    print(filter_restaurants(district="大安區", category="燒肉", party_size=2, budget=1000))
