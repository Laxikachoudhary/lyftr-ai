
import os
import sqlite3
from pathlib import Path
from urllib.parse import unquote

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./app.db")


def get_database_path():
    """Convert SQLite DATABASE_URL into a filesystem path."""
    if not DATABASE_URL.startswith("sqlite:///"):
        raise ValueError("Only SQLite DATABASE_URL is supported")

    path = unquote(DATABASE_URL[len("sqlite:///"):])

    if path.startswith("/"):
        db_path = Path(path)
    else:
        db_path = Path(__file__).resolve().parent.parent / path

    db_path.parent.mkdir(parents=True, exist_ok=True)
    return db_path


DATABASE_PATH = get_database_path()


def get_connection():
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db():
    """Create tables and safely upgrade existing databases."""
    with get_connection() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                title TEXT DEFAULT 'New Chat',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Upgrade existing databases without deleting their data.
        columns = [
            row["name"]
            for row in connection.execute(
                "PRAGMA table_info(sessions)"
            ).fetchall()
        ]

        if "title" not in columns:
            connection.execute("""
                ALTER TABLE sessions
                ADD COLUMN title TEXT DEFAULT 'New Chat'
            """)

        connection.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                input_tokens INTEGER DEFAULT 0,
                output_tokens INTEGER DEFAULT 0,
                model TEXT,
                latency_ms REAL DEFAULT 0,
                key_id TEXT,
                fallback_attempts INTEGER DEFAULT 0,
                response_source TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id)
                    REFERENCES sessions(session_id)
                    ON DELETE CASCADE
            )
        """)

        connection.commit()


def create_session(session_id: str, title: str = "New Chat"):
    with get_connection() as connection:
        connection.execute(
            "INSERT INTO sessions (session_id, title) VALUES (?, ?)",
            (session_id, title)
        )
        connection.commit()


def session_exists(session_id: str) -> bool:
    with get_connection() as connection:
        result = connection.execute(
            "SELECT 1 FROM sessions WHERE session_id = ?",
            (session_id,)
        ).fetchone()

        return result is not None


def update_session_title(session_id: str, title: str):
    with get_connection() as connection:
        connection.execute(
            "UPDATE sessions SET title = ? WHERE session_id = ?",
            (title, session_id)
        )
        connection.commit()


def get_all_sessions():
    """Return conversations, newest activity first."""
    with get_connection() as connection:
        rows = connection.execute("""
            SELECT
                s.session_id,
                s.title,
                s.created_at,
                (
                    SELECT m.content
                    FROM messages m
                    WHERE m.session_id = s.session_id
                    ORDER BY m.id DESC
                    LIMIT 1
                ) AS last_message,
                (
                    SELECT MAX(m.id)
                    FROM messages m
                    WHERE m.session_id = s.session_id
                ) AS last_message_id
            FROM sessions s
            ORDER BY
                last_message_id DESC,
                s.created_at DESC
        """).fetchall()

        return [dict(row) for row in rows]


def add_message(
    session_id: str,
    role: str,
    content: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    model: str = "",
    latency_ms: float = 0,
    key_id: str = "",
    fallback_attempts: int = 0,
    response_source: str = ""
):
    with get_connection() as connection:
        connection.execute("""
            INSERT INTO messages (
                session_id, role, content, input_tokens,
                output_tokens, model, latency_ms, key_id,
                fallback_attempts, response_source
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session_id, role, content, input_tokens,
            output_tokens, model, latency_ms, key_id,
            fallback_attempts, response_source
        ))
        connection.commit()


def get_session_messages(session_id: str):
    with get_connection() as connection:
        rows = connection.execute("""
            SELECT * FROM messages
            WHERE session_id = ?
            ORDER BY id ASC
        """, (session_id,)).fetchall()

        return [dict(row) for row in rows]
