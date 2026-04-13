import sqlite3
from flask import current_app
from database.db import get_db


# ==========================================================
# Helpers
# ==========================================================
def _connect():
    db_path = current_app.config.get(
        "DATABASE") or current_app.config.get("DB_PATH")
    if not db_path:
        raise RuntimeError(
            "Config do banco não encontrada. Use current_app.config['DATABASE']."
        )

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def _table_exists(conn, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
        (table_name,),
    ).fetchone()
    return row is not None


def _columns(conn, table_name: str) -> set:
    if not _table_exists(conn, table_name):
        return set()
    cols = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {c["name"] for c in cols}


# ==========================================================
# BLOQUEIOS
# ==========================================================
def ensure_bloqueios_dia_inteiro_column():
    db = get_db()
    cols = db.execute("PRAGMA table_info(bloqueios)").fetchall()
    nomes = {c["name"] for c in cols}

    if "dia_inteiro" in nomes:
        return

    db.execute("ALTER TABLE bloqueios ADD COLUMN dia_inteiro INTEGER")
    db.execute("UPDATE bloqueios SET dia_inteiro = 1 WHERE dia_inteiro IS NULL")
    db.commit()


# ==========================================================
# SERVIÇOS
# ==========================================================
def ensure_servicos_ativo_column():
    conn = _connect()
    try:
        if not _table_exists(conn, "servicos"):
            return

        col_names = _columns(conn, "servicos")
        if "ativo" not in col_names:
            conn.execute(
                "ALTER TABLE servicos ADD COLUMN ativo INTEGER NOT NULL DEFAULT 1"
            )
            conn.commit()
    finally:
        conn.close()


def ensure_servicos_extra_columns():
    conn = _connect()
    try:
        if not _table_exists(conn, "servicos"):
            return

        col_names = _columns(conn, "servicos")

        if "categoria" not in col_names:
            conn.execute("ALTER TABLE servicos ADD COLUMN categoria TEXT")
        if "descricao" not in col_names:
            conn.execute("ALTER TABLE servicos ADD COLUMN descricao TEXT")

        conn.commit()
    finally:
        conn.close()


