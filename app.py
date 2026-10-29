import os
from flask import Flask, request, jsonify
import google.generativeai as genai

app = Flask(__name__)

# Aapki Gemini API Key yahan set kar di gayi hai
GEMINI_API_KEY = "AQ.Ab8RN6JDq6Lshk4fdZaD6DP3Qc9RJ5K3PcUFHG9rTr1j4-OlfQ"
genai.configure(api_key=GEMINI_API_KEY)

# Gemini Model Setup
model = genai.GenerativeModel("gemini-1.5-flash")

@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "Saathi Cloud AI Server is Running!"})

@app.route("/command", methods=["POST"])
def handle_command():
    data = request.json
    command = data.get("command", "")
    
    if not command:
        return jsonify({"reply": "Kuch toh boliye Sir!"})

    try:
        # Prompt jisse Saathi ka Nature set hoga
        system_prompt = (
            "Aapka naam Saathi hai. Aap Aakash Sir ke personal, loyal aur highly intelligent AI assistant hain. "
            "Aap HINGLISH mein jawab dete hain. Friendly, respectful aur smart tone rakhein. "
            f"User ka message: {command}"
        )
        
        response = model.generate_content(system_prompt)
        reply = response.text.strip()
        
    except Exception as e:
        reply = f"Error aa gaya Sir: {str(e)}"

    return jsonify({"reply": reply})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
