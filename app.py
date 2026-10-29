import os
import requests
from bs4 import BeautifulSoup
from flask import Flask, request, jsonify
import google.generativeai as genai
from datetime import datetime

app = Flask(__name__)

GEMINI_API_KEY = "AQ.Ab8RN6JDq6Lshk4fdZaD6DP3Qc9RJ5K3PcUFHG9rTr1j4-OlfQ"
genai.configure(api_key=GEMINI_API_KEY)

model = genai.GenerativeModel("gemini-1.5-flash")

@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "Saathi Web Scanning Brain AI is Active!"})

@app.route("/command", methods=["POST"])
def handle_command():
    data = request.json or {}
    command = data.get("command", "").strip().lower()

    if not command:
        return jsonify({"reply": "Kuch toh boliye Sir!"})

    # --- FAST LOCAL SYSTEM HANDLERS ---
    if any(w in command for w in ["time", "samay", "kitne baje"]):
        return jsonify({"reply": f"Abhi samay {datetime.now().strftime('%I:%M %p')} ho raha hai Sir."})

    if any(w in command for w in ["date", "tareekh", "din", "aaj ki date", "kon sa hai"]):
        return jsonify({"reply": f"Aaj ki tareekh {datetime.now().strftime('%d %B %Y')} hai Sir."})

    # --- WEB SCANNING & READING FEATURE ---
    scraped_text = ""
    if "padho" in command or "scan karo" in command or "http" in command:
        try:
            # Agar user ne URL diya ho toh extract karein
            words = command.split()
            url = next((w for w in words if w.startswith("http")), None)
            
            if url:
                headers = {"User-Agent": "Mozilla/5.0"}
                page = requests.get(url, headers=headers, timeout=5)
                soup = BeautifulSoup(page.text, 'html.parser')
                
                # Page ka main text nikalna
                paragraphs = soup.find_all(['p', 'h1', 'h2'])
                scraped_text = " ".join([p.get_text() for p in paragraphs[:10]])[:3000] # Limit data size
                command = f"Is web content ko padh kar summary do: {scraped_text}"
        except Exception as e:
            scraped_text = f"Web scan nahi ho paya: {str(e)}"

    # --- GEMINI AI CLOUD BRAIN ---
    try:
        system_prompt = (
            "Tum Saathi ho — Aakash Sir ke personal, extremely loyal, ultra-smart AI assistant. "
            "Hamesha friendly, respectful aur detailed Hinglish mein jawab do jaise ek expert AI deta hai. "
            f"User Query: {command}"
        )
        response = model.generate_content(system_prompt)
        reply = response.text.strip()
    except Exception as e:
        reply = f"Error aa gaya Sir: {str(e)}"

    return jsonify({"reply": reply})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
