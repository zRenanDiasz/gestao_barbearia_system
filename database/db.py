import sqlite3
from flask import g
from config import DB_PATH


def get_db():
    if "db" not in g:
        # timeout: espera até 10s se o banco estiver ocupado
        g.db = sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False)
        g.db.row_factory = sqlite3.Row

        # recomendações para estabilidade/concorrrência no SQLite
        g.db.execute("PRAGMA foreign_keys = ON;")
        g.db.execute("PRAGMA journal_mode = WAL;")
        g.db.execute("PRAGMA busy_timeout = 10000;")  # 10s

    return g.db


def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()
