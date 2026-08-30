from concurrent.futures import thread

from flask import (
    Flask,
    render_template,
    request,
    send_from_directory,
    send_file,
    abort,
    jsonify,
    redirect,
    url_for,
    session
)
from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash, generate_password_hash
from functools import wraps
from main import process_audio
from mutagen import File as MutagenFile
from segments import generate_html
from pdf_generator import generate_transcript_pdf
from datetime import datetime
from logger import write_log
from dotenv import load_dotenv

import os
import uuid
import json
import time
import threading
import sqlite3
import secrets
import tempfile

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "clave_temporal_solo_desarrollo")

UPLOAD_FOLDER = "data/uploads"
OUTPUT_FOLDER = "data/out"
CONFIG_FOLDER = "data/config"
TEST_FOLDER = "data/test"
DB_FOLDER = "data/db"
PROFILE_PHOTO_FOLDER = "data/profile_photos"
DB_PATH = os.path.join(DB_FOLDER, "app.db")

CALIBRATION_FILE = os.path.join(CONFIG_FOLDER, "calibration.json")
CALIBRATION_AUDIO = os.path.join(TEST_FOLDER, "calibration_audio.mp3")

ALLOWED_EXTENSIONS = {"mp3", "wav", "m4a", "mpeg", "mp4"}
ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
AVATAR_COLORS = [
    "#3f7ad9",
    "#16a34a",
    "#ea580c",
    "#9333ea",
    "#0891b2",
    "#be123c",
    "#ca8a04",
    "#4f46e5"
]

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)
os.makedirs(CONFIG_FOLDER, exist_ok=True)
os.makedirs(TEST_FOLDER, exist_ok=True)
os.makedirs(DB_FOLDER, exist_ok=True)
os.makedirs(PROFILE_PHOTO_FOLDER, exist_ok=True)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["OUTPUT_FOLDER"] = OUTPUT_FOLDER

jobs = {}


