import os
import sqlite3
import secrets
from werkzeug.security import generate_password_hash

DB_FOLDER = "data/db"
DB_PATH = os.path.join(DB_FOLDER, "app.db")

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    os.makedirs(DB_FOLDER, exist_ok=True)

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('admin', 'user')),
        profile_photo TEXT DEFAULT '',
        avatar_color TEXT DEFAULT '',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS meetings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        original_filename TEXT,
        stored_filename TEXT,
        upload_path TEXT,
        output_dir TEXT,
        owner_id INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
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

    # Crear admin inicial si no existe ninguno
    cur.execute("SELECT COUNT(*) AS total FROM users WHERE role = 'admin'")
    total_admins = cur.fetchone()["total"]

    if total_admins == 0:
        random_password = secrets.token_urlsafe(10)
        password_hash = generate_password_hash(random_password)

        cur.execute("""
            INSERT INTO users (username, password_hash, role, avatar_color)
            VALUES (?, ?, ?, ?)
        """, ("admin", password_hash, "admin", random_avatar_color()))

        conn.commit()

        print("=" * 60)
        print("ADMIN INICIAL CREADO")
        print("Usuario: admin")
        print(f"Contraseña: {random_password}")
        print("Guárdala porque solo se muestra esta vez.")
        print("=" * 60)

    conn.close()