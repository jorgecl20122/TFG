from flask import Flask, render_template, request, redirect, url_for, send_from_directory, abort
from werkzeug.utils import secure_filename
from main import process_audio
import os
import uuid

app = Flask(__name__)

UPLOAD_FOLDER = "data/uploads"
OUTPUT_FOLDER = "data/out"
ALLOWED_EXTENSIONS = {"mp3", "wav", "m4a", "mpeg", "mp4"}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["OUTPUT_FOLDER"] = OUTPUT_FOLDER


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/upload", methods=["POST"])
def upload_file():
    if "audio" not in request.files:
        return "No se ha enviado ningún archivo", 400

    file = request.files["audio"]

    if file.filename == "":
        return "No se ha seleccionado ningún archivo", 400

    if not allowed_file(file.filename):
        return "Formato no permitido", 400

    original_name = secure_filename(file.filename)
    job_id = str(uuid.uuid4())
    upload_name = f"{job_id}_{original_name}"
    upload_path = os.path.join(app.config["UPLOAD_FOLDER"], upload_name)

    file.save(upload_path)

    job_output_dir = os.path.join(app.config["OUTPUT_FOLDER"], job_id)
    os.makedirs(job_output_dir, exist_ok=True)

    web_audio_path = url_for("uploaded_file", filename=upload_name)

    process_audio(
        audio_path=upload_path,
        output_dir=job_output_dir,
        web_audio_path=web_audio_path
    )

    return redirect(url_for("result", job_id=job_id))


@app.route("/result/<job_id>")
def result(job_id):
    html_path = os.path.join(app.config["OUTPUT_FOLDER"], job_id, "editor.html")

    if not os.path.exists(html_path):
        abort(404)

    return render_template("result.html", job_id=job_id)


@app.route("/viewer/<job_id>")
def viewer(job_id):
    folder = os.path.join(app.config["OUTPUT_FOLDER"], job_id)
    html_path = os.path.join(folder, "editor.html")

    if not os.path.exists(html_path):
        abort(404)

    return send_from_directory(folder, "editor.html")


@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


if __name__ == "__main__":
    app.run(debug=True)