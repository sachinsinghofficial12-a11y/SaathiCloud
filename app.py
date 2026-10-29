import os
from flask import Flask, request, jsonify
from datetime import datetime
from groq import Groq

app = Flask(__name__)

# Aapki Groq API key
GROQ_API_KEY = "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"
client = Groq(api_key=GROQ_API_KEY)

@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "Saathi Cloud AI Active!"})

@app.route("/command", methods=["POST"])
def handle_command():
    data = request.json or {}
    command = data.get("command", "").strip().lower()

    if not command:
        return jsonify({"reply": "Kuch toh boliye Sir!"})

    # --- LOCAL SYSTEM HANDLERS ---
    if any(w in command for w in ["time", "samay", "kitne baje"]):
        return jsonify({"reply": f"Abhi samay {datetime.now().strftime('%I:%M %p')} ho raha hai Sir."})

    if any(w in command for w in ["date", "tareekh", "din", "aaj ki date"]):
        return jsonify({"reply": f"Aaj ki tareekh {datetime.now().strftime('%d %B %Y')} hai Sir."})

    # --- GROQ AI BACKEND ---
    try:
        response = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "Tum Saathi ho — Aakash Sir ke personal, extremely loyal, ultra-smart AI assistant. Hamesha friendly, respectful aur short Hinglish mein jawab do."
                },
                {
                    "role": "user",
                    "content": command,
                }
            ],
            model="llama3-70b-8192",
        )
        reply = response.choices[0].message.content.strip()
    except Exception as e:
        reply = f"Error aa gaya Sir: {str(e)}"

    return jsonify({"reply": reply})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
