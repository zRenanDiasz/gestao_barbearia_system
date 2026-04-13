from datetime import datetime

from database.db import get_db


# =============================================================================
# Constantes operacionais do caixa
# =============================================================================
FORMAS_VALIDAS = {"dinheiro", "pix", "debito", "credito", "plano"}
TIPOS_VALIDOS = {"entrada", "saida"}
STATUS_VALIDOS = {"pago", "pendente", "cancelado"}
STATUS_MOV_VALIDOS = {"pago", "pendente", "cancelado"}


# =============================================================================
# Helpers internos
# =============================================================================
def _normalizar_texto(valor, default=""):
    return (valor or default).strip().lower()


def _parse_float(valor, campo="valor"):
    try:
        return float(valor)
    except Exception:
        raise ValueError(f"{campo} inválido")


def _parse_int_opcional(valor, campo="id"):
    if valor is None:
        return None
    try:
        return int(valor)
    except Exception:
        raise ValueError(f"{campo} inválido")


def _validar_data_hora_iso(valor, campo="data_hora"):
    texto = (valor or "").strip()
    if not texto:
        raise ValueError(f"{campo} é obrigatória (YYYY-MM-DD HH:MM:SS ou ISO)")

    try:
        return datetime.fromisoformat(texto).isoformat(timespec="seconds")
    except Exception:
        raise ValueError(f"{campo} inválida")


def _is_movimentacao_plano(tipo: str, forma_pagamento: str, valor: float) -> bool:
    return (
        _normalizar_texto(tipo) == "entrada"
        and _normalizar_texto(forma_pagamento) == "plano"
        and float(valor) == 0.0
    )