# ==========================================================
# CAIXA
# ==========================================================
def ensure_movimentacoes_caixa_table():
    """
    Cria a tabela no formato atual.
    Regras:
    - forma_pagamento aceita 'plano'
    - valor aceita 0 (a regra fina fica no service)
    """
    conn = _connect()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS movimentacoes_caixa (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tipo TEXT NOT NULL CHECK (tipo IN ('entrada', 'saida')),
                forma_pagamento TEXT NOT NULL CHECK (
                    forma_pagamento IN ('dinheiro', 'pix', 'debito', 'credito', 'plano')
                ),
                valor REAL NOT NULL CHECK (valor >= 0),
                data_hora TEXT NOT NULL,
                descricao TEXT,
                agendamento_id INTEGER,
                profissional_id INTEGER,
                servico_id INTEGER,
                status TEXT NOT NULL DEFAULT 'pendente' CHECK (status IN ('pago','pendente','cancelado')),
                comissao_valor REAL NOT NULL DEFAULT 0,
                criado_em TEXT NOT NULL DEFAULT (datetime('now'))
            );
            """
        )
        conn.commit()
    finally:
        conn.close()


def ensure_movimentacoes_caixa_status_column():
    conn = _connect()
    try:
        if not _table_exists(conn, "movimentacoes_caixa"):
            return

        col_names = _columns(conn, "movimentacoes_caixa")
        if "status" not in col_names:
            conn.execute(
                "ALTER TABLE movimentacoes_caixa ADD COLUMN status TEXT")
            conn.execute(
                "UPDATE movimentacoes_caixa SET status = 'pendente' WHERE status IS NULL"
            )
            conn.commit()
    finally:
        conn.close()


def ensure_movimentacoes_caixa_comissao_column():
    conn = _connect()
    try:
        if not _table_exists(conn, "movimentacoes_caixa"):
            return

        col_names = _columns(conn, "movimentacoes_caixa")
        if "comissao_valor" not in col_names:
            conn.execute(
                "ALTER TABLE movimentacoes_caixa ADD COLUMN comissao_valor REAL NOT NULL DEFAULT 0"
            )
            conn.execute(
                "UPDATE movimentacoes_caixa SET comissao_valor = 0 WHERE comissao_valor IS NULL"
            )
            conn.commit()
    finally:
        conn.close()


def ensure_movimentacoes_caixa_planos_rules():
    """
    SQLite não permite alterar CHECK de tabela existente.
    Então, se a tabela antiga ainda bloquear:
      - forma_pagamento = 'plano'
      - valor = 0
    reconstruímos a tabela preservando os dados.
    """
    conn = _connect()
    try:
        if not _table_exists(conn, "movimentacoes_caixa"):
            return

        row = conn.execute(
            """
            SELECT sql
            FROM sqlite_master
            WHERE type = 'table' AND name = 'movimentacoes_caixa'
            """
        ).fetchone()

        create_sql = (row["sql"] or "").lower() if row else ""

        precisa_rebuild = False

        if "'plano'" not in create_sql:
            precisa_rebuild = True

        if "check (valor > 0)" in create_sql:
            precisa_rebuild = True

        if not precisa_rebuild:
            return

        conn.execute("PRAGMA foreign_keys = OFF;")
        conn.execute("BEGIN")

        conn.execute(
            """
            CREATE TABLE movimentacoes_caixa_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tipo TEXT NOT NULL CHECK (tipo IN ('entrada', 'saida')),
                forma_pagamento TEXT NOT NULL CHECK (
                    forma_pagamento IN ('dinheiro', 'pix', 'debito', 'credito', 'plano')
                ),
                valor REAL NOT NULL CHECK (valor >= 0),
                data_hora TEXT NOT NULL,
                descricao TEXT,
                agendamento_id INTEGER,
                profissional_id INTEGER,
                servico_id INTEGER,
                status TEXT NOT NULL DEFAULT 'pendente' CHECK (status IN ('pago','pendente','cancelado')),
                comissao_valor REAL NOT NULL DEFAULT 0,
                criado_em TEXT NOT NULL DEFAULT (datetime('now'))
            );
            """
        )

        cols = _columns(conn, "movimentacoes_caixa")

        has_status = "status" in cols
        has_comissao = "comissao_valor" in cols
        has_criado_em = "criado_em" in cols
        has_servico_id = "servico_id" in cols

        conn.execute(
            f"""
            INSERT INTO movimentacoes_caixa_new
                (id, tipo, forma_pagamento, valor, data_hora, descricao,
                 agendamento_id, profissional_id, servico_id, status, comissao_valor, criado_em)
            SELECT
                id,
                tipo,
                forma_pagamento,
                valor,
                data_hora,
                descricao,
                agendamento_id,
                profissional_id,
                {"servico_id" if has_servico_id else "NULL AS servico_id"},
                {"status" if has_status else "'pendente' AS status"},
                {"comissao_valor" if has_comissao else "0 AS comissao_valor"},
                {"criado_em" if has_criado_em else "datetime('now') AS criado_em"}
            FROM movimentacoes_caixa
            """
        )

        conn.execute("DROP TABLE movimentacoes_caixa")
        conn.execute(
            "ALTER TABLE movimentacoes_caixa_new RENAME TO movimentacoes_caixa")

        conn.commit()
        conn.execute("PRAGMA foreign_keys = ON;")

    except Exception:
        conn.execute("ROLLBACK")
        conn.execute("PRAGMA foreign_keys = ON;")
        raise

    finally:
        conn.close()


def ensure_vendas_produtos_table():
    conn = _connect()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS vendas_produtos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                movimentacao_id INTEGER NOT NULL,
                produto_id INTEGER NOT NULL,
                nome TEXT NOT NULL,
                quantidade INTEGER NOT NULL CHECK (quantidade > 0),
                preco_unit REAL NOT NULL CHECK (preco_unit >= 0),
                subtotal REAL NOT NULL CHECK (subtotal >= 0),
                criado_em TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (movimentacao_id) REFERENCES movimentacoes_caixa(id),
                FOREIGN KEY (produto_id) REFERENCES produtos(id)
            );
            """
        )
        conn.commit()
    finally:
        conn.close()


