from flask import Flask, render_template, request
from dotenv import load_dotenv
from openai import OpenAI
from pathlib import Path
import sqlite3
import os

#-----SETUP-----
load_dotenv()

DATABASE_NAME = "plan.db"

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:0.5b")

app = Flask(
    __name__,
    template_folder="../frontend",
    static_folder="../frontend",
    static_url_path="/static"
)

client = OpenAI(
    base_url=OLLAMA_BASE_URL,
    api_key="ollama"
)

PROMPT_DIR = Path(__file__).with_name("prompts")

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

@app.route("/trip/<int:trip_id>")
def view_trip(trip_it):
    conn = get_db_connection()
    days = conn.execute(
        "SELECT student_id, student_name, subject_code FROM day WHERE trip_id = trip_it"
    ).fetchall()
    conn.close()

    html = "<ul>"
    for day in days:
        html += (
            f"<li>"
            f"{day['student_id']} - "
            f"{day['student_name']} - "
            f"{day['subject_code']}"
            f"</li>"
        )
    html += "</ul>"

    return html



@app.route("/ask-with-context", methods=["POST"])
def ask_with_context():
    question = request.form.get("question", "").strip()

    if not question:
        return "<p>Question is required.</p>", 400

    implementation = 'prompts/implementation_system_prompt.txt'
    context_qa = 'prompts/context_qa_task_prompt.txt'

    with open(implementation, 'r') as file:
        sys_imp = file.read()
    with open(context_qa, 'r') as file:
        context = file.read()
    
    usr_resp = f"{context}. Based on this context, here is the user's question: {question}" 

    try:
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
        print("no")
        return (
            "<p>Local AI agent request failed. "
            "Please input proper context first.</p>"
            f"<pre>{exc}</pre>",
            503,
        )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
