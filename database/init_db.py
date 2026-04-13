import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "instance", "database.db")
SCHEMA_PATH = os.path.join(BASE_DIR, "database", "schema.sql")


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    conn = sqlite3.connect(DB_PATH)

    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        conn.executescript(f.read())

    conn.commit()
    conn.close()

    print("Banco de dados criado com sucesso.")


def adicionar_coluna_ativo_servicos():
    import sqlite3
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute("PRAGMA table_info(servicos)")
    colunas = [col[1] for col in cursor.fetchall()]

    if "ativo" not in colunas:
        conn.execute("ALTER TABLE servicos ADD COLUMN ativo INTEGER DEFAULT 1")
        conn.commit()
        print("Coluna 'ativo' adicionada com sucesso!")
    else:
        print("Coluna 'ativo' já existe, nada a fazer.")

    conn.close()


if __name__ == "__main__":
    init_db()
    adicionar_coluna_ativo_servicos()