# ==========================================================
# PROFISSIONAIS / COMISSÕES
# ==========================================================
def ensure_profissionais_comissao_columns():
    conn = _connect()
    try:
        if not _table_exists(conn, "profissionais"):
            return

        col_names = _columns(conn, "profissionais")

        if "tipo_comissao" not in col_names:
            conn.execute(
                "ALTER TABLE profissionais ADD COLUMN tipo_comissao TEXT DEFAULT 'percentual'"
            )
        if "valor_comissao" not in col_names:
            conn.execute(
                "ALTER TABLE profissionais ADD COLUMN valor_comissao REAL DEFAULT 0"
            )

        conn.commit()
    finally:
        conn.close()


def ensure_comissoes_profissionais_table():
    conn = _connect()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS comissoes_profissionais (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profissional_id INTEGER NOT NULL,
                tipo_comissao TEXT NOT NULL CHECK (tipo_comissao IN ('percentual', 'fixo')),
                valor_comissao REAL NOT NULL CHECK (valor_comissao >= 0),
                vigente_desde TEXT NOT NULL,
                criado_em TEXT NOT NULL DEFAULT (datetime('now'))
            );
            """
        )
        conn.commit()
    finally:
        conn.close()


def ensure_profissionais_agenda_columns():
    conn = _connect()
    try:
        if not _table_exists(conn, "profissionais"):
            return

        col_names = _columns(conn, "profissionais")

        if "telefone" not in col_names:
            conn.execute("ALTER TABLE profissionais ADD COLUMN telefone TEXT")
        if "dias_trabalho" not in col_names:
            conn.execute(
                "ALTER TABLE profissionais ADD COLUMN dias_trabalho TEXT")
        if "hora_inicio" not in col_names:
            conn.execute(
                "ALTER TABLE profissionais ADD COLUMN hora_inicio TEXT")
        if "hora_fim" not in col_names:
            conn.execute("ALTER TABLE profissionais ADD COLUMN hora_fim TEXT")
        if "ativo" not in col_names:
            conn.execute(
                "ALTER TABLE profissionais ADD COLUMN ativo INTEGER NOT NULL DEFAULT 1"
            )

        conn.commit()
    finally:
        conn.close()


# ==========================================================
# ESTOQUE
# ==========================================================
def ensure_estoque_tables():
    conn = _connect()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS produtos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                preco_venda REAL DEFAULT 0,
                estoque_atual INTEGER NOT NULL DEFAULT 0 CHECK (estoque_atual >= 0),
                estoque_minimo INTEGER NOT NULL DEFAULT 0 CHECK (estoque_minimo >= 0),
                ativo INTEGER NOT NULL DEFAULT 1 CHECK (ativo IN (0,1)),
                criado_em TEXT NOT NULL DEFAULT (datetime('now'))
            );
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS movimentacoes_estoque (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                produto_id INTEGER NOT NULL,
                tipo TEXT NOT NULL CHECK (tipo IN ('entrada', 'saida')),
                quantidade INTEGER NOT NULL CHECK (quantidade > 0),
                data_hora TEXT NOT NULL,
                descricao TEXT,
                criado_em TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (produto_id) REFERENCES produtos(id)
            );
            """
        )

        conn.commit()
    finally:
        conn.close()


def ensure_produtos_extra_columns():
    conn = _connect()
    try:
        if not _table_exists(conn, "produtos"):
            return

        col_names = _columns(conn, "produtos")

        if "categoria" not in col_names:
            conn.execute("ALTER TABLE produtos ADD COLUMN categoria TEXT")
        if "marca" not in col_names:
            conn.execute("ALTER TABLE produtos ADD COLUMN marca TEXT")
        if "preco_custo" not in col_names:
            conn.execute("ALTER TABLE produtos ADD COLUMN preco_custo REAL")
            conn.execute(
                "UPDATE produtos SET preco_custo = 0 WHERE preco_custo IS NULL"
            )

        conn.commit()
    finally:
        conn.close()


# ==========================================================
# CLIENTES
# ==========================================================
def ensure_clientes_criado_em_column():
    conn = _connect()
    try:
        if not _table_exists(conn, "clientes"):
            return

        col_names = _columns(conn, "clientes")

        if "criado_em" not in col_names:
            conn.execute("ALTER TABLE clientes ADD COLUMN criado_em TEXT")
            conn.execute(
                "UPDATE clientes SET criado_em = datetime('now') WHERE criado_em IS NULL"
            )
            conn.commit()
    finally:
        conn.close()


