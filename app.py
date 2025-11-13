from flask import Flask, render_template, request, jsonify
from extensions import db, make_celery
import redis, os, uuid

app = Flask(__name__)

app.config.update(
    SQLALCHEMY_DATABASE_URI="sqlite:///acme.db",
    CELERY_BROKER_URL="redis://localhost:6379/0",
    CELERY_RESULT_BACKEND="redis://localhost:6379/0",
    UPLOAD_FOLDER=os.path.join(os.getcwd(), "uploads")
)

db.init_app(app)
celery = make_celery(app)
r = redis.Redis(host="localhost", port=6379, db=0)

@app.route("/")
def home():
    return render_template("upload.html")

@app.route("/upload", methods=["POST"])
def upload_csv():
    file = request.files.get("file")
    if not file or file.filename == "":
        return jsonify({"error": "No file uploaded"}), 400

    # Save file
    filename = f"{uuid.uuid4()}.csv"
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    file.save(filepath)

    # For now, just confirm upload
    return jsonify({"message": f"File {filename} uploaded successfully!"})

if __name__ == "__main__":
    app.run(debug=True)
