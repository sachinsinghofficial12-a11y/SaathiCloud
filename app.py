from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "Saathi Cloud Server is Running!"})

@app.route("/command", methods=["POST"])
def handle_command():
    data = request.json
    command = data.get("command", "").lower()
    
    print(f"Command mili: {command}")
    
    reply = "Done Sir."
    if "hello" in command or "hi" in command:
        reply = "Haan Aakash Sir, main sun rahi hoon. Boliye kya madad karu?"
    elif "kaise ho" in command:
        reply = "Main ekdum badhiya hoon sir, aap bataiye aap kaise hain?"
    else:
        reply = f"Aapne kaha: {command}. Ispar kaam chal raha hai!"

    return jsonify({"reply": reply})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)