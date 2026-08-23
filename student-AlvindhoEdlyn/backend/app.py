from flask import Flask, render_template

app = Flask(
    __name__,
    template_folder="../frontend",
    static_folder="../frontend",
    static_url_path="/static"
)

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/health")
def health():
    return {"status": "ok", "student": "1"}

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
