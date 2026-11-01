"""
title: Taipei Restaurant Recommendation Pipe
author: Taipei Food Bot
version: 3.1.0
description: 全台北市美食餐廳推薦系統 Pipe（LLM 理解需求 + 加權推薦 + 推薦理由）
"""

import json
import re
from typing import Generator, Iterator, Optional, Union

import requests
from pydantic import BaseModel, Field


DISTRICTS = [
    "大安區", "信義區", "中山區", "中正區", "萬華區", "松山區",
    "士林區", "北投區", "內湖區", "南港區", "文山區", "大同區",
]

CATEGORIES = [
    "火鍋", "燒肉", "日式料理", "拉麵", "義式料理", "平價小吃",
    "中式餐廳", "小籠包", "美式餐廳", "早午餐", "韓式料理", "泰式料理", "酒吧", "甜點",
]

# 規則解析用：口語同義詞 → 標準類別
CATEGORY_SYNONYMS = {
    "火鍋": ["麻辣鍋", "涮涮鍋", "鍋物", "石頭鍋", "薑母鴨", "羊肉爐"],
    "燒肉": ["燒烤", "烤肉"],
    "日式料理": ["日本料理", "日料", "壽司", "生魚片", "丼飯", "居酒屋"],
    "拉麵": ["ramen"],
    "義式料理": ["義大利麵", "義大利菜", "披薩", "pizza", "燉飯"],
    "平價小吃": ["小吃", "夜市", "便當", "滷肉飯"],
    "中式餐廳": ["中菜", "合菜", "台菜", "熱炒", "港式", "粵菜"],
    "美式餐廳": ["漢堡", "牛排", "美式"],
    "早午餐": ["早餐", "brunch"],
    "韓式料理": ["韓國菜", "韓國料理", "韓式", "韓料"],
    "泰式料理": ["泰國菜", "泰國料理", "泰式"],
    "酒吧": ["喝酒", "調酒", "小酌", "bar"],
    "甜點": ["蛋糕", "下午茶", "甜食", "冰品"],
}

