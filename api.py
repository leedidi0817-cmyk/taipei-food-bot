import os
import sys
from flask import Flask, request, jsonify

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
from recommender import search_restaurants, format_results, to_records

app = Flask(__name__)


@app.route('/recommend', methods=['POST'])
def recommend():
    data = request.json or {}
    results, error = search_restaurants(
        district=data.get('district'),
        category=data.get('category'),
        party_size=data.get('party_size'),
        budget=data.get('budget'),
    )
    if error:
        return jsonify({"result": error, "restaurants": []})
    # result：顯示用文字；restaurants：結構化資料，給 LLM 寫推薦理由
    return jsonify({"result": format_results(results), "restaurants": to_records(results)})


if __name__ == '__main__':
    app.run(port=5000)
