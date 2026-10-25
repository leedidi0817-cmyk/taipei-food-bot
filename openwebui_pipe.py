"""
title: Taipei Restaurant Recommendation Pipe
author: Taipei Food Bot
version: 2.0.0
description: 全台北市美食餐廳推薦系統 Pipe (API 串接版)
"""

import re
import requests
from typing import List, Union, Generator, Iterator

class Pipe:
    def __init__(self):
        # 如果 Open WebUI 是用 Docker 執行的，請將 127.0.0.1 改為 host.docker.internal
        self.api_url = "http://host.docker.internal:5000/recommend"
        # 若 Open WebUI 是直接在本機 (非 Docker) 執行，請改用以下網址：
        # self.api_url = "http://127.0.0.1:5000/recommend"

        self.districts = [
            "大安區", "信義區", "中山區", "中正區", "萬華區", "松山區",
            "士林區", "北投區", "內湖區", "南港區", "文山區", "大同區"
        ]
        
        self.categories = [
            "火鍋", "燒肉", "日式料理", "拉麵", "義式料理", "平價小吃",
            "中式餐廳", "小籠包", "美式餐廳", "早午餐", "韓式料理", "泰式料理", "酒吧", "甜點"
        ]

    def parse_user_query(self, text: str):
        district = None
        category = None
        budget = None
        party_size = None

        for d in self.districts:
            if d in text or d.replace("區", "") in text:
                district = d
                break

        for c in self.categories:
            if c in text:
                category = c
                break

        party_match = re.search(r'(\d+)\s*(?:人|位)', text)
        if party_match:
            party_size = int(party_match.group(1))

        budget_match = re.search(r'(\d+)\s*(?:元|塊|以內|預算)', text)
        if budget_match:
            budget = int(budget_match.group(1))

        return district, category, party_size, budget

    def pipe(self, body: dict) -> Union[str, Generator, Iterator]:
        messages = body.get("messages", [])
        if not messages:
            return "無有效的對話訊息。"

        user_message = messages[-1].get("content", "")

        # 1. 解析用戶條件
        district, category, party_size, budget = self.parse_user_query(user_message)

        # 2. 發送 POST 請求給 Flask API
        payload = {
            "district": district,
            "category": category,
            "party_size": party_size,
            "budget": budget
        }

        try:
            response = requests.post(self.api_url, json=payload, timeout=5)
            if response.status_code == 200:
                return response.json().get("result", "沒有取得有效的推薦結果。")
            else:
                return f"❌ API 回應異常 (HTTP {response.status_code})"
        except Exception as e:
            # 若 host.docker.internal 連不上，嘗試降級連線 127.0.0.1
            try:
                alt_url = "http://127.0.0.1:5000/recommend"
                response = requests.post(alt_url, json=payload, timeout=5)
                return response.json().get("result", "沒有取得有效的推薦結果。")
            except Exception:
                return f"❌ 無法連線至本機推薦 API 服務，請確認 `python api.py` 是否已啟動。\n錯誤訊息: {e}"