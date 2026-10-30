
import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

CLOUD_URL = os.getenv(
    "SAATHI_CLOUD_URL",
    "https://saathicloud-1.onrender.com/command"
)

API_KEY = os.getenv("SAATHI_API_KEY")
CONVERSATION_FILE = "saathi_conversation.json"


def load_conversation_id():
    if not os.path.exists(CONVERSATION_FILE):
        return None

    try:
        with open(CONVERSATION_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)
            return data.get("conversation_id")
    except (json.JSONDecodeError, OSError):
        return None


def save_conversation_id(conversation_id):
    with open(CONVERSATION_FILE, "w", encoding="utf-8") as file:
        json.dump(
            {"conversation_id": conversation_id},
            file,
            ensure_ascii=False,
            indent=2
        )


def main():
    if not API_KEY:
        print("Error: .env file mein SAATHI_API_KEY set nahi hai.")
        return

    conversation_id = load_conversation_id()

    print("Saathi Cloud AI Connected!")
    print("Type 'exit' to quit.")
    print("Type 'new chat' to start a fresh conversation.\n")

    while True:
        user_input = input("Aap: ").strip()

        if not user_input:
            continue

        if user_input.lower() == "exit":
            print("Saathi: Phir milte hain!")
            break

        if user_input.lower() == "new chat":
            conversation_id = None

            if os.path.exists(CONVERSATION_FILE):
                os.remove(CONVERSATION_FILE)

            print("Saathi: Nayi conversation shuru ho gayi.\n")
            continue

        payload = {"command": user_input}

        if conversation_id:
            payload["conversation_id"] = conversation_id

        headers = {
            "X-API-Key": API_KEY,
            "Content-Type": "application/json"
        }

        try:
            response = requests.post(
                CLOUD_URL,
                json=payload,
                headers=headers,
                timeout=120
            )

            response.raise_for_status()
            data = response.json()

            conversation_id = data.get(
                "conversation_id",
                conversation_id
            )

            if conversation_id:
                save_conversation_id(conversation_id)

            print("\nSaathi:", data.get("reply", "Koi reply nahi mila."))

            if data.get("model"):
                print("Model:", data["model"])

            print()

        except requests.exceptions.HTTPError:
            print("\nServer Error:", response.status_code)
            print(response.text[:1000], "\n")

        except requests.exceptions.Timeout:
            print("\nSaathi: Server response mein time lag raha hai. Dobara try karein.\n")

        except requests.exceptions.RequestException as error:
            print("\nConnection Error:", error, "\n")

        except ValueError:
            print("\nSaathi: Server se valid JSON response nahi mila.\n")


if __name__ == "__main__":
    main()
