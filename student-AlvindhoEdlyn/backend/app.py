from flask import Flask, render_template, request
from flask_cors import CORS
from dotenv import load_dotenv
from openai import OpenAI
from pathlib import Path
import sqlite3
import os

#-----SETUP-----
load_dotenv()

DATABASE_NAME = "plan.db"

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://ai-mode:11434/v1")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:0.5b")
PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts"

app = Flask(
    __name__,
    template_folder="../frontend",
    static_folder="../frontend",
    static_url_path=""
)

CORS(app, resources={r"/*": {"origins": "*"}})

client = OpenAI(
    base_url=OLLAMA_BASE_URL,
    api_key="ollama"
)

def get_db_connection():
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def load_prompt(filename):
    prompt_path = PROMPT_DIR / filename
    return prompt_path.read_text(encoding="utf-8").strip()

#-----ROUTES-----
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/ask-with-context", methods=["POST"])
def ask_with_context():
    question = request.form.get("question", "").strip()
    itinerary_context = request.form.get("itinerary", "No itinerary provided yet.")

    if not question:
        return "<p>Question is required.</p>", 400

    try:
        sys_imp = load_prompt("plan_suggestions.txt")

        usr_resp = f"Itinerary Context:\n{itinerary_context}\n\nUser Question: {question}"

        response = client.chat.completions.create(
            model=OLLAMA_MODEL,
            messages=[
                {"role": "system", "content": sys_imp},
                {"role": "user", "content": usr_resp},
            ],
            max_tokens=300,
            temperature=0,
        )

        answer = response.choices[0].message.content
        return f"<p>{answer}</p>"

    except Exception as exc:
        print(f"Backend Error: {exc}")
        return (
            f"<p>Local AI agent request failed.</p><pre>{exc}</pre>",
            500,
        )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
