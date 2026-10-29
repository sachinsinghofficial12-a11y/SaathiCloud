import os
import requests
from flask import Flask, request, jsonify
from datetime import datetime

app = Flask(__name__)

GEMINI_API_KEY = "AQ.Ab8RN6JDq6Lshk4fdZaD6DP3Qc9RJ5K3PcUFHG9rTr1j4-OlfQ"

@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "Saathi Cloud Smart Brain AI is Active!"})

@app.route("/command", methods=["POST"])
def handle_command():
    data = request.json or {}
    command = data.get("command", "").strip().lower()

    if not command:
        return jsonify({"reply": "Kuch toh boliye Sir!"})

    # --- 1. DIRECT SYSTEM HANDLERS (Fast & Guaranteed) ---
    if any(w in command for w in ["time", "samay", "kitne baje"]):
        return jsonify({"reply": f"Abhi samay {datetime.now().strftime('%I:%M %p')} ho raha hai Sir."})

    if any(w in command for w in ["date", "tareekh", "din", "aaj ki date", "kon sa hai"]):
        return jsonify({"reply": f"Aaj ki tareekh {datetime.now().strftime('%d %B %Y')} hai Sir."})

    # --- 2. DIRECT GEMINI REST API (No SDK Version Errors) ---
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
        
        prompt_text = (
            "Tum Saathi ho — Aakash Sir ke personal, extremely loyal, ultra-smart AI assistant. "
            "Hamesha friendly, respectful aur short Hinglish mein jawab do. "
            f"User Query: {command}"
        )

        payload = {
            "contents": [{
                "parts": [{"text": prompt_text}]
            }]
        }

        response = requests.post(url, json=payload, timeout=10)
        res_data = response.json()

        if "candidates" in res_data and len(res_data["candidates"]) > 0:
            reply = res_data["candidates"][0]["content"]["parts"][0]["text"].strip()
        else:
            reply = "Sir, abhi reply process karne mein dikkat ho rahi hai."

    except Exception as e:
        reply = f"Error aa gaya Sir: {str(e)}"

    return jsonify({"reply": reply})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