# =========================
# BASE DE DATOS
# =========================

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('admin', 'user')),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS meetings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id TEXT NOT NULL UNIQUE,
        title TEXT NOT NULL,
        original_filename TEXT,
        stored_filename TEXT,
        upload_path TEXT NOT NULL,
        output_dir TEXT NOT NULL,
        owner_id INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        error_message TEXT DEFAULT '',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(owner_id) REFERENCES users(id)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS transcripts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        meeting_id INTEGER NOT NULL UNIQUE,
        json_path TEXT,
        html_path TEXT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(meeting_id) REFERENCES meetings(id)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS email_jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        meeting_id INTEGER NOT NULL,
        recipient TEXT NOT NULL,
        subject TEXT,
        body TEXT,
        status TEXT NOT NULL DEFAULT 'draft',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(meeting_id) REFERENCES meetings(id)
    )
    """)

    existing_columns = [
        row["name"]
        for row in cur.execute("PRAGMA table_info(users)").fetchall()
    ]

    if "profile_photo" not in existing_columns:
        cur.execute("ALTER TABLE users ADD COLUMN profile_photo TEXT DEFAULT ''")

    if "avatar_color" not in existing_columns:
        cur.execute("ALTER TABLE users ADD COLUMN avatar_color TEXT DEFAULT ''")

    users_without_color = cur.execute("""
        SELECT id
        FROM users
        WHERE avatar_color IS NULL OR avatar_color = ''
    """).fetchall()

    for user_row in users_without_color:
        cur.execute(
            "UPDATE users SET avatar_color = ? WHERE id = ?",
            (random_avatar_color(), user_row["id"])
        )

    conn.commit()

    admin_exists = cur.execute(
        "SELECT id FROM users WHERE role = 'admin' LIMIT 1"
    ).fetchone()

    if admin_exists is None:
        random_password = secrets.token_urlsafe(10)
        password_hash = generate_password_hash(random_password)

        cur.execute("""
            INSERT INTO users (username, password_hash, role)
            VALUES (?, ?, ?)
        """, ("admin", password_hash, "admin"))
        conn.commit()

        print("=" * 60)
        print("ADMIN INICIAL CREADO")
        print("Usuario: admin")
        print(f"Contraseña: {random_password}")
        print("Guarda esta contraseña. Solo se muestra al crear el admin.")
        print("=" * 60)

    conn.close()


# =========================
# AUTENTICACIÓN Y ROLES
# =========================

def get_current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None

    conn = get_connection()
    user = conn.execute(
        "SELECT * FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()
    conn.close()
    return user


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped_view


def admin_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        user = get_current_user()
        if user is None:
            return redirect(url_for("login"))

        if user["role"] != "admin":
            return "Acceso denegado", 403

        return view(*args, **kwargs)
    return wrapped_view


# =========================
# UTILIDADES
# =========================

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def allowed_image(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS


def random_avatar_color():
    return secrets.choice(AVATAR_COLORS)


def get_user_initial(user):
    username = user["username"] if user and user["username"] else "?"
    return username[0].upper()


def get_audio_duration(path):
    audio = MutagenFile(path)
    if audio is None or not hasattr(audio, "info") or not hasattr(audio.info, "length"):
        raise ValueError("No se ha podido leer la duración del audio")
    return float(audio.info.length)


def load_calibration_factor():
    if not os.path.exists(CALIBRATION_FILE):
        return None

    with open(CALIBRATION_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    return float(data.get("seconds_per_second", 0.27))


def save_calibration_factor(factor):
    with open(CALIBRATION_FILE, "w", encoding="utf-8") as f:
        json.dump({"seconds_per_second": factor}, f, indent=2, ensure_ascii=False)


def calibrate_machine():
    if not os.path.exists(CALIBRATION_AUDIO):
        print(
            "No se ha encontrado el audio de calibración. "
            "Se usará el factor anterior o 0.27 por defecto."
        )

        previous_factor = load_calibration_factor()

        if previous_factor is not None:
            return previous_factor

        save_calibration_factor(0.27)
        return 0.27

    duration = get_audio_duration(CALIBRATION_AUDIO)

    if duration <= 0:
        raise ValueError(
            "El audio de calibración no tiene una duración válida"
        )

    print("=" * 60)
    print("INICIANDO CALIBRACIÓN COMPLETA")
    print(f"Duración del audio: {duration:.2f} segundos")
    print("Se ejecutarán las dos transcripciones y la diarización.")
    print("=" * 60)

    try:
        with tempfile.TemporaryDirectory(
            prefix="transcribematic_calibration_"
        ) as calibration_output_dir:

            start = time.perf_counter()

            process_audio(
                audio_path=CALIBRATION_AUDIO,
                output_dir=calibration_output_dir,
                web_audio_path="/calibration_audio.mp3",
                job_id="calibration",
                require_diarization=True
            )

            elapsed = time.perf_counter() - start

    except Exception as e:
        print(f"Error durante la calibración completa: {e}")

        previous_factor = load_calibration_factor()

        if previous_factor is not None:
            print(
                f"Se mantiene el factor anterior: "
                f"{previous_factor:.3f}"
            )
            return previous_factor

        print("Se utilizará el factor 0.27 por defecto.")
        save_calibration_factor(0.27)
        return 0.27

    factor = elapsed / duration

    save_calibration_factor(factor)

    print("=" * 60)
    print("CALIBRACIÓN COMPLETADA")
    print(f"Duración del audio: {duration:.2f} s")
    print(f"Tiempo total de procesamiento: {elapsed:.2f} s")
    print(f"Factor guardado: {factor:.3f}")
    print(f"Estimación: {factor * 60:.1f} segundos por minuto")
    print("=" * 60)

    return factor

def format_duration(seconds):
    seconds = max(0, int(round(seconds)))
    minutes = seconds // 60
    secs = seconds % 60
    return f"{minutes:02d}:{secs:02d}"


def user_can_access_meeting(meeting, user):
    if meeting is None or user is None:
        return False

    if user["role"] == "admin":
        return True

    return meeting["owner_id"] == user["id"]


# =========================
# LOGIN / LOGOUT
# =========================

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        conn = get_connection()
        user = conn.execute(
            "SELECT * FROM users WHERE username = ?",
            (username,)
        ).fetchone()
        conn.close()

        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            return redirect(url_for("index"))

        return render_template(
            "login.html",
            error="Usuario o contraseña incorrectos",
            current_user=None
        )

    return render_template(
        "login.html",
        error=None,
        current_user=None
    )


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# =========================
# HOME
# =========================

@app.route("/")
@login_required
def index():
    factor = load_calibration_factor()
    if factor is None:
        factor = 0.27

    user = get_current_user()

    return render_template(
        "index.html",
        seconds_per_minute=round(factor * 60, 1),
        current_user=user
    )


# =========================
# SUBIDA Y PROCESADO
# =========================

@app.route("/upload", methods=["POST"])
@login_required
def upload_file():
    if "audio" not in request.files:
        return "No se ha enviado ningún archivo", 400

    file = request.files["audio"]

    if file.filename == "":
        return "No se ha seleccionado ningún archivo", 400

    if not allowed_file(file.filename):
        return "Formato no permitido", 400

    original_name = secure_filename(file.filename)
    title = request.form.get("title", "").strip()

    if not title:
        title = original_name

    job_id = str(uuid.uuid4())
    upload_name = f"{job_id}_{original_name}"
    upload_path = os.path.join(app.config["UPLOAD_FOLDER"], upload_name)
    job_output_dir = os.path.join(app.config["OUTPUT_FOLDER"], job_id)

    os.makedirs(job_output_dir, exist_ok=True)
    file.save(upload_path)

    duration = get_audio_duration(upload_path)

    factor = load_calibration_factor()
    if factor is None:
        factor = 0.27

    estimated_seconds = duration * factor

    user = get_current_user()

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO meetings (
            job_id, title, original_filename, stored_filename,
            upload_path, output_dir, owner_id, status, error_message
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        job_id,
        title,
        original_name,
        upload_name,
        upload_path,
        job_output_dir,
        user["id"],
        "pending",
        ""
    ))
    conn.commit()
    meeting_id = cur.lastrowid
    conn.close()

    jobs[job_id] = {
        "meeting_id": meeting_id,
        "status": "pending",
        "upload_path": upload_path,
        "upload_name": upload_name,
        "output_dir": job_output_dir,
        "duration": duration,
        "estimated_seconds": estimated_seconds,
        "owner_id": user["id"]
    }

    write_log(
        module="upload",
        action="audio_uploaded",
        user=user["username"],
        job_id=job_id,
        details={
            "title": title,
            "original_filename": original_name,
            "duration": duration,
            "estimated_seconds": estimated_seconds
        }
    )

    thread = threading.Thread(target=run_transcription, args=(job_id,))
    thread.start()

    return render_template(
        "processing.html",
        job_id=job_id,
        audio_duration=format_duration(duration),
        estimated_time=format_duration(estimated_seconds),
        seconds_per_minute=round(factor * 60, 1),
        current_user=user
    )


def run_transcription(job_id):
    job = jobs[job_id]
    job["status"] = "processing"

    username = get_username_by_id(job["owner_id"])

    write_log(
        module="transcription",
        action="transcription_started",
        user=username,
        job_id=job_id,
        details={
            "meeting_id": job["meeting_id"],
            "upload_path": job["upload_path"]
        }
    )

    conn = get_connection()
    conn.execute(
        "UPDATE meetings SET status = ?, error_message = ? WHERE id = ?",
        ("processing", "", job["meeting_id"])
    )
    conn.commit()
    conn.close()

    try:
        web_audio_path = f"/uploads/{job['upload_name']}"

        result = process_audio(
            audio_path=job["upload_path"],
            output_dir=job["output_dir"],
            web_audio_path=web_audio_path,
            job_id=job_id
        )

        conn = get_connection()
        conn.execute(
            "UPDATE meetings SET status = ?, error_message = ? WHERE id = ?",
            ("done", "", job["meeting_id"])
        )
        conn.execute("""
            INSERT INTO transcripts (meeting_id, json_path, html_path, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(meeting_id) DO UPDATE SET
                json_path = excluded.json_path,
                html_path = excluded.html_path,
                updated_at = CURRENT_TIMESTAMP
        """, (
            job["meeting_id"],
            result["json_path"],
            result["html_path"]
        ))
        conn.commit()
        conn.close()

        job["status"] = "done"

        write_log(
            module="transcription",
            action="transcription_finished",
            user=username,
            job_id=job_id,
            details={
                "meeting_id": job["meeting_id"]
            }
        )

    except Exception as e:
        error_text = str(e)

        conn = get_connection()
        conn.execute(
            "UPDATE meetings SET status = ?, error_message = ? WHERE id = ?",
            ("error", error_text, job["meeting_id"])
        )
        conn.commit()
        conn.close()

        job["status"] = "error"
        job["error"] = error_text

        write_log(
            module="transcription",
            action="transcription_error",
            user=username,
            job_id=job_id,
            details={
                "meeting_id": job["meeting_id"],
                "error": error_text
            }
        )

def get_username_by_id(user_id):
    conn = get_connection()
    user = conn.execute(
        "SELECT username FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()
    conn.close()

    if user is None:
        return f"usuario_id_{user_id}"

    return user["username"]


@app.route("/start_process/<job_id>", methods=["POST"])
@login_required
def start_process(job_id):
    conn = get_connection()
    meeting = conn.execute(
        "SELECT * FROM meetings WHERE job_id = ?",
        (job_id,)
    ).fetchone()
    conn.close()

    if meeting is None:
        abort(404)

    user = get_current_user()
    if not user_can_access_meeting(meeting, user):
        return "Acceso denegado", 403

    job = jobs.get(job_id)

    if job is None:
        jobs[job_id] = {
            "meeting_id": meeting["id"],
            "status": meeting["status"],
            "upload_path": meeting["upload_path"],
            "upload_name": meeting["stored_filename"],
            "output_dir": meeting["output_dir"],
            "owner_id": meeting["owner_id"],
            "error": meeting["error_message"] or ""
        }
        job = jobs[job_id]

    if job["status"] == "pending":
        thread = threading.Thread(target=run_transcription, args=(job_id,))
        thread.start()

    return jsonify({"status": job["status"]})


@app.route("/job_status/<job_id>")
@login_required
def job_status(job_id):
    conn = get_connection()
    meeting = conn.execute(
        "SELECT * FROM meetings WHERE job_id = ?",
        (job_id,)
    ).fetchone()
    conn.close()

    if meeting is None:
        abort(404)

    user = get_current_user()
    if not user_can_access_meeting(meeting, user):
        return "Acceso denegado", 403

    job = jobs.get(job_id)

    if job:
        return jsonify({
            "status": job["status"],
            "error": job.get("error", "")
        })

    return jsonify({
        "status": meeting["status"],
        "error": meeting["error_message"] or ""
    })


@app.route("/review_segment/<job_id>/<int:segment_index>", methods=["POST"])
@login_required
def review_segment(job_id, segment_index):
    conn = get_connection()
    meeting = conn.execute(
        "SELECT * FROM meetings WHERE job_id = ?",
        (job_id,)
    ).fetchone()

    if meeting is None:
        conn.close()
        abort(404)

    user = get_current_user()
    if not user_can_access_meeting(meeting, user):
        conn.close()
        return jsonify({"ok": False, "error": "Acceso denegado"}), 403

    transcript = conn.execute(
        "SELECT * FROM transcripts WHERE meeting_id = ?",
        (meeting["id"],)
    ).fetchone()

    if transcript is None or not transcript["json_path"]:
        conn.close()
        return jsonify({
            "ok": False,
            "error": "No se ha encontrado la transcripción"
        }), 404

    json_path = transcript["json_path"]
    html_path = transcript["html_path"]

    data = request.get_json(silent=True) or {}
    reviewed_text = data.get("text", "").strip()

    if not reviewed_text:
        conn.close()
        return jsonify({
            "ok": False,
            "error": "El texto revisado no puede estar vacío"
        }), 400

    if not os.path.exists(json_path):
        conn.close()
        return jsonify({
            "ok": False,
            "error": "No existe el archivo JSON de segmentos"
        }), 404

    with open(json_path, "r", encoding="utf-8") as f:
        segments = json.load(f)

    if segment_index < 0 or segment_index >= len(segments):
        conn.close()
        return jsonify({
            "ok": False,
            "error": "Índice de segmento no válido"
        }), 400

    reviewed_at = datetime.now().strftime("%d/%m/%Y %H:%M")

    segments[segment_index]["text"] = reviewed_text
    segments[segment_index]["human_reviewed"] = True
    segments[segment_index]["reviewed_by"] = user["username"]
    segments[segment_index]["review_status"] = "human_reviewed"
    segments[segment_index]["reviewed_at"] = reviewed_at

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(segments, f, indent=2, ensure_ascii=False)

    write_log(
        module="editor",
        action="segment_reviewed",
        user=user["username"],
        job_id=job_id,
        details={
            "segment_index": segment_index,
            "reviewed_at": reviewed_at
        }
    )

    web_audio_path = f"/uploads/{meeting['stored_filename']}"

    generate_html(
        segments,
        web_audio_path,
        html_path,
        job_id=job_id
    )

    conn.execute(
        """
        UPDATE transcripts
        SET updated_at = CURRENT_TIMESTAMP
        WHERE meeting_id = ?
        """,
        (meeting["id"],)
    )
    conn.commit()
    conn.close()

    return jsonify({
        "ok": True,
        "text": reviewed_text,
        "status": "human_reviewed",
        "reviewed_at": reviewed_at
    })

@app.route("/update_speaker_name/<job_id>", methods=["POST"])
@login_required
def update_speaker_name(job_id):
    conn = get_connection()
    meeting = conn.execute(
        "SELECT * FROM meetings WHERE job_id = ?",
        (job_id,)
    ).fetchone()

    if meeting is None:
        conn.close()
        abort(404)

    user = get_current_user()
    if not user_can_access_meeting(meeting, user):
        conn.close()
        return jsonify({
            "ok": False,
            "error": "Acceso denegado"
        }), 403

    transcript = conn.execute(
        "SELECT * FROM transcripts WHERE meeting_id = ?",
        (meeting["id"],)
    ).fetchone()

    if transcript is None or not transcript["json_path"]:
        conn.close()
        return jsonify({
            "ok": False,
            "error": "No se ha encontrado la transcripción"
        }), 404

    json_path = transcript["json_path"]
    html_path = transcript["html_path"]

    data = request.get_json(silent=True) or {}
    original_speaker = data.get("speaker", "").strip()
    speaker_name = data.get("name", "").strip()

    if not original_speaker:
        conn.close()
        return jsonify({
            "ok": False,
            "error": "No se ha recibido el hablante original"
        }), 400

    if not os.path.exists(json_path):
        conn.close()
        return jsonify({
            "ok": False,
            "error": "No existe el archivo JSON de segmentos"
        }), 404

    with open(json_path, "r", encoding="utf-8") as f:
        segments = json.load(f)

    updated = 0

    for segment in segments:
        if segment.get("speaker", "SPEAKER_UNKNOWN") == original_speaker:
            segment["speaker_name"] = speaker_name
            updated += 1

    if updated == 0:
        conn.close()
        return jsonify({
            "ok": False,
            "error": "No se ha encontrado ningún segmento con ese hablante"
        }), 404

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(segments, f, indent=2, ensure_ascii=False)

    write_log(
        module="speakers",
        action="speaker_name_updated",
        user=user["username"],
        job_id=job_id,
        details={
            "original_speaker": original_speaker,
            "new_name": speaker_name,
            "segments_updated": updated
        }
    )

    web_audio_path = f"/uploads/{meeting['stored_filename']}"

    generate_html(
        segments,
        web_audio_path,
        html_path,
        job_id=job_id
    )

    conn.execute(
        """
        UPDATE transcripts
        SET updated_at = CURRENT_TIMESTAMP
        WHERE meeting_id = ?
        """,
        (meeting["id"],)
    )
    conn.commit()
    conn.close()

    return jsonify({
        "ok": True,
        "speaker": original_speaker,
        "name": speaker_name,
        "updated": updated
    })

@app.route("/log_event", methods=["POST"])
@login_required
def log_event():
    user = get_current_user()
    data = request.get_json(silent=True) or {}

    module = data.get("module", "frontend")
    action = data.get("action", "unknown")
    job_id = data.get("job_id", "")
    shortcut = data.get("shortcut", "")
    details = data.get("details", {})

    write_log(
        module=module,
        action=action,
        user=user["username"] if user else None,
        job_id=job_id,
        shortcut=shortcut,
        details=details
    )

    return jsonify({"ok": True})


# =========================
# RESULTADOS
# =========================

@app.route("/result/<job_id>")
@login_required
def result(job_id):
    conn = get_connection()
    meeting = conn.execute(
        "SELECT * FROM meetings WHERE job_id = ?",
        (job_id,)
    ).fetchone()
    conn.close()

    if meeting is None:
        abort(404)

    user = get_current_user()
    if not user_can_access_meeting(meeting, user):
        return "Acceso denegado", 403

    if meeting["status"] in ("pending", "processing"):
        factor = load_calibration_factor()
        if factor is None:
            factor = 0.27

        try:
            duration = get_audio_duration(meeting["upload_path"])
        except Exception:
            duration = 0

        estimated_seconds = duration * factor

        return render_template(
            "processing.html",
            job_id=job_id,
            audio_duration=format_duration(duration),
            estimated_time=format_duration(estimated_seconds),
            seconds_per_minute=round(factor * 60, 1),
            current_user=user
    )

    if meeting["status"] == "error":
        return f"Error procesando la reunión: {meeting['error_message']}", 500

    html_path = os.path.join(app.config["OUTPUT_FOLDER"], job_id, "editor.html")

    if not os.path.exists(html_path):
        return "La transcripción todavía no está disponible. Vuelve a intentarlo en unos segundos.", 202

    return render_template("result.html", job_id=job_id, meeting=meeting)


@app.route("/viewer/<job_id>")
@login_required
def viewer(job_id):
    conn = get_connection()
    meeting = conn.execute(
        "SELECT * FROM meetings WHERE job_id = ?",
        (job_id,)
    ).fetchone()

    if meeting is None:
        conn.close()
        abort(404)

    user = get_current_user()
    if not user_can_access_meeting(meeting, user):
        conn.close()
        return "Acceso denegado", 403

    transcript = conn.execute(
        "SELECT * FROM transcripts WHERE meeting_id = ?",
        (meeting["id"],)
    ).fetchone()

    conn.close()

    if transcript is None or not transcript["json_path"]:
        abort(404)

    json_path = transcript["json_path"]
    html_path = transcript["html_path"]

    if not os.path.exists(json_path):
        abort(404)

    with open(json_path, "r", encoding="utf-8") as f:
        segments = json.load(f)

    web_audio_path = f"/uploads/{meeting['stored_filename']}"

    generate_html(
        segments,
        web_audio_path,
        html_path,
        job_id=job_id
    )

    folder = os.path.dirname(html_path)
    filename = os.path.basename(html_path)

    return send_from_directory(folder, filename)


@app.route("/acta_pdf/<job_id>")
@login_required
def acta_pdf(job_id):
    conn = get_connection()
    meeting = conn.execute(
        "SELECT * FROM meetings WHERE job_id = ?",
        (job_id,)
    ).fetchone()

    if meeting is None:
        conn.close()
        abort(404)

    user = get_current_user()
    if not user_can_access_meeting(meeting, user):
        conn.close()
        return "Acceso denegado", 403

    transcript = conn.execute(
        "SELECT * FROM transcripts WHERE meeting_id = ?",
        (meeting["id"],)
    ).fetchone()

    conn.close()

    if transcript is None or not transcript["json_path"]:
        return "No se ha encontrado la transcripción", 404

    json_path = transcript["json_path"]

    if not os.path.exists(json_path):
        return "No existe el archivo JSON de segmentos", 404

    with open(json_path, "r", encoding="utf-8") as f:
        segments = json.load(f)

    pdf_path = os.path.join(
        meeting["output_dir"],
        "transcripcion_acta.pdf"
    )

    generate_transcript_pdf(
        segments=segments,
        meeting=meeting,
        output_path=pdf_path
    )

    safe_title = secure_filename(meeting["title"]) or "transcripcion"
    download_name = f"{safe_title}_acta.pdf"

    write_log(
        module="pdf",
        action="pdf_generated",
        user=user["username"],
        job_id=job_id,
        details={
            "meeting_title": meeting["title"],
            "output_path": pdf_path
        }
    )

    return send_file(
        pdf_path,
        as_attachment=True,
        download_name=download_name,
        mimetype="application/pdf"
    ) 


@app.route("/uploads/<filename>")
@login_required
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


@app.route("/profile_photos/<filename>")
@login_required
def profile_photo(filename):
    return send_from_directory(PROFILE_PHOTO_FOLDER, filename)


# =========================
# LISTADO DE REUNIONES
# =========================

@app.route("/meetings")
@login_required
def meetings():
    user = get_current_user()
    conn = get_connection()

    if user["role"] == "admin":
        rows = conn.execute("""
            SELECT 
                meetings.*, 
                users.username,
                users.profile_photo,
                users.avatar_color
            FROM meetings
            JOIN users ON users.id = meetings.owner_id
            ORDER BY meetings.created_at DESC
        """).fetchall()
    else:
        rows = conn.execute("""
            SELECT meetings.*, users.username, users.profile_photo, users.avatar_color
            FROM meetings
            JOIN users ON users.id = meetings.owner_id
            WHERE meetings.owner_id = ?
            ORDER BY meetings.created_at DESC
        """, (user["id"],)).fetchall()

    conn.close()

    return render_template(
        "meetings.html",
        meetings=rows,
        current_user=user
    )


# =========================
# ADMIN: USUARIOS
# =========================

@app.route("/admin/users")
@admin_required
def admin_users():
    conn = get_connection()
    users = conn.execute("""
        SELECT id, username, role, created_at
        FROM users
        ORDER BY created_at DESC
    """).fetchall()
    conn.close()

    return render_template(
        "admin_users.html",
        users=users,
        current_user=get_current_user()
    )


@app.route("/admin/users/create", methods=["POST"])
@admin_required
def create_user():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    role = request.form.get("role", "").strip()

    if not username or not password:
        return "Usuario y contraseña obligatorios", 400

    if role not in ("admin", "user"):
        return "Rol no válido", 400

    conn = get_connection()
    try:
        conn.execute("""
            INSERT INTO users (username, password_hash, role, avatar_color)
            VALUES (?, ?, ?, ?)
        """, (
            username,
            generate_password_hash(password),
            role,
            random_avatar_color()
        ))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return "Ese usuario ya existe", 400
    conn.close()
    return redirect(url_for("admin_users"))


@app.route("/admin/users/delete/<int:user_id>", methods=["POST"])
@admin_required
def delete_user(user_id):
    current_user = get_current_user()

    if user_id == current_user["id"]:
        return "No puedes borrarte a ti mismo", 400

    conn = get_connection()

    user_to_delete = conn.execute(
        "SELECT * FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()

    if user_to_delete is None:
        conn.close()
        return "Usuario no encontrado", 404

    meetings_count = conn.execute(
        "SELECT COUNT(*) AS total FROM meetings WHERE owner_id = ?",
        (user_id,)
    ).fetchone()["total"]

    if meetings_count > 0:
        conn.close()
        return "No se puede borrar un usuario que ya tiene reuniones asociadas", 400

    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()

    return redirect(url_for("admin_users"))

@app.route("/profile")
@login_required
def profile():
    user = get_current_user()
    conn = get_connection()

    recent_meetings = conn.execute("""
        SELECT *
        FROM meetings
        WHERE owner_id = ?
        ORDER BY created_at DESC
        LIMIT 5
    """, (user["id"],)).fetchall()

    conn.close()

    return render_template(
        "profile.html",
        current_user=user,
        recent_meetings=recent_meetings,
        message=request.args.get("message", ""),
        error=request.args.get("error", "")
    )


@app.route("/profile/update_username", methods=["POST"])
@login_required
def update_username():
    user = get_current_user()
    new_username = request.form.get("new_username", "").strip()

    if not new_username:
        return redirect(url_for("profile", error="El username no puede estar vacío"))

    conn = get_connection()
    try:
        conn.execute(
            "UPDATE users SET username = ? WHERE id = ?",
            (new_username, user["id"])
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return redirect(url_for("profile", error="Ese nombre de usuario ya existe"))

    conn.close()
    return redirect(url_for("profile", message="Username actualizado correctamente"))


@app.route("/profile/update_photo", methods=["POST"])
@login_required
def update_photo():
    user = get_current_user()

    if "photo" not in request.files:
        return redirect(url_for("profile", error="No se ha enviado ninguna foto"))

    file = request.files["photo"]

    if file.filename == "":
        return redirect(url_for("profile", error="No se ha seleccionado ninguna foto"))

    if not allowed_image(file.filename):
        return redirect(url_for("profile", error="Formato de imagen no permitido"))

    original_name = secure_filename(file.filename)
    extension = original_name.rsplit(".", 1)[1].lower()
    photo_name = f"user_{user['id']}_{uuid.uuid4().hex}.{extension}"
    photo_path = os.path.join(PROFILE_PHOTO_FOLDER, photo_name)

    file.save(photo_path)

    old_photo = user["profile_photo"] if "profile_photo" in user.keys() else ""

    conn = get_connection()
    conn.execute(
        "UPDATE users SET profile_photo = ? WHERE id = ?",
        (photo_name, user["id"])
    )
    conn.commit()
    conn.close()

    if old_photo:
        old_path = os.path.join(PROFILE_PHOTO_FOLDER, old_photo)

        if os.path.exists(old_path):
            try:
                os.remove(old_path)
            except OSError:
                pass

    return redirect(url_for("profile", message="Foto de perfil actualizada correctamente"))


@app.route("/profile/update_password", methods=["POST"])
@login_required
def update_password():
    user = get_current_user()
    current_password = request.form.get("current_password", "").strip()
    new_password = request.form.get("new_password", "").strip()

    if not current_password or not new_password:
        return redirect(url_for("profile", error="Debes completar ambos campos"))

    if not check_password_hash(user["password_hash"], current_password):
        return redirect(url_for("profile", error="La contraseña actual no es correcta"))

    conn = get_connection()
    conn.execute(
        "UPDATE users SET password_hash = ? WHERE id = ?",
        (generate_password_hash(new_password), user["id"])
    )
    conn.commit()
    conn.close()

    return redirect(url_for("profile", message="Contraseña actualizada correctamente"))


# =========================
# ARRANQUE
# =========================

if __name__ == "__main__":
    init_db()

    calibrate_machine()

    app.run(debug=True, use_reloader=False)