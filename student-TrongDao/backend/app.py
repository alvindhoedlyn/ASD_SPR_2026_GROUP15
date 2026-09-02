import os
import requests
from flask import Flask, render_template, jsonify

app = Flask(
    __name__,
    template_folder="../frontend",
    static_folder="../frontend",
    static_url_path="/static"
)

DATABASE_API_URL = os.getenv(
    "DATABASE_API_URL",
    "http://localhost:5404"
)


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/health")
def health():
    return {"status": "ok", "student": "4"}


@app.route("/api/places", methods=["GET"])
def get_places():
    try:
        response = requests.get(
            f"{DATABASE_API_URL}/places",
            timeout=5
        )

        response.raise_for_status()

        return jsonify(response.json()), response.status_code

    except requests.RequestException as error:
        return jsonify({
            "error": "Could not connect to the database service",
            "details": str(error)
        }), 503

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5004)
