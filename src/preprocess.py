import os
import pandas as pd

def preprocess_data():
    raw_path = "data/raw_restaurants.csv"
    output_path = "data/processed_restaurants.csv"

    # 1. 檢查原始資料檔是否存在
    if not os.path.exists(raw_path):
        print(f"❌ 找不到 {raw_path}，請先執行 python src/collector.py！")
        return

    # 2. 載入資料
    df = pd.read_csv(raw_path)

    # 3. 補齊欄位與型態轉換
    df['min_price'] = df['min_price'].fillna(200).astype(int)
    df['max_price'] = df['max_price'].fillna(1000).astype(int)
    df['min_party'] = df['min_party'].fillna(1).astype(int)
    df['max_party'] = df['max_party'].fillna(10).astype(int)
    df['rating'] = df['rating'].fillna(4.0).astype(float)
    df['category'] = df['category'].fillna("綜合餐飲")

    # 4. 建立綜合檢索標籤 (方便後續比對)
    df['tags'] = df['name'] + " " + df['category'] + " " + df['address']

    # 5. 儲存預處理完成的資料集
    df.to_csv(output_path, index=False, encoding="utf-8-sig")
    print(f"✅ 階段 2 完成！預處理資料已儲存至：{output_path}")

if __name__ == "__main__":
    preprocess_data()