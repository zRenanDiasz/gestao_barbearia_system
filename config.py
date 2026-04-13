import os
import sys


def _is_frozen() -> bool:
    return getattr(sys, "frozen", False) is True


def app_dir() -> str:
    """
    Base directory:
    - DEV: directory where config.py lives (project root)
    - EXE: directory where the .exe lives
    """
    if _is_frozen():
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


APP_DIR = app_dir()

# Where templates/static will exist in the packaged folder (same folder as exe)
TEMPLATES_DIR = os.path.join(APP_DIR, "templates")
if not os.path.exists(TEMPLATES_DIR):
    TEMPLATES_DIR = os.path.join(APP_DIR, "_internal", "templates")

STATIC_DIR = os.path.join(APP_DIR, "static")
if not os.path.exists(STATIC_DIR):
    STATIC_DIR = os.path.join(APP_DIR, "_internal", "static")

# Persistent data folder (db/logs live here)
DATA_DIR = os.path.join(APP_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

# SQLite path (portable)
DB_PATH = os.path.join(DATA_DIR, "database.db")

# Schema file (we will ship it inside dist as /database/schema.sql)
SCHEMA_PATH = os.path.join(APP_DIR, "database", "schema.sql")
if not os.path.exists(SCHEMA_PATH):
    SCHEMA_PATH = os.path.join(APP_DIR, "_internal", "database", "schema.sql")