CN_DIGITS = {"零": 0, "一": 1, "二": 2, "兩": 2, "三": 3, "四": 4,
             "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
CN_UNITS = {"十": 10, "百": 100, "千": 1000}
NUM = r"(\d+(?:\.\d+)?\s*[kK]|\d+|[零一二兩三四五六七八九十百千]+)"


def to_number(token: str) -> Optional[int]:
    """把「1000」「1k」「一千」「一千五」「兩百」轉成整數。"""
    token = token.strip()
    if not token:
        return None
    if token[-1] in "kK":
        return int(float(token[:-1].strip()) * 1000)
    if token.isdigit():
        return int(token)
    total, num, last_unit = 0, 0, 1
    for ch in token:
        if ch in CN_DIGITS:
            num = CN_DIGITS[ch]
        elif ch in CN_UNITS:
            last_unit = CN_UNITS[ch]
            total += (num or 1) * last_unit
            num = 0
    if num:
        # 「一千五」= 1500、「十二」= 12
        total += num * (last_unit // 10 if last_unit >= 100 else 1)
    return total or None


PARSE_PROMPT = f"""你是台北餐廳推薦系統的「搜尋條件抽取器」。
請根據對話，找出使用者「目前」想要的搜尋條件，只輸出一個 JSON 物件，不要任何其他文字。

JSON 格式：
{{"district": 字串或 null, "category": 字串或 null, "party_size": 整數或 null, "budget": 整數或 null}}

規則：
1. district 只能是以下其中之一，或 null：{"、".join(DISTRICTS)}
   - 「大安」「信義」這類省略「區」的說法要補成完整名稱。
   - 提到地標時，只有在非常確定所屬行政區時才填（例如「士林夜市」→士林區），不確定就填 null。
2. category 只能是以下其中之一，或 null：{"、".join(CATEGORIES)}
   - 同義詞要對應：麻辣鍋/涮涮鍋→火鍋、日本料理/壽司→日式料理、韓國菜→韓式料理、
     泰國菜→泰式料理、義大利麵/披薩→義式料理、小吃/夜市→平價小吃、早餐→早午餐、
     蛋糕/下午茶→甜點、喝酒/調酒→酒吧、中菜/合菜→中式餐廳、漢堡/牛排→美式餐廳。
3. party_size 是用餐人數（整數）。「我們兩個」=2、「一個人」=1、「三個人」=3。沒提到就 null。
4. budget 是「每人」預算上限（整數，台幣）。「一千」=1000、「1k」=1000、「500以內」=500。
   如果使用者給的是總預算且有人數，換算成每人（總預算 ÷ 人數，取整數）。沒提到就 null。
5. 多輪對話：沿用先前的條件，只更新使用者這次改動的部分。
   - 「再便宜一點」：把先前的 budget 乘以 0.7 取整數；先前沒有 budget 就設為 300。
   - 「換成○○」「改○○」：只替換對應欄位。
   - 「不限地區」「哪裡都可以」：district 設為 null。
"""

REASON_PROMPT = """你是台北餐廳推薦助理。根據使用者的需求和下方的餐廳資料，用繁體中文寫一段 2~4 句的推薦說明。
規則：
- 只能使用資料中提供的資訊（名稱、評分、評論數、價格區間、推薦指數），不要編造菜色、裝潢、營業時間等資料沒有的內容。
- 點出最推薦的 1~2 家和理由（例如評論數多代表口碑穩定、價格區間符合預算）。
- 語氣自然友善，不要使用條列，不要重複列出所有餐廳的完整資料。
"""


class Pipe:
    class Valves(BaseModel):
        API_URL: str = Field(
            default="http://127.0.0.1:5000/recommend",
            description="推薦 API 網址（api.py）",
        )
        LLM_BASE_URL: str = Field(
            default="http://163.14.73.40:8088/v1",
            description="LLM 服務網址（OpenAI 相容格式，結尾是 /v1）",
        )
        LLM_API_KEY: str = Field(
            default="",
            description="LLM API Key（實驗室 .env 裡的 LLM_API_KEY）。留空則只用規則解析",
        )
        LLM_MODEL: str = Field(
            default="",
            description="模型名稱。留空會自動使用服務提供的第一個模型",
        )
        USE_LLM_PARSER: bool = Field(default=True, description="用 LLM 理解使用者需求")
        USE_LLM_REASON: bool = Field(default=True, description="用 LLM 寫推薦理由")
        SHOW_CONDITIONS: bool = Field(default=True, description="在回答開頭顯示解析出的條件")

    def __init__(self):
        self.valves = self.Valves()
        self._model_cache = None

    # ------------------------------------------------------------------
    # LLM 呼叫
    # ------------------------------------------------------------------
    def _llm_enabled(self) -> bool:
        return bool(self.valves.LLM_API_KEY and self.valves.LLM_BASE_URL)

    def _base_url(self) -> str:
        return self.valves.LLM_BASE_URL.rstrip("/")

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.valves.LLM_API_KEY}"}

    def _model(self) -> str:
        if self.valves.LLM_MODEL:
            return self.valves.LLM_MODEL
        if self._model_cache is None:
            r = requests.get(f"{self._base_url()}/models", headers=self._headers(), timeout=10)
            r.raise_for_status()
            self._model_cache = r.json()["data"][0]["id"]
        return self._model_cache

    def _chat(self, messages: list, max_tokens: int = 400) -> str:
        payload = {
            "model": self._model(),
            "messages": messages,
            "temperature": 0,
            "max_tokens": max_tokens,
            # Qwen3 系列：關閉思考模式，回應更快（不支援的伺服器會忽略）
            "chat_template_kwargs": {"enable_thinking": False},
        }
        r = requests.post(
            f"{self._base_url()}/chat/completions",
            headers=self._headers(),
            json=payload,
            timeout=60,
        )
        r.raise_for_status()
        text = r.json()["choices"][0]["message"]["content"] or ""
        # 移除可能出現的思考內容
        return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

    # ------------------------------------------------------------------
    # 條件解析：LLM 優先，失敗時退回規則
    # ------------------------------------------------------------------
    def parse_user_query(self, text: str):
        """規則解析（不需要 LLM），支援常見口語說法。"""
        district = None
        category = None
        budget = None
        party_size = None
        lower = text.lower()

        # 行政區：「大安區」或省略「區」的「大安」
        for d in DISTRICTS:
            if d in text or d.replace("區", "") in text:
                district = d
                break

        # 類別：先找標準名稱，再找同義詞（麻辣鍋→火鍋、韓國菜→韓式料理…）
        for c in CATEGORIES:
            if c in text:
                category = c
                break
        if category is None:
            for c, words in CATEGORY_SYNONYMS.items():
                if any(w.lower() in lower for w in words):
                    category = c
                    break

        # 人數：「3人」「3位」「三個人」「我們6個人」「一個人」
        party_match = re.search(NUM + r"\s*個?\s*(?:人|位)", text)
        if party_match:
            party_size = to_number(party_match.group(1))

        # 預算：「預算1000」「預算一千」「1000元」「500以內」「一人500」「每人一千」「1k」
        budget_patterns = [
            r"預算\s*" + NUM,
            r"(?:一人|每人|每位|一位)\s*" + NUM,
            NUM + r"\s*(?:元|塊|以內|以下)",
            r"(\d+(?:\.\d+)?\s*[kK])",
        ]
        for pattern in budget_patterns:
            m = re.search(pattern, text)
            if m:
                budget = to_number(m.group(1))
                break

        return district, category, party_size, budget

    def parse_with_llm(self, messages: list):
        """用 LLM 解析整段對話，回傳 (district, category, party_size, budget)。"""
        history = []
        for m in messages[-8:]:
            content = m.get("content", "")
            if isinstance(content, str) and m.get("role") in ("user", "assistant"):
                # 助理的長篇回答只保留開頭（含先前解析的條件），節省 token
                history.append({"role": m["role"], "content": content[:300]})

        raw = self._chat([{"role": "system", "content": PARSE_PROMPT}] + history, max_tokens=200)
        match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
        if not match:
            raise ValueError(f"LLM 沒有回傳 JSON：{raw[:100]}")
        data = json.loads(match.group(0))

        district = data.get("district")
        district = district if district in DISTRICTS else None
        category = data.get("category")
        category = category if category in CATEGORIES else None

        def to_int(v):
            try:
                v = int(float(v))
                return v if v > 0 else None
            except (TypeError, ValueError):
                return None

        return district, category, to_int(data.get("party_size")), to_int(data.get("budget"))

    def get_conditions(self, messages: list):
        """回傳 (條件 tuple, 解析方式)。"""
        user_message = messages[-1].get("content", "")
        if self.valves.USE_LLM_PARSER and self._llm_enabled():
            try:
                return self.parse_with_llm(messages), "LLM"
            except Exception:
                pass  # LLM 失敗時退回規則解析
        return self.parse_user_query(user_message), "規則"

    # ------------------------------------------------------------------
    # 推薦理由
    # ------------------------------------------------------------------
    def write_reason(self, user_message: str, restaurants: list) -> Optional[str]:
        if not (self.valves.USE_LLM_REASON and self._llm_enabled() and restaurants):
            return None
        try:
            data = json.dumps(restaurants, ensure_ascii=False)
            return self._chat(
                [
                    {"role": "system", "content": REASON_PROMPT},
                    {"role": "user", "content": f"使用者需求：{user_message}\n\n餐廳資料：{data}"},
                ],
                max_tokens=400,
            )
        except Exception:
            return None

    # ------------------------------------------------------------------
    # 主流程
    # ------------------------------------------------------------------
    @staticmethod
    def describe_conditions(district, category, party_size, budget, source) -> str:
        parts = [
            district or "不限地區",
            category or "不限類別",
            f"{party_size} 人" if party_size else "人數不限",
            f"每人 {budget} 元內" if budget else "預算不限",
        ]
        return f"🔎 搜尋條件：{'｜'.join(parts)}（{source}解析）"

    def pipe(self, body: dict) -> Union[str, Generator, Iterator]:
        messages = body.get("messages", [])
        if not messages:
            return "無有效的對話訊息。"

        user_message = messages[-1].get("content", "")
        if not isinstance(user_message, str):
            user_message = str(user_message)

        # 1. 解析用戶條件
        (district, category, party_size, budget), source = self.get_conditions(messages)

        # 2. 呼叫推薦 API
        payload = {
            "district": district,
            "category": category,
            "party_size": party_size,
            "budget": budget,
        }
        try:
            response = requests.post(self.valves.API_URL, json=payload, timeout=10)
            if response.status_code != 200:
                return f"❌ API 回應異常 (HTTP {response.status_code})"
            data = response.json()
        except Exception as e:
            return f"❌ 無法連線至本機推薦 API 服務，請確認 `python api.py` 是否已啟動。\n錯誤訊息: {e}"

        result = data.get("result", "沒有取得有效的推薦結果。")

        # 3. 組合回答：條件 → 推薦理由 → 餐廳清單
        sections = []
        if self.valves.SHOW_CONDITIONS:
            sections.append(self.describe_conditions(district, category, party_size, budget, source))
        reason = self.write_reason(user_message, data.get("restaurants", []))
        if reason:
            sections.append(f"💬 {reason}")
        sections.append(result)
        return "\n\n".join(sections)
