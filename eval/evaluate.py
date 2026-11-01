"""
成效評估腳本
1. 條件解析準確率：比較舊版 / 新版（之後可加入 LLM 版）的解析結果
2. 排序品質：比較舊版（只看評分）與新版（加權推薦指數）的前 5 名
執行：python eval/evaluate.py
"""
import os
import re
import sys

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "src"))

from openwebui_pipe import Pipe            # noqa: E402
from recommender import DF_PATH, compute_scores  # noqa: E402

FIELDS = ["district", "category", "party_size", "budget"]


class OldPipe(Pipe):
    """原始版本的預算解析（只認「數字+元/塊/以內」）"""
    def parse_user_query(self, text):
        district, category, party_size, _ = super().parse_user_query(text)
        budget = None
        m = re.search(r'(\d+)\s*(?:元|塊|以內|預算)', text)
        if m:
            budget = int(m.group(1))
        return district, category, party_size, budget


def norm(v):
    if v is None or (isinstance(v, float) and pd.isna(v)) or v == "":
        return None
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return str(v)


def eval_parser(name, parser, tests):
    rows = []
    for _, t in tests.iterrows():
        got = dict(zip(FIELDS, parser.parse_user_query(t["query"])))
        hits = {f: norm(got[f]) == norm(t[f]) for f in FIELDS}
        rows.append({"query": t["query"], "type": t["type"], **{f"{f}_ok": hits[f] for f in FIELDS},
                     "all_ok": all(hits.values()), **{f"got_{f}": got[f] for f in FIELDS}})
    df = pd.DataFrame(rows)
    print(f"\n【{name}】條件解析準確率")
    for f in FIELDS:
        print(f"  {f:<11} {df[f + '_ok'].mean():.0%}")
    for typ, g in df.groupby("type"):
        print(f"  整句全對（{typ}） {g['all_ok'].mean():.0%}  ({g['all_ok'].sum()}/{len(g)})")
    print(f"  整句全對（全部） {df['all_ok'].mean():.0%}  ({df['all_ok'].sum()}/{len(df)})")
    return df


def eval_ranking():
    data = pd.read_csv(DF_PATH)
    combos = data.groupby(["district", "category"]).size()
    combos = combos[combos >= 10].index
    stats = {"舊版（只看評分）": [], "新版（加權推薦指數）": []}
    for d, c in combos:
        df = data[(data.district == d) & (data.category == c)].copy()
        old = df.sort_values(["rating", "user_ratings_total"], ascending=False).head(5)
        df["score"] = compute_scores(df)
        new = df.sort_values("score", ascending=False).head(5)
        for k, top in (("舊版（只看評分）", old), ("新版（加權推薦指數）", new)):
            stats[k].append({
                "median_reviews": top.user_ratings_total.median(),
                "low_review_share": (top.user_ratings_total < 200).mean(),
                "avg_rating": top.rating.mean(),
            })
    print(f"\n【排序品質】共 {len(combos)} 組「行政區 × 類別」，各取前 5 名")
    print(f"  {'版本':<14}{'前5名評論數中位數':>14}{'評論<200則的比例':>16}{'平均評分':>10}")
    for k, v in stats.items():
        s = pd.DataFrame(v)
        print(f"  {k:<14}{s.median_reviews.mean():>14.0f}{s.low_review_share.mean():>16.0%}{s.avg_rating.mean():>10.2f}")


if __name__ == "__main__":
    tests = pd.read_csv(os.path.join(ROOT, "eval", "test_queries.csv"), dtype=str)
    eval_parser("舊版解析", OldPipe(), tests)
    new = eval_parser("目前版本解析", Pipe(), tests)
    out = os.path.join(ROOT, "eval", "parser_results.csv")
    new.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"\n逐句結果已存到 {out}")
    eval_ranking()
