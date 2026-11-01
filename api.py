import os
import sys
from flask import Flask, request, jsonify

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
from recommender import filter_restaurants

app = Flask(__name__)

@app.route('/recommend', methods=['POST'])
def recommend():
    data = request.json or {}
    district = data.get('district')
    category = data.get('category')
    party_size = data.get('party_size')
    budget = data.get('budget')
    
    result = filter_restaurants(
        district=district, 
        category=category, 
        party_size=party_size, 
        budget=budget
    )
    return jsonify({"result": result})

if __name__ == '__main__':
    app.run(port=5000)