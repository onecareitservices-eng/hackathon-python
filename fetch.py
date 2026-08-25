from flask import Flask, jsonify
import os

app = Flask(__name__)

@app.route("/")
def home():
    return "Hackathon Python API is working!"

@app.route("/api/hackathons")
def hackathons():
    data = [
        {
            "title": "Test Hackathon",
            "description": "This is a test hackathon.",
            "category": "Technology",
            "prize": "₹1,00,000",
            "source": "Test",
            "link": "https://example.com"
        }
    ]

    return jsonify(data)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
