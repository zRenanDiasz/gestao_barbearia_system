from database.db import get_db


def _to_int(v, field):
    try:
        return int(v)
    except Exception:
        raise ValueError(f"{field} inválido")


def _to_float(v, field):
    try:
        return float(v)
    except Exception:
        raise ValueError(f"{field} inválido")


def listar_servicos(q=None, categoria=None, status=None):
    """
    status:
      - None => só ativos (compatível com comportamento atual)
      - 'ativo' => só ativos
      - 'inativo' => só inativos
      - 'todos' => todos
    """
    db = get_db()

    q = (q or "").strip()
    categoria = (categoria or "").strip()
    status = (status or "").strip().lower() or None

    where = []
    params = []

    if status in (None, "", "ativo"):
        where.append("s.ativo = 1")
    elif status == "inativo":
        where.append("s.ativo = 0")
    elif status == "todos":
        pass
    else:
        raise ValueError("status inválido (use: ativo, inativo, todos)")

    if q:
        where.append("(s.nome LIKE ? OR COALESCE(s.descricao,'') LIKE ?)")
        params.extend([f"%{q}%", f"%{q}%"])

    if categoria:
        where.append("COALESCE(s.categoria,'') = ?")
        params.append(categoria)

    sql = """
        SELECT
            s.id,
            s.nome,
            s.categoria,
            s.descricao,
            s.duracao,
            s.preco,
            s.ativo
        FROM servicos s
    """

    if where:
        sql += " WHERE " + " AND ".join(where)

    sql += " ORDER BY s.nome"

    return db.execute(sql, tuple(params)).fetchall()


def buscar_servico_por_id(servico_id: int):
    db = get_db()
    servico_id = _to_int(servico_id, "servico_id")

    return db.execute(
        """
        SELECT id, nome, categoria, descricao, duracao, preco, ativo
        FROM servicos
        WHERE id = ?
        """,
        (servico_id,),
    ).fetchone()


def criar_servico(nome, duracao, preco, categoria=None, descricao=None, ativo=1):
    db = get_db()

    nome = (nome or "").strip()
    if not nome:
        raise ValueError("nome é obrigatório")

    duracao = _to_int(duracao, "duracao")
    if duracao <= 0:
        raise ValueError("duracao deve ser maior que 0")

    preco = _to_float(preco, "preco")
    if preco < 0:
        raise ValueError("preco não pode ser negativo")

    categoria = (categoria or "").strip() or None
    descricao = (descricao or "").strip() or None

    ativo = _to_int(ativo, "ativo")
    if ativo not in (0, 1):
        raise ValueError("ativo inválido (use 0 ou 1)")

    dup = db.execute(
        "SELECT id FROM servicos WHERE lower(nome) = lower(?)",
        (nome,),
    ).fetchone()
    if dup:
        raise ValueError("Já existe um serviço com esse nome")

    cur = db.execute(
        """
        INSERT INTO servicos (nome, categoria, descricao, duracao, preco, ativo)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (nome, categoria, descricao, duracao, preco, ativo),
    )
    db.commit()
    return cur.lastrowid


def atualizar_servico(servico_id, nome, duracao, preco, categoria=None, descricao=None, ativo=1) -> bool:
    db = get_db()
    servico_id = _to_int(servico_id, "servico_id")

    nome = (nome or "").strip()
    if not nome:
        raise ValueError("nome é obrigatório")

    duracao = _to_int(duracao, "duracao")
    if duracao <= 0:
        raise ValueError("duracao deve ser maior que 0")

    preco = _to_float(preco, "preco")
    if preco < 0:
        raise ValueError("preco não pode ser negativo")

    categoria = (categoria or "").strip() or None
    descricao = (descricao or "").strip() or None

    ativo = _to_int(ativo, "ativo")
    if ativo not in (0, 1):
        raise ValueError("ativo inválido (use 0 ou 1)")

    existe = db.execute(
        "SELECT id FROM servicos WHERE id = ?",
        (servico_id,),
    ).fetchone()
    if not existe:
        return False

    dup = db.execute(
        "SELECT id FROM servicos WHERE lower(nome) = lower(?) AND id <> ?",
        (nome, servico_id),
    ).fetchone()
    if dup:
        raise ValueError("Já existe um serviço com esse nome")

    cur = db.execute(
        """
        UPDATE servicos
        SET nome = ?, categoria = ?, descricao = ?, duracao = ?, preco = ?, ativo = ?
        WHERE id = ?
        """,
        (nome, categoria, descricao, duracao, preco, ativo, servico_id),
    )
    db.commit()
    return cur.rowcount > 0


def set_servico_ativo(servico_id: int, ativo: int) -> bool:
    db = get_db()
    servico_id = _to_int(servico_id, "servico_id")
    ativo = _to_int(ativo, "ativo")

    if ativo not in (0, 1):
        raise ValueError("ativo inválido (use 0 ou 1)")

    cur = db.execute(
        "UPDATE servicos SET ativo = ? WHERE id = ?",
        (ativo, servico_id),
    )
    db.commit()
    return cur.rowcount > 0


def excluir_servico(servico_id: int) -> bool:
    db = get_db()
    servico_id = _to_int(servico_id, "servico_id")

    row = db.execute(
        """
        SELECT COUNT(1) AS qtd
        FROM agendamentos
        WHERE servico_id = ?
        """,
        (servico_id,),
    ).fetchone()

    qtd = int(row["qtd"] or 0)
    if qtd > 0:
        raise ValueError("SERVICO_COM_HISTORICO")

    cur = db.execute("DELETE FROM servicos WHERE id = ?", (servico_id,))
    db.commit()
    return cur.rowcount > 0


def kpis_servicos():
    db = get_db()

    total = db.execute("SELECT COUNT(1) AS n FROM servicos").fetchone()["n"]
    ativos = db.execute(
        "SELECT COUNT(1) AS n FROM servicos WHERE ativo = 1"
    ).fetchone()["n"]
    inativos = db.execute(
        "SELECT COUNT(1) AS n FROM servicos WHERE ativo = 0"
    ).fetchone()["n"]

    cats = db.execute(
        """
        SELECT COALESCE(categoria,'') AS categoria, COUNT(1) AS total
        FROM servicos
        GROUP BY COALESCE(categoria,'')
        ORDER BY total DESC
        """
    ).fetchall()

    categorias = [dict(c) for c in cats if (
        c["categoria"] or "").strip() != ""]

    row_top = db.execute(
        """
        SELECT
            s.nome AS nome,
            COUNT(1) AS qtd
        FROM movimentacoes_caixa mc
        JOIN servicos s ON s.id = mc.servico_id
        WHERE mc.tipo = 'entrada'
          AND mc.status = 'pago'
          AND mc.agendamento_id IS NOT NULL
          AND mc.servico_id IS NOT NULL
          AND substr(mc.data_hora, 1, 7) = substr(date('now'), 1, 7)
        GROUP BY s.id, s.nome
        ORDER BY qtd DESC, s.nome ASC
        LIMIT 1
        """
    ).fetchone()

    mais_vendido = None
    if row_top:
        mais_vendido = {
            "nome": row_top["nome"],
            "qtd": int(row_top["qtd"] or 0)
        }

    return {
        "total": int(total or 0),
        "ativos": int(ativos or 0),
        "inativos": int(inativos or 0),
        "categorias": categorias,
        "mais_vendido": mais_vendido,
    }
