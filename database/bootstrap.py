import os
import sqlite3

from config import DB_PATH, SCHEMA_PATH


def ensure_database_exists() -> bool:
    """
    Creates a fresh database from schema.sql if DB file does not exist.
    Returns True if it created a new DB, False if it already existed.
    """
    if os.path.exists(DB_PATH):
        return False

    # Ensure parent dir exists
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    if not os.path.exists(SCHEMA_PATH):
        raise FileNotFoundError(
            f"schema.sql não encontrado em: {SCHEMA_PATH}\n"
            "Garanta que você está empacotando /database/schema.sql no build."
        )

    conn = sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON;")

    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        sql = f.read()

    # Defensive fix: your schema.sql has duplicated bloqueios creation.
    # To avoid bootstrap crashes, keep only the IF NOT EXISTS version.
    sql = sql.replace(
        "CREATE TABLE bloqueios (\n"
        "    id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
        "    profissional_id INTEGER NOT NULL,\n"
        "    data TEXT NOT NULL,\n"
        "    hora_inicio TEXT NOT NULL,\n"
        "    hora_fim TEXT NOT NULL,\n"
        "    motivo TEXT\n"
        ");\n\n",
        ""
    )

    conn.executescript(sql)
    conn.commit()
    conn.close()
    return True
