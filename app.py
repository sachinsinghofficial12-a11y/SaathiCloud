import os
from flask import Flask, request, jsonify
import google.generativeai as genai
from datetime import datetime

app = Flask(__name__)

# Gemini API Key setup
GEMINI_API_KEY = "AQ.Ab8RN6JDq6Lshk4fdZaD6DP3Qc9RJ5K3PcUFHG9rTr1j4-OlfQ"
genai.configure(api_key=GEMINI_API_KEY)

# Automatic Model Fallback Loader
def get_working_model():
    models_to_try = ["gemini-1.5-flash-latest", "gemini-1.5-pro-latest", "gemini-1.0-pro"]
    for m in models_to_try:
        try:
            return genai.GenerativeModel(m)
        except Exception:
            continue
    return genai.GenerativeModel("gemini-1.5-flash-latest")

model = get_working_model()

@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "Saathi Cloud Smart Brain AI is Active!"})

@app.route("/command", methods=["POST"])
def handle_command():
    data = request.json or {}
    command = data.get("command", "").strip().lower()

    if not command:
        return jsonify({"reply": "Kuch toh boliye Sir!"})

    # --- 1. LOCAL / SYSTEM FAST HANDLERS (Kal ke code se inspired) ---
    if any(w in command for w in ["time", "samay", "kitne baje"]):
        return jsonify({"reply": f"Abhi samay {datetime.now().strftime('%I:%M %p')} ho raha hai Sir."})

    if any(w in command for w in ["date", "tareekh", "din", "aaj ki date"]):
        return jsonify({"reply": f"Aaj ki tareekh {datetime.now().strftime('%d %B %Y')} hai Sir."})

    # --- 2. CLOUD SMART AI BRAIN (Fallback System) ---
    try:
        system_prompt = (
            "Tum Saathi ho — Aakash Sir ke personal, extremely loyal, ultra-smart AI assistant. "
            "Hamesha friendly, respectful aur concise Hinglish mein jawab do. "
            f"User Query: {command}"
        )
        response = model.generate_content(system_prompt)
        reply = response.text.strip()
    except Exception as e:
        reply = f"Haan Sir, bataiye kya madad karoon? (AI Cloud Error: {str(e)})"

    return jsonify({"reply": reply})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
