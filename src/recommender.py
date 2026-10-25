import os
import pandas as pd

# 資料庫路徑
DF_PATH = "data/taipei_all_restaurants.csv"

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
        return "⚠️️ 沒有找到完全符合條件的餐廳，建議放寬預算或地區條件！"

    # 5. 依評分與評論數排序
    df = df.sort_values(by=['rating', 'user_ratings_total'], ascending=[False, False])

    results = df.head(top_n)

    output = []
    for idx, row in results.iterrows():
        output.append(
            f"📍 **{row['name']}** ({row['district']} - {row['category']})\n"
            f"⭐ 評分: {row['rating']} ({row['user_ratings_total']} 則評論)\n"
            f"💰 約略預算: ${row['min_price']} - ${row['max_price']} / 人\n"
            f"🏠 地址: {row['address']}\n"
        )

    return "\n---\n".join(output)

if __name__ == "__main__":
    print("🧪 測試篩選結果（大安區、燒肉、2人、預算 1000 元）：\n")
    print(filter_restaurants(district="大安區", category="燒肉", party_size=2, budget=1000))