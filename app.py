import os
from flask import Flask, request, jsonify
from datetime import datetime
from groq import Groq

app = Flask(__name__)

GROQ_API_KEY = "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"
client = Groq(api_key=GROQ_API_KEY)

def get_active_model():
    """Groq API se currently supported active model fetch karta hai."""
    try:
        models = client.models.list()
        model_ids = [m.id for m in models.data]
        
        # Priority order for text models
        preferred = [
            "llama-3.3-70b-versatile",
            "llama-3.1-8b-instant",
            "llama-3.2-11b-vision-instruct",
            "mixtral-8x7b-32768"
        ]
        
        for p in preferred:
            if p in model_ids:
                return p
                
        return model_ids[0] if model_ids else "llama-3.1-8b-instant"
    except Exception:
        return "llama-3.1-8b-instant"

ACTIVE_MODEL = get_active_model()
print(f"--> Selected Active Groq Model: {ACTIVE_MODEL}")

@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "Saathi Cloud AI Active!", "model": ACTIVE_MODEL})

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
            model=ACTIVE_MODEL,
        )
        reply = response.choices[0].message.content.strip()
    except Exception as e:
        reply = f"Error aa gaya Sir: {str(e)}"

    return jsonify({"reply": reply})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
