
import requests

CLOUD_URL = "http://127.0.0.1:5000/command"

print("Saathi Cloud Client Connected! Type 'exit' to quit.\n")

while True:
    user_input = input("Aap: ").strip()

    if user_input.lower() == "exit":
        print("Alvida! Saathi client band ho raha hai.")
        break

    if not user_input:
        continue

    try:
        response = requests.post(
            CLOUD_URL,
            json={"command": user_input},
            timeout=60
        )

        if response.status_code == 200:
            data = response.json()
            print(f"Saathi: {data.get('reply', 'No response')}")

        else:
            print(f"Error: Server returned status code {response.status_code}")

            try:
                error_data = response.json()
                print("Details:", error_data)
            except ValueError:
                print("Details:", response.text[:500])

    except requests.exceptions.Timeout:
        print("Saathi: Server se response aane mein zyada samay lag raha hai.")

    except requests.exceptions.RequestException as e:
        print(f"Connection Error: {e}")
