from database.db import get_db

JANELA_INATIVIDADE_DIAS = 60


def listar_clientes():
    db = get_db()

    rows = db.execute(f"""
        WITH stats AS (
            SELECT
                c.id,
                c.nome,
                c.telefone,
                c.criado_em,

                COALESCE(SUM(
                    CASE
                      WHEN lower(a.status) IN ('concluido','concluído') THEN 1
                      ELSE 0
                    END
                ), 0) AS total_visitas,

                MAX(
                    CASE
                      WHEN lower(a.status) IN ('concluido','concluído') THEN substr(a.data, 1, 10)
                      ELSE NULL
                    END
                ) AS ultima_visita

            FROM clientes c
            LEFT JOIN agendamentos a ON a.cliente_id = c.id
            GROUP BY c.id, c.nome, c.telefone, c.criado_em
        )
        SELECT
            id,
            nome,
            telefone,
            criado_em,
            total_visitas,
            ultima_visita,
            CASE
              WHEN ultima_visita IS NOT NULL
               AND date(ultima_visita) >= date('now', '-{JANELA_INATIVIDADE_DIAS} day')
                THEN 'ativo'
              ELSE 'inativo'
            END AS status_cliente
        FROM stats
        ORDER BY nome
    """).fetchall()

    return rows


def buscar_cliente_por_telefone(telefone: str):
    telefone = (telefone or "").strip()
    if not telefone:
        raise ValueError("telefone é obrigatório")

    db = get_db()
    row = db.execute(
        "SELECT id, nome, telefone, criado_em FROM clientes WHERE telefone = ?",
        (telefone,)
    ).fetchone()
    return row


def criar_cliente(nome, telefone, observacoes=None):
    db = get_db()

    nome = (nome or "").strip()
    telefone = (telefone or "").strip()

    if not nome:
        raise ValueError("nome é obrigatório")
    if not telefone:
        raise ValueError("telefone é obrigatório")

    existente = db.execute(
        "SELECT id FROM clientes WHERE telefone = ?",
        (telefone,)
    ).fetchone()

    if existente:
        raise ValueError("Já existe um cliente com esse telefone")

    cur = db.execute(
        """
        INSERT INTO clientes (nome, telefone, observacoes, criado_em)
        VALUES (?, ?, ?, datetime('now'))
        """,
        (nome, telefone, observacoes)
    )
    db.commit()
    return cur.lastrowid


def atualizar_cliente(cliente_id: int, nome: str, telefone: str, observacoes=None) -> bool:
    try:
        cliente_id = int(cliente_id)
    except Exception:
        raise ValueError("cliente_id inválido")

    nome = (nome or "").strip()
    telefone = (telefone or "").strip()

    if not nome:
        raise ValueError("nome é obrigatório")
    if not telefone:
        raise ValueError("telefone é obrigatório")

    db = get_db()

    existe = db.execute(
        "SELECT id FROM clientes WHERE id = ?", (cliente_id,)
    ).fetchone()
    if not existe:
        return False

    dup = db.execute(
        "SELECT id FROM clientes WHERE telefone = ? AND id <> ?",
        (telefone, cliente_id)
    ).fetchone()
    if dup:
        raise ValueError("Já existe um cliente com esse telefone")

    cur = db.execute(
        """
        UPDATE clientes
        SET nome = ?, telefone = ?, observacoes = ?
        WHERE id = ?
        """,
        (nome, telefone, observacoes, cliente_id)
    )
    db.commit()
    return cur.rowcount > 0


def excluir_cliente(cliente_id: int):
    db = get_db()

    row = db.execute("""
        SELECT COUNT(1) AS qtd
        FROM agendamentos
        WHERE cliente_id = ?
    """, (cliente_id,)).fetchone()

    qtd = int(row["qtd"] or 0)

    if qtd > 0:
        raise ValueError("CLIENTE_COM_HISTORICO")

    cur = db.execute("DELETE FROM clientes WHERE id = ?", (cliente_id,))
    db.commit()
    return cur.rowcount > 0
