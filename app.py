
import os
import logging
from dotenv import load_dotenv
from datetime import datetime
from zoneinfo import ZoneInfo

from flask import Flask, request, jsonify
from groq import Groq

# Local .env file se environment variables load karein
load_dotenv()

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024  # 32 KB request limit

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("saathi")

# Secrets and configuration come from environment variables
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
ACTIVE_MODEL = os.getenv(
    "GROQ_MODEL",
    "llama-3.3-70b-versatile"
)

client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

SYSTEM_PROMPT = """
Tum Saathi ho, Aakash Sir ke personal AI assistant.
Friendly, respectful aur natural Hinglish mein jawab do.
User se hamesha respect se baat karo.
Seedha, useful aur accurate jawab do.
Agar kisi baat ka pata nahi hai, toh saaf batao.
Internet se live information check kiye bina use current
ya verified hone ka claim mat karo.
"""


@app.get("/")
def home():
    return jsonify({
        "app": "Saathi Cloud AI",
        "status": "online",
        "model": ACTIVE_MODEL
    })


@app.get("/health")
def health():
    return jsonify({"status": "ok"}), 200


@app.post("/command")
def handle_command():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "reply": "Sir, valid JSON request bhejiye."
        }), 400

    command = data.get("command", "")

    if not isinstance(command, str):
        return jsonify({
            "reply": "Sir, command text format mein bhejiye."
        }), 400

    command = command.strip()

    if not command:
        return jsonify({
            "reply": "Kuch toh boliye Sir!"
        }), 400

    if len(command) > 8000:
        return jsonify({
            "reply": "Sir, message kaafi lamba hai. Chhota message bhejiye."
        }), 413

    normalized = command.casefold()
    now = datetime.now(ZoneInfo("Asia/Kolkata"))

    # Local date and time handlers
    time_phrases = [
        "time", "samay", "kitne baje", "current time"
    ]
    date_phrases = [
        "date", "tareekh", "aaj ki date",
        "aaj ki tareekh", "today's date"
    ]

    if any(word in normalized for word in time_phrases):
        return jsonify({
            "reply": (
                f"Abhi India mein {now.strftime('%I:%M %p')} "
                f"ho rahe hain Sir."
            )
        })

    if any(word in normalized for word in date_phrases):
        return jsonify({
            "reply": (
                f"Aaj {now.strftime('%d %B %Y')} hai Sir."
            )
        })

    if client is None:
        logger.error("GROQ_API_KEY is not configured.")
        return jsonify({
            "reply": (
                "Sir, AI service ki API key configure nahi hai. "
                "Server settings check karni hongi."
            )
        }), 503

    try:
        response = client.chat.completions.create(
            model=ACTIVE_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT
                },
                {
                    "role": "user",
                    "content": command
                }
            ],
            temperature=0.7,
            max_completion_tokens=800
        )

        reply = response.choices[0].message.content

        if not reply:
            reply = "Sir, is baar jawab generate nahi ho paya."

        return jsonify({"reply": reply.strip()})

    except Exception as e:
        # Detailed error server logs mein rahega
        logger.exception("Groq request failed: %s", type(e).__name__)

        return jsonify({
            "reply": (
                "Sir, AI service se response nahi mil paya. "
                "API key, model ID aur server logs check karein."
            )
        }), 502


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