# ==========================================================
# PLANOS
# ==========================================================
def ensure_planos_tables():
    conn = _connect()
    try:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS planos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            valor_mensal REAL NOT NULL,
            usos_por_mes INTEGER NOT NULL,
            ativo INTEGER NOT NULL DEFAULT 1,
            criado_em TEXT DEFAULT (datetime('now'))
        );
        """)

        conn.execute("""
        CREATE TABLE IF NOT EXISTS planos_servicos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plano_id INTEGER NOT NULL,
            servico_id INTEGER NOT NULL,
            FOREIGN KEY (plano_id) REFERENCES planos(id),
            FOREIGN KEY (servico_id) REFERENCES servicos(id)
        );
        """)

        conn.execute("""
        CREATE TABLE IF NOT EXISTS clientes_planos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_id INTEGER NOT NULL,
            plano_id INTEGER NOT NULL,
            data_inicio TEXT,
            proximo_vencimento TEXT,
            usos_totais INTEGER NOT NULL,
            usos_restantes INTEGER NOT NULL,
            forma_pagamento TEXT,
            status TEXT NOT NULL CHECK (
                status IN ('ativo','aguardando_pagamento','atrasado','cancelado')
            ),
            criado_em TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (cliente_id) REFERENCES clientes(id),
            FOREIGN KEY (plano_id) REFERENCES planos(id)
        );
        """)

        conn.execute("""
        CREATE TABLE IF NOT EXISTS clientes_planos_usos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_plano_id INTEGER NOT NULL,
            agendamento_id INTEGER,
            data_uso TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (cliente_plano_id) REFERENCES clientes_planos(id),
            FOREIGN KEY (agendamento_id) REFERENCES agendamentos(id)
        );
        """)

        conn.commit()

    finally:
        conn.close()


# ==========================================================
# CONFIGURAÇÕES (GERAL + HORÁRIOS)
# ==========================================================
def ensure_configuracoes_tables():
    conn = _connect()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS configuracoes_geral (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                nome TEXT DEFAULT '',
                telefone TEXT DEFAULT '',
                endereco TEXT DEFAULT '',
                email TEXT DEFAULT '',
                cnpj TEXT DEFAULT '',
                atualizado_em TEXT DEFAULT (datetime('now'))
            );
            """
        )
        conn.execute(
            "INSERT OR IGNORE INTO configuracoes_geral (id) VALUES (1);")

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS configuracoes_horarios (
                dia_semana INTEGER NOT NULL CHECK (dia_semana BETWEEN 0 AND 6),
                aberto INTEGER NOT NULL DEFAULT 1 CHECK (aberto IN (0,1)),
                hora_inicio TEXT NOT NULL DEFAULT '09:00',
                hora_fim TEXT NOT NULL DEFAULT '19:00',
                atualizado_em TEXT DEFAULT (datetime('now')),
                PRIMARY KEY (dia_semana)
            );
            """
        )

        for d in range(7):
            aberto = 0 if d == 0 else 1
            conn.execute(
                """
                INSERT OR IGNORE INTO configuracoes_horarios
                    (dia_semana, aberto, hora_inicio, hora_fim)
                VALUES
                    (?, ?, '09:00', '19:00');
                """,
                (d, aberto),
            )

        conn.commit()
    finally:
        conn.close()


# ==========================================================
# ORQUESTRADOR
# ==========================================================
def run_all_migrations():
    ensure_bloqueios_dia_inteiro_column()

    ensure_servicos_ativo_column()
    ensure_servicos_extra_columns()

    ensure_movimentacoes_caixa_table()
    ensure_movimentacoes_caixa_status_column()
    ensure_movimentacoes_caixa_comissao_column()
    ensure_movimentacoes_caixa_planos_rules()
    ensure_vendas_produtos_table()

    ensure_profissionais_agenda_columns()
    ensure_profissionais_comissao_columns()
    ensure_comissoes_profissionais_table()

    ensure_estoque_tables()
    ensure_produtos_extra_columns()

    ensure_clientes_criado_em_column()

    ensure_planos_tables()

    ensure_configuracoes_tables()
