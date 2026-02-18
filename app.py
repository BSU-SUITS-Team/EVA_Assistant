from flask import Flask, request, jsonify
import subprocess

app = Flask(__name__, static_folder=".", static_url_path="")

def generate_response(prompt):
    """
    Generate a response by calling the Deepseek model through Ollama.
    Make sure that Ollama is installed and Deepseek is set up locally.
    """
    # Construct the command to call Deepseek via Ollama
    command = ["ollama", "run", "deepseek-r1:1.5b"]

    try:
        # Run the command and pass the prompt via stdin
        result = subprocess.run(command, input=prompt, capture_output=True, text=True, check=True)
        # The response is expected in stdout
        response = result.stdout.strip()
    except subprocess.CalledProcessError as e:
        response = f"Error generating response: {e.stderr if e.stderr else e}"
    except FileNotFoundError:
        response = "Error: Ollama is not installed or not in PATH"

    return response

@app.route("/chat", methods=["GET", "POST"])
def chat():
    """
    API endpoint to receive a user message and return a chatbot response.
    """
    if request.method == "GET":
        return jsonify({"message": "Send a POST request with JSON: {\"message\": \"...\"}"})

    data = request.get_json()
    user_message = data.get("message", "")

    if not user_message:
        return jsonify({"error": "No message provided"}), 400

    response_text = generate_response(user_message)
    return jsonify({"response": response_text})

# Optionally, serve the frontend from the Flask app
@app.route("/", methods=["GET"])
def home():
    return app.send_static_file("index.html")

if __name__ == "__main__":
    app.run(debug=True)