# =============================================================================
# Criação de movimentação de caixa
# Responsável por registrar entradas e saídas no financeiro
# =============================================================================
def criar_movimentacao_caixa(
    tipo: str,
    forma_pagamento: str,
    valor: float,
    data_hora: str,
    descricao: str = None,
    agendamento_id: int = None,
    profissional_id: int = None,
    servico_id: int = None,
    status: str = "pendente",
    comissao_valor: float = 0.0,
    commit: bool = True,
):
    tipo = _normalizar_texto(tipo)
    if tipo not in TIPOS_VALIDOS:
        raise ValueError("tipo inválido (use 'entrada' ou 'saida')")

    forma_pagamento = _normalizar_texto(forma_pagamento)
    if forma_pagamento not in FORMAS_VALIDAS:
        raise ValueError(
            "forma_pagamento inválida (dinheiro, pix, debito, credito, plano)"
        )

    valor = _parse_float(valor, "valor")
    mov_plano = _is_movimentacao_plano(tipo, forma_pagamento, valor)

    if mov_plano:
        if valor != 0:
            raise ValueError(
                "Movimentação de plano deve ter valor igual a zero")
    else:
        if valor <= 0:
            raise ValueError("valor deve ser maior que zero")

    data_hora = _validar_data_hora_iso(data_hora, "data_hora")

    status = _normalizar_texto(status)
    if status not in STATUS_VALIDOS:
        raise ValueError("status inválido (pago, pendente, cancelado)")

    comissao_valor = _parse_float(comissao_valor or 0, "comissao_valor")
    if comissao_valor < 0:
        raise ValueError("comissao_valor não pode ser negativo")

    agendamento_id = _parse_int_opcional(agendamento_id, "agendamento_id")
    profissional_id = _parse_int_opcional(profissional_id, "profissional_id")
    servico_id = _parse_int_opcional(servico_id, "servico_id")

    descricao = (descricao or "").strip() or None

    db = get_db()
    cursor = db.execute(
        """
        INSERT INTO movimentacoes_caixa
            (
                tipo,
                forma_pagamento,
                valor,
                data_hora,
                descricao,
                agendamento_id,
                profissional_id,
                servico_id,
                status,
                comissao_valor
            )
        VALUES
            (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            tipo,
            forma_pagamento,
            valor,
            data_hora,
            descricao,
            agendamento_id,
            profissional_id,
            servico_id,
            status,
            comissao_valor,
        ),
    )

    if commit:
        db.commit()

    return cursor.lastrowid


# =============================================================================
# Listagem de movimentações
# Inclui produtos vinculados e comissão gravada
# =============================================================================
def listar_movimentacoes_caixa(data=None, inicio=None, fim=None, profissional_id=None):
    """
    Retorna movimentações:
    - por dia: data=YYYY-MM-DD
    - por período: inicio=YYYY-MM-DD e fim=YYYY-MM-DD (inclusive)
    Filtro opcional: profissional_id

    Inclui:
      - comissao_valor
      - produtos (texto agregado de vendas_produtos por movimentacao_id)
    """
    db = get_db()

    where = []
    params = []

    if data:
        where.append("date(mc.data_hora) = date(?)")
        params.append(data)
    elif inicio and fim:
        where.append("date(mc.data_hora) >= date(?)")
        params.append(inicio)
        where.append("date(mc.data_hora) <= date(?)")
        params.append(fim)

    if profissional_id:
        where.append("mc.profissional_id = ?")
        params.append(int(profissional_id))

    where_sql = ""
    if where:
        where_sql = "WHERE " + " AND ".join(where)

    rows = db.execute(
        f"""
        SELECT
            mc.id,
            mc.tipo,
            mc.forma_pagamento,
            mc.valor,
            mc.data_hora,
            mc.descricao,
            mc.status,
            mc.agendamento_id,
            mc.profissional_id,
            mc.servico_id,
            mc.criado_em,
            COALESCE(mc.comissao_valor, 0) AS comissao_valor,
            COALESCE((
                SELECT GROUP_CONCAT(vp.nome || ' x' || vp.quantidade, ', ')
                FROM vendas_produtos vp
                WHERE vp.movimentacao_id = mc.id
            ), '') AS produtos
        FROM movimentacoes_caixa mc
        {where_sql}
        ORDER BY mc.id DESC
        LIMIT 500
        """,
        tuple(params),
    ).fetchall()

    out = []
    for r in rows:
        d = dict(r)
        prod = (d.get("produtos") or "").strip()
        d["produtos"] = f"Produtos: {prod}" if prod else ""
        out.append(d)

    return out


# =============================================================================
# Fechamento de caixa por data
# Considera apenas movimentações efetivamente pagas para o saldo operacional
# =============================================================================
def fechamento_caixa_por_data(data: str):
    db = get_db()

    totais = db.execute(
        """
        SELECT
            COALESCE(SUM(CASE WHEN tipo = 'entrada' AND status = 'pago' THEN valor END), 0) AS total_entradas,
            COALESCE(SUM(CASE WHEN tipo = 'saida' AND status = 'pago' THEN valor END), 0) AS total_saidas
        FROM movimentacoes_caixa
        WHERE date(data_hora) = date(?)
        """,
        (data,),
    ).fetchone()

    por_forma = db.execute(
        """
        SELECT
            forma_pagamento,
            tipo,
            COALESCE(SUM(valor), 0) AS total
        FROM movimentacoes_caixa
        WHERE date(data_hora) = date(?)
          AND status = 'pago'
        GROUP BY forma_pagamento, tipo
        ORDER BY forma_pagamento, tipo
        """,
        (data,),
    ).fetchall()

    total_entradas = float(totais["total_entradas"] or 0)
    total_saidas = float(totais["total_saidas"] or 0)
    saldo = total_entradas - total_saidas

    formas = {}
    for row in por_forma:
        fp = row["forma_pagamento"]
        tp = row["tipo"]
        if fp not in formas:
            formas[fp] = {"entrada": 0.0, "saida": 0.0}
        formas[fp][tp] = float(row["total"] or 0)

    return {
        "data": data,
        "total_entradas": total_entradas,
        "total_saidas": total_saidas,
        "saldo": saldo,
        "por_forma_pagamento": formas,
    }


# =============================================================================
# Verificações auxiliares
# =============================================================================
def agendamento_ja_pago(agendamento_id: int) -> bool:
    db = get_db()
    row = db.execute(
        """
        SELECT 1
        FROM movimentacoes_caixa
        WHERE agendamento_id = ?
          AND tipo = 'entrada'
          AND status != 'cancelado'
        LIMIT 1
        """,
        (agendamento_id,),
    ).fetchone()
    return row is not None


def atualizar_status_movimentacao(mov_id: int, novo_status: str) -> bool:
    novo_status = _normalizar_texto(novo_status)
    if novo_status not in STATUS_MOV_VALIDOS:
        raise ValueError("status inválido (use: pago, pendente, cancelado)")

    db = get_db()
    cur = db.execute(
        """
        UPDATE movimentacoes_caixa
        SET status = ?
        WHERE id = ?
        """,
        (novo_status, mov_id),
    )
    db.commit()
    return cur.rowcount > 0


def movimentacao_vinculada_agendamento(mov_id: int) -> bool:
    db = get_db()
    row = db.execute(
        """
        SELECT agendamento_id
        FROM movimentacoes_caixa
        WHERE id = ?
        """,
        (mov_id,),
    ).fetchone()

    if not row:
        raise ValueError("Movimentação não encontrada")

    return row["agendamento_id"] is not None


def atualizar_status_movimentacao_restrito(mov_id: int, novo_status: str) -> bool:
    """
    Regra operacional:
    - Se movimentação é vinculada a agendamento: permite apenas 'cancelado'
    - Caso contrário: permite pago/pendente/cancelado
    """
    novo_status = _normalizar_texto(novo_status)
    validos = {"pago", "pendente", "cancelado"}

    if novo_status not in validos:
        raise ValueError("status inválido (use: pago, pendente, cancelado)")

    if movimentacao_vinculada_agendamento(mov_id):
        if novo_status != "cancelado":
            raise ValueError(
                "Movimentação de agendamento: status não pode ser alterado (apenas cancelado)."
            )

    return atualizar_status_movimentacao(mov_id, novo_status)


# =============================================================================
# Comissão
# Compatível com histórico por data e fallback no cadastro do profissional
# =============================================================================
def obter_comissao_vigente(db, profissional_id: int, data_ref: str):
    """
    Retorna a regra vigente de comissão.

    Prioridade:
    1) comissoes_profissionais (vigente_desde <= data_ref)
    2) fallback em profissionais (tipo_comissao/valor_comissao)

    Retorno: row-like com chaves: tipo_comissao, valor_comissao
    """
    row = db.execute(
        """
        SELECT tipo_comissao, valor_comissao
        FROM comissoes_profissionais
        WHERE profissional_id = ?
          AND date(vigente_desde) <= date(?)
        ORDER BY date(vigente_desde) DESC, id DESC
        LIMIT 1
        """,
        (profissional_id, data_ref),
    ).fetchone()

    if row:
        tipo = _normalizar_texto(row["tipo_comissao"])
        if tipo in ("percentual", "fixo"):
            return row

    row2 = db.execute(
        """
        SELECT tipo_comissao, valor_comissao
        FROM profissionais
        WHERE id = ?
          AND COALESCE(ativo, 1) = 1
        LIMIT 1
        """,
        (profissional_id,),
    ).fetchone()

    if row2:
        tipo = _normalizar_texto(row2["tipo_comissao"])
        if tipo in ("percentual", "fixo"):
            return row2

    return None


def calcular_comissao_por_data(profissional_id: int, data_ref: str):
    """
    Comissão do dia = soma do que foi efetivamente gravado em comissao_valor
    nas entradas pagas do profissional.
    """
    db = get_db()

    total_recebido = db.execute(
        """
        SELECT COALESCE(SUM(valor), 0) AS total
        FROM movimentacoes_caixa
        WHERE tipo = 'entrada'
          AND status = 'pago'
          AND profissional_id = ?
          AND date(data_hora) = date(?)
        """,
        (profissional_id, data_ref),
    ).fetchone()

    total_comissao = db.execute(
        """
        SELECT COALESCE(SUM(COALESCE(comissao_valor, 0)), 0) AS total
        FROM movimentacoes_caixa
        WHERE tipo = 'entrada'
          AND status = 'pago'
          AND profissional_id = ?
          AND date(data_hora) = date(?)
        """,
        (profissional_id, data_ref),
    ).fetchone()

    return {
        "profissional_id": int(profissional_id),
        "data": data_ref,
        "total_recebido": float(total_recebido["total"] or 0),
        "total_comissao": float(total_comissao["total"] or 0),
        "fonte": "comissao_valor",
    }


def calcular_comissao_diaria(profissional_id: int, data_ref: str):
    return calcular_comissao_por_data(profissional_id, data_ref)


def calcular_comissao_mensal(profissional_id: int, ano: str, mes: str):
    db = get_db()

    inicio = f"{ano}-{str(mes).zfill(2)}-01"
    fim = db.execute(
        "SELECT date(?, '+1 month') AS fim",
        (inicio,),
    ).fetchone()["fim"]

    total_recebido = db.execute(
        """
        SELECT COALESCE(SUM(valor), 0) AS total
        FROM movimentacoes_caixa
        WHERE tipo = 'entrada'
          AND status = 'pago'
          AND profissional_id = ?
          AND date(data_hora) >= date(?)
          AND date(data_hora) < date(?)
        """,
        (profissional_id, inicio, fim),
    ).fetchone()

    total_comissao = db.execute(
        """
        SELECT COALESCE(SUM(COALESCE(comissao_valor, 0)), 0) AS total
        FROM movimentacoes_caixa
        WHERE tipo = 'entrada'
          AND status = 'pago'
          AND profissional_id = ?
          AND date(data_hora) >= date(?)
          AND date(data_hora) < date(?)
        """,
        (profissional_id, inicio, fim),
    ).fetchone()

    return {
        "profissional_id": int(profissional_id),
        "ano": int(ano),
        "mes": int(mes),
        "total_recebido": float(total_recebido["total"] or 0),
        "total_comissao": float(total_comissao["total"] or 0),
        "fonte": "comissao_valor",
    }


# =============================================================================
# Resumo mensal do caixa
# Considera apenas movimentações efetivamente pagas para o fechamento
# =============================================================================
def resumo_caixa_mensal(ano: str, mes: str):
    db = get_db()

    inicio = f"{ano}-{str(mes).zfill(2)}-01"
    fim = db.execute(
        "SELECT date(?, '+1 month') AS fim",
        (inicio,),
    ).fetchone()["fim"]

    totais = db.execute(
        """
        SELECT
            COALESCE(SUM(CASE WHEN tipo = 'entrada' AND status = 'pago' THEN valor END), 0) AS total_entradas,
            COALESCE(SUM(CASE WHEN tipo = 'saida' AND status = 'pago' THEN valor END), 0) AS total_saidas
        FROM movimentacoes_caixa
        WHERE date(data_hora) >= date(?)
          AND date(data_hora) < date(?)
        """,
        (inicio, fim),
    ).fetchone()

    total_entradas = float(totais["total_entradas"] or 0)
    total_saidas = float(totais["total_saidas"] or 0)
    saldo = total_entradas - total_saidas

    por_forma = db.execute(
        """
        SELECT forma_pagamento, tipo, COALESCE(SUM(valor), 0) AS total
        FROM movimentacoes_caixa
        WHERE date(data_hora) >= date(?)
          AND date(data_hora) < date(?)
          AND status = 'pago'
        GROUP BY forma_pagamento, tipo
        ORDER BY forma_pagamento, tipo
        """,
        (inicio, fim),
    ).fetchall()

    por_prof = db.execute(
        """
        SELECT
            p.id AS profissional_id,
            p.nome AS profissional_nome,
            COALESCE(SUM(mc.valor), 0) AS total
        FROM movimentacoes_caixa mc
        JOIN profissionais p ON p.id = mc.profissional_id
        WHERE mc.tipo = 'entrada'
          AND mc.status = 'pago'
          AND mc.profissional_id IS NOT NULL
          AND date(mc.data_hora) >= date(?)
          AND date(mc.data_hora) < date(?)
        GROUP BY p.id, p.nome
        ORDER BY total DESC
        """,
        (inicio, fim),
    ).fetchall()

    por_profissional = [
        {
            "profissional_id": int(r["profissional_id"]),
            "profissional_nome": r["profissional_nome"],
            "total_entradas": float(r["total"] or 0),
        }
        for r in por_prof
    ]

    formas = {}
    for row in por_forma:
        fp = row["forma_pagamento"]
        tp = row["tipo"]
        if fp not in formas:
            formas[fp] = {"entrada": 0.0, "saida": 0.0}
        formas[fp][tp] = float(row["total"] or 0)

    return {
        "ano": int(ano),
        "mes": int(mes),
        "total_entradas": total_entradas,
        "total_saidas": total_saidas,
        "saldo": saldo,
        "por_forma_pagamento": formas,
        "por_profissional": por_profissional,
    }


# =============================================================================
# Movimentação criada por pagamento de agendamento
# Regra crítica do sistema: um agendamento não pode gerar duplicidade financeira
# =============================================================================
def criar_movimentacao_por_agendamento(
    *,
    agendamento_id: int,
    valor: float,
    forma_pagamento: str,
    descricao: str,
    profissional_id: int | None = None,
    servico_id: int | None = None,
    status: str = "pago",
    tipo: str = "entrada",
    data_hora: str | None = None,
    comissao_valor: float = 0.0,
    commit: bool = True,
) -> dict:
    """
    Regras:
    - Impede duplicidade por agendamento_id em entradas ativas
    - Registra profissional_id e servico_id quando disponíveis
    - Registra comissao_valor já calculada no momento da venda
    """
    db = get_db()

    agendamento_id = _parse_int_opcional(agendamento_id, "agendamento_id")
    profissional_id = _parse_int_opcional(profissional_id, "profissional_id")
    servico_id = _parse_int_opcional(servico_id, "servico_id")

    if not agendamento_id:
        return {
            "ok": False,
            "error": {
                "code": "INVALID_DATA",
                "message": "agendamento_id inválido."
            }
        }

    dup = db.execute(
        """
        SELECT id
        FROM movimentacoes_caixa
        WHERE agendamento_id = ?
          AND tipo = 'entrada'
          AND status != 'cancelado'
        LIMIT 1
        """,
        (agendamento_id,),
    ).fetchone()

    if dup:
        return {
            "ok": False,
            "error": {
                "code": "ALREADY_PAID",
                "message": "Este agendamento já possui movimentação de recebimento."
            }
        }

    if data_hora is None:
        data_hora = datetime.now().isoformat(timespec="seconds")

    try:
        mov_id = criar_movimentacao_caixa(
            tipo=tipo,
            forma_pagamento=forma_pagamento,
            valor=valor,
            data_hora=data_hora,
            descricao=descricao,
            agendamento_id=agendamento_id,
            profissional_id=profissional_id,
            servico_id=servico_id,
            status=status,
            comissao_valor=comissao_valor,
            commit=commit,
        )
    except ValueError as e:
        return {
            "ok": False,
            "error": {
                "code": "INVALID_DATA",
                "message": str(e)
            }
        }

    return {
        "ok": True,
        "data": {
            "movimentacao_id": mov_id,
            "agendamento_id": agendamento_id,
            "tipo": tipo,
            "status": status,
            "forma_pagamento": forma_pagamento,
            "valor": float(valor),
            "comissao_valor": float(comissao_valor or 0),
            "data_hora": data_hora,
            "descricao": descricao,
            "profissional_id": profissional_id,
            "servico_id": servico_id,
        },
    }
