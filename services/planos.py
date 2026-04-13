from datetime import datetime, timedelta

from database.db import get_db
from services.caixa import criar_movimentacao_caixa


STATUS_ATIVO = "ativo"
STATUS_AGUARDANDO_PAGAMENTO = "aguardando_pagamento"
STATUS_ATRASADO = "atrasado"
STATUS_CANCELADO = "cancelado"

STATUS_VALIDOS = {
    STATUS_ATIVO,
    STATUS_AGUARDANDO_PAGAMENTO,
    STATUS_ATRASADO,
    STATUS_CANCELADO,
}

FORMAS_PAGAMENTO_VALIDAS = {
    "dinheiro",
    "pix",
    "debito",
    "credito",
}


def _hoje_iso():
    return datetime.now().date().isoformat()


def _agora_iso():
    return datetime.now().isoformat(timespec="seconds")


def _normalizar_status(status: str, default: str = STATUS_AGUARDANDO_PAGAMENTO) -> str:
    s = (status or default).strip().lower()
    if s not in STATUS_VALIDOS:
        raise ValueError("Status do plano inválido")
    return s


def _normalizar_bool_ativo(valor) -> int:
    if isinstance(valor, bool):
        return 1 if valor else 0

    if valor is None:
        raise ValueError("ativo é obrigatório")

    s = str(valor).strip().lower()
    if s in {"1", "true", "ativo", "sim", "yes"}:
        return 1
    if s in {"0", "false", "inativo", "nao", "não", "no"}:
        return 0

    raise ValueError("ativo inválido (use true/false ou 1/0)")


def _normalizar_forma_pagamento(valor, obrigatorio=False):
    v = (valor or "").strip().lower()

    if not v:
        if obrigatorio:
            raise ValueError("Forma de pagamento é obrigatória")
        return None

    if v not in FORMAS_PAGAMENTO_VALIDAS:
        raise ValueError("Forma de pagamento inválida")

    return v


def _normalizar_data_iso_opcional(valor):
    if valor is None:
        return None

    v = str(valor).strip()
    if not v:
        return None

    try:
        return datetime.fromisoformat(v).date().isoformat()
    except Exception:
        raise ValueError("Data inválida")


def _validar_vencimento_iso(vencimento: str | None):
    if not vencimento:
        return

    try:
        datetime.fromisoformat(vencimento).date()
    except Exception:
        raise ValueError("Data de vencimento inválida")


def _validar_plano_nao_vencido(proximo_vencimento: str | None):
    if not proximo_vencimento:
        return

    try:
        hoje = datetime.now().date()
        venc = datetime.fromisoformat(proximo_vencimento).date()
    except Exception:
        raise ValueError(
            "Plano com vencimento inválido. Ajuste a data do plano.")

    if hoje > venc:
        raise ValueError("Plano vencido. Renove para continuar usando.")


def _calcular_comissao_por_uso(valor_mensal: float, usos_por_mes: int) -> float:
    if usos_por_mes <= 0:
        raise ValueError("Plano com quantidade de usos inválida")
    return round((float(valor_mensal) * 0.5) / int(usos_por_mes), 2)


def _obter_cliente_plano_ativo_por_id(db, cliente_plano_id: int):
    return db.execute(
        """
        SELECT
            cp.id,
            cp.cliente_id,
            cp.plano_id,
            cp.data_inicio,
            cp.proximo_vencimento,
            cp.usos_totais,
            cp.usos_restantes,
            cp.forma_pagamento,
            cp.status,
            p.nome AS plano_nome,
            p.valor_mensal,
            p.usos_por_mes
        FROM clientes_planos cp
        JOIN planos p ON p.id = cp.plano_id
        WHERE cp.id = ?
          AND cp.status = 'ativo'
        """,
        (cliente_plano_id,),
    ).fetchone()


def _obter_agendamento_para_plano(db, agendamento_id: int):
    return db.execute(
        """
        SELECT
            a.id,
            a.cliente_id,
            a.profissional_id,
            a.servico_id,
            a.status,
            a.data,
            a.horario,
            s.nome AS servico_nome
        FROM agendamentos a
        JOIN servicos s ON s.id = a.servico_id
        WHERE a.id = ?
        """,
        (agendamento_id,),
    ).fetchone()


def _servico_pertence_ao_plano(db, plano_id: int, servico_id: int) -> bool:
    row = db.execute(
        """
        SELECT 1
        FROM planos_servicos
        WHERE plano_id = ?
          AND servico_id = ?
        LIMIT 1
        """,
        (plano_id, servico_id),
    ).fetchone()
    return row is not None


def _agendamento_ja_tem_recebimento_ativo(db, agendamento_id: int) -> bool:
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


def _agendamento_ja_consumiu_plano(db, agendamento_id: int) -> bool:
    row = db.execute(
        """
        SELECT 1
        FROM clientes_planos_usos
        WHERE agendamento_id = ?
        LIMIT 1
        """,
        (agendamento_id,),
    ).fetchone()
    return row is not None


def listar_planos():
    db = get_db()

    rows = db.execute(
        """
        SELECT *
        FROM planos
        ORDER BY nome
        """
    ).fetchall()

    return rows


def criar_plano(nome, valor_mensal, usos_por_mes, servicos, ativo=1):
    if not nome or not str(nome).strip():
        raise ValueError("nome é obrigatório")

    if valor_mensal is None or float(valor_mensal) < 0:
        raise ValueError("valor_mensal inválido")

    if usos_por_mes is None or int(usos_por_mes) <= 0:
        raise ValueError("usos_por_mes inválido")

    if not servicos:
        raise ValueError("o plano deve possuir ao menos um serviço")

    ativo_norm = _normalizar_bool_ativo(ativo)
    db = get_db()

    cursor = db.execute(
        """
        INSERT INTO planos
        (nome, valor_mensal, usos_por_mes, ativo)
        VALUES (?, ?, ?, ?)
        """,
        (str(nome).strip(), float(valor_mensal), int(usos_por_mes), ativo_norm),
    )

    plano_id = cursor.lastrowid

    for servico_id in servicos:
        db.execute(
            """
            INSERT INTO planos_servicos
            (plano_id, servico_id)
            VALUES (?, ?)
            """,
            (plano_id, int(servico_id)),
        )

    db.commit()
    return plano_id


def atualizar_status_plano(plano_id, ativo):
    ativo_norm = _normalizar_bool_ativo(ativo)
    db = get_db()

    row = db.execute(
        """
        SELECT id
        FROM planos
        WHERE id = ?
        """,
        (int(plano_id),),
    ).fetchone()

    if not row:
        raise ValueError("Plano não encontrado")

    db.execute(
        """
        UPDATE planos
        SET ativo = ?
        WHERE id = ?
        """,
        (ativo_norm, int(plano_id)),
    )
    db.commit()

    return {
        "id": int(plano_id),
        "ativo": bool(ativo_norm),
    }


def listar_planos_com_servicos_e_qtd(db):
    planos = db.execute(
        """
        SELECT p.id, p.nome, p.valor_mensal, p.usos_por_mes, p.ativo, p.criado_em
        FROM planos p
        ORDER BY p.nome ASC
        """
    ).fetchall()

    rows = db.execute(
        """
        SELECT ps.plano_id, s.nome AS servico_nome
        FROM planos_servicos ps
        JOIN servicos s ON s.id = ps.servico_id
        ORDER BY ps.plano_id, s.nome
        """
    ).fetchall()

    serv_by_plano = {}
    for r in rows:
        serv_by_plano.setdefault(r["plano_id"], []).append(r["servico_nome"])

    rows2 = db.execute(
        """
        SELECT plano_id, COUNT(*) AS qtd
        FROM clientes_planos
        WHERE status = 'ativo'
        GROUP BY plano_id
        """
    ).fetchall()

    qtd_by_plano = {r["plano_id"]: r["qtd"] for r in rows2}

    out = []
    for p in planos:
        pid = p["id"]
        item = dict(p)
        item["servicos_nomes"] = serv_by_plano.get(pid, [])
        item["qtd_clientes"] = int(qtd_by_plano.get(pid, 0))
        out.append(item)

    return out


def obter_kpis_planos():
    db = get_db()

    row_total = db.execute(
        """
        SELECT
            COUNT(*) AS planos_total,
            SUM(CASE WHEN ativo = 1 THEN 1 ELSE 0 END) AS planos_ativos
        FROM planos
        """
    ).fetchone()

    row_clientes = db.execute(
        """
        SELECT COUNT(*) AS clientes_com_plano
        FROM clientes_planos
        WHERE status = 'ativo'
        """
    ).fetchone()

    hoje = datetime.now().date()
    limite = hoje + timedelta(days=7)

    row_venc = db.execute(
        """
        SELECT COUNT(*) AS proximos_vencimentos_7d
        FROM clientes_planos
        WHERE status IN ('ativo', 'aguardando_pagamento', 'atrasado')
          AND proximo_vencimento IS NOT NULL
          AND date(proximo_vencimento) BETWEEN date(?) AND date(?)
        """,
        (hoje.isoformat(), limite.isoformat()),
    ).fetchone()

    row_popular = db.execute(
        """
        SELECT
            p.nome AS plano_popular_nome,
            COUNT(cp.id) AS plano_popular_qtd
        FROM planos p
        LEFT JOIN clientes_planos cp
            ON cp.plano_id = p.id
           AND cp.status = 'ativo'
        GROUP BY p.id, p.nome
        ORDER BY plano_popular_qtd DESC, p.nome ASC
        LIMIT 1
        """
    ).fetchone()

    return {
        "planos_total": int((row_total["planos_total"] or 0) if row_total else 0),
        "planos_ativos": int((row_total["planos_ativos"] or 0) if row_total else 0),
        "clientes_com_plano": int((row_clientes["clientes_com_plano"] or 0) if row_clientes else 0),
        "proximos_vencimentos_7d": int((row_venc["proximos_vencimentos_7d"] or 0) if row_venc else 0),
        "plano_popular_nome": (row_popular["plano_popular_nome"] if row_popular and row_popular["plano_popular_nome"] else "—"),
        "plano_popular_qtd": int((row_popular["plano_popular_qtd"] or 0) if row_popular else 0),
    }


def listar_clientes_do_plano(db, plano_id: int):
    rows = db.execute(
        """
        SELECT
          cp.id as id,
          cp.cliente_id,
          c.nome AS cliente_nome,
          cp.data_inicio,
          cp.proximo_vencimento,
          cp.usos_totais,
          cp.usos_restantes,
          cp.forma_pagamento,
          cp.status
        FROM clientes_planos cp
        JOIN clientes c ON c.id = cp.cliente_id
        WHERE cp.plano_id = ?
        ORDER BY c.nome ASC
        """,
        (plano_id,),
    ).fetchall()

    return [dict(r) for r in rows]


def vincular_cliente_plano(
    cliente_id,
    plano_id,
    forma_pagamento=None,
    data_inicio=None,
    proximo_vencimento=None,
    status=STATUS_AGUARDANDO_PAGAMENTO,
):
    db = get_db()

    status = _normalizar_status(status)
    data_inicio = _normalizar_data_iso_opcional(data_inicio) or _hoje_iso()
    proximo_vencimento = _normalizar_data_iso_opcional(proximo_vencimento)
    forma_pagamento = _normalizar_forma_pagamento(
        forma_pagamento,
        obrigatorio=(status == STATUS_ATIVO),
    )

    if status == STATUS_ATIVO and not proximo_vencimento:
        raise ValueError("Plano ativo deve possuir data de vencimento")

    try:
        db.execute("BEGIN IMMEDIATE")

        plano = db.execute(
            """
            SELECT *
            FROM planos
            WHERE id = ?
              AND ativo = 1
            """,
            (int(plano_id),),
        ).fetchone()

        if not plano:
            raise ValueError("Plano não encontrado")

        existente = db.execute(
            """
            SELECT id
            FROM clientes_planos
            WHERE cliente_id = ?
              AND status = 'ativo'
            LIMIT 1
            """,
            (int(cliente_id),),
        ).fetchone()

        if existente:
            raise ValueError("Cliente já possui plano ativo")

        cursor = db.execute(
            """
            INSERT INTO clientes_planos
            (
                cliente_id,
                plano_id,
                data_inicio,
                proximo_vencimento,
                usos_totais,
                usos_restantes,
                forma_pagamento,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(cliente_id),
                int(plano_id),
                data_inicio,
                proximo_vencimento,
                int(plano["usos_por_mes"]),
                int(plano["usos_por_mes"]),
                forma_pagamento,
                status,
            ),
        )

        cliente_plano_id = cursor.lastrowid

        if status == STATUS_ATIVO:
            criar_movimentacao_caixa(
                tipo="entrada",
                forma_pagamento=forma_pagamento,
                valor=float(plano["valor_mensal"]),
                data_hora=_agora_iso(),
                descricao=f"Assinatura {plano['nome']}",
                status="pago",
                comissao_valor=0,
                commit=False,
            )

        db.commit()
        return cliente_plano_id

    except Exception:
        db.execute("ROLLBACK")
        raise


def obter_plano_ativo_cliente(cliente_id):
    db = get_db()

    row = db.execute(
        """
        SELECT
            cp.*,
            p.nome AS plano_nome,
            p.usos_por_mes
        FROM clientes_planos cp
        JOIN planos p ON p.id = cp.plano_id
        WHERE cp.cliente_id = ?
          AND cp.status = 'ativo'
        LIMIT 1
        """,
        (cliente_id,),
    ).fetchone()

    return row


def registrar_uso_plano(cliente_plano_id, agendamento_id=None):
    db = get_db()

    cp = _obter_cliente_plano_ativo_por_id(db, int(cliente_plano_id))
    if not cp:
        raise ValueError("Plano não encontrado ou inativo")

    _validar_plano_nao_vencido(cp["proximo_vencimento"])

    if int(cp["usos_restantes"] or 0) <= 0:
        raise ValueError("Plano sem usos disponíveis")

    descricao = "Uso de Plano"
    profissional_id = None
    servico_id = None

    if agendamento_id is not None:
        ag = _obter_agendamento_para_plano(db, int(agendamento_id))
        if not ag:
            raise ValueError("Agendamento não encontrado")

        if int(ag["cliente_id"]) != int(cp["cliente_id"]):
            raise ValueError("Agendamento não pertence ao cliente do plano")

        if _agendamento_ja_consumiu_plano(db, int(agendamento_id)):
            raise ValueError("Este agendamento já consumiu um uso de plano")

        if not _servico_pertence_ao_plano(db, int(cp["plano_id"]), int(ag["servico_id"])):
            raise ValueError(
                "Serviço do agendamento não está incluso no plano do cliente")

        profissional_id = int(
            ag["profissional_id"]) if ag["profissional_id"] is not None else None
        servico_id = int(
            ag["servico_id"]) if ag["servico_id"] is not None else None
        descricao = f"Uso de Plano - {ag['servico_nome']}"

    usos_por_mes = int(cp["usos_por_mes"] or 0)
    if usos_por_mes <= 0:
        raise ValueError("Plano com quantidade de usos inválida")

    valor_mensal = float(cp["valor_mensal"] or 0)
    comissao_por_uso = _calcular_comissao_por_uso(valor_mensal, usos_por_mes)
    data_hora = _agora_iso()

    try:
        db.execute("BEGIN IMMEDIATE")

        cp_lock = _obter_cliente_plano_ativo_por_id(db, int(cliente_plano_id))
        if not cp_lock:
            raise ValueError("Plano não encontrado ou inativo")

        _validar_plano_nao_vencido(cp_lock["proximo_vencimento"])

        if int(cp_lock["usos_restantes"] or 0) <= 0:
            raise ValueError("Plano sem usos disponíveis")

        if agendamento_id is not None and _agendamento_ja_consumiu_plano(db, int(agendamento_id)):
            raise ValueError("Este agendamento já consumiu um uso de plano")

        cursor = db.execute(
            """
            UPDATE clientes_planos
            SET usos_restantes = usos_restantes - 1
            WHERE id = ?
              AND usos_restantes > 0
            """,
            (int(cliente_plano_id),),
        )

        if cursor.rowcount <= 0:
            raise ValueError("Não foi possível consumir uso do plano")

        db.execute(
            """
            INSERT INTO clientes_planos_usos
            (cliente_plano_id, agendamento_id, data_uso)
            VALUES (?, ?, ?)
            """,
            (
                int(cliente_plano_id),
                int(agendamento_id) if agendamento_id is not None else None,
                data_hora,
            ),
        )

        criar_movimentacao_caixa(
            tipo="entrada",
            forma_pagamento="plano",
            valor=0,
            data_hora=data_hora,
            descricao=descricao,
            agendamento_id=int(
                agendamento_id) if agendamento_id is not None else None,
            profissional_id=profissional_id,
            servico_id=servico_id,
            status="pago",
            comissao_valor=comissao_por_uso,
            commit=False,
        )

        db.commit()

    except Exception:
        db.execute("ROLLBACK")
        raise


def renovar_plano(cliente_plano_id, nova_data_vencimento, forma_pagamento):
    db = get_db()

    nova_data_vencimento = _normalizar_data_iso_opcional(nova_data_vencimento)
    forma_pagamento = _normalizar_forma_pagamento(
        forma_pagamento, obrigatorio=True)

    if not nova_data_vencimento:
        raise ValueError("Nova data de vencimento é obrigatória")

    try:
        db.execute("BEGIN IMMEDIATE")

        plano = db.execute(
            """
            SELECT cp.*, p.usos_por_mes, p.valor_mensal, p.nome
            FROM clientes_planos cp
            JOIN planos p ON p.id = cp.plano_id
            WHERE cp.id = ?
            """,
            (int(cliente_plano_id),),
        ).fetchone()

        if not plano:
            raise ValueError("Plano não encontrado")

        vencimento_atual = _normalizar_data_iso_opcional(
            plano["proximo_vencimento"])
        if vencimento_atual and nova_data_vencimento <= vencimento_atual:
            raise ValueError(
                "Nova data de vencimento deve ser maior que o vencimento atual")

        cursor = db.execute(
            """
            UPDATE clientes_planos
            SET
                usos_totais = ?,
                usos_restantes = ?,
                proximo_vencimento = ?,
                forma_pagamento = ?,
                status = 'ativo'
            WHERE id = ?
            """,
            (
                int(plano["usos_por_mes"]),
                int(plano["usos_por_mes"]),
                nova_data_vencimento,
                forma_pagamento,
                int(cliente_plano_id),
            ),
        )

        if cursor.rowcount <= 0:
            raise ValueError("Não foi possível renovar o plano")

        criar_movimentacao_caixa(
            tipo="entrada",
            forma_pagamento=forma_pagamento,
            valor=float(plano["valor_mensal"]),
            data_hora=_agora_iso(),
            descricao=f"Renovação {plano['nome']}",
            status="pago",
            comissao_valor=0,
            commit=False,
        )

        db.commit()

    except Exception:
        db.execute("ROLLBACK")
        raise

    return obter_cliente_plano_por_id(cliente_plano_id)


def usar_plano_em_agendamento(cliente_plano_id, agendamento_id):
    db = get_db()

    try:
        db.execute("BEGIN IMMEDIATE")

        ag = _obter_agendamento_para_plano(db, int(agendamento_id))
        if not ag:
            raise ValueError("Agendamento não encontrado")

        status_ag = (ag["status"] or "").strip().lower()
        if status_ag == "concluido":
            raise ValueError("Agendamento já está concluído")
        if status_ag == "cancelado":
            raise ValueError("Agendamento cancelado não pode usar plano")

        if _agendamento_ja_tem_recebimento_ativo(db, int(agendamento_id)):
            raise ValueError("Este agendamento já possui pagamento registrado")

        if _agendamento_ja_consumiu_plano(db, int(agendamento_id)):
            raise ValueError("Este agendamento já consumiu um uso de plano")

        cp = _obter_cliente_plano_ativo_por_id(db, int(cliente_plano_id))
        if not cp:
            raise ValueError("Plano não encontrado ou inativo")

        if int(ag["cliente_id"]) != int(cp["cliente_id"]):
            raise ValueError("Agendamento não pertence ao cliente do plano")

        _validar_plano_nao_vencido(cp["proximo_vencimento"])

        if int(cp["usos_restantes"] or 0) <= 0:
            raise ValueError("Plano sem usos disponíveis")

        if not _servico_pertence_ao_plano(db, int(cp["plano_id"]), int(ag["servico_id"])):
            raise ValueError(
                "Serviço do agendamento não está incluso no plano do cliente")

        usos_por_mes = int(cp["usos_por_mes"] or 0)
        if usos_por_mes <= 0:
            raise ValueError("Plano com quantidade de usos inválida")

        valor_mensal = float(cp["valor_mensal"] or 0)
        comissao_por_uso = _calcular_comissao_por_uso(
            valor_mensal, usos_por_mes)

        data_hora = _agora_iso()
        descricao = f"Uso de Plano - {ag['servico_nome']}"

        cursor = db.execute(
            """
            UPDATE clientes_planos
            SET usos_restantes = usos_restantes - 1
            WHERE id = ?
              AND usos_restantes > 0
            """,
            (int(cliente_plano_id),),
        )

        if cursor.rowcount <= 0:
            raise ValueError("Não foi possível consumir uso do plano")

        db.execute(
            """
            INSERT INTO clientes_planos_usos
            (cliente_plano_id, agendamento_id, data_uso)
            VALUES (?, ?, ?)
            """,
            (int(cliente_plano_id), int(agendamento_id), data_hora),
        )

        criar_movimentacao_caixa(
            tipo="entrada",
            forma_pagamento="plano",
            valor=0,
            data_hora=data_hora,
            descricao=descricao,
            agendamento_id=int(agendamento_id),
            profissional_id=int(
                ag["profissional_id"]) if ag["profissional_id"] is not None else None,
            servico_id=int(ag["servico_id"]
                           ) if ag["servico_id"] is not None else None,
            status="pago",
            comissao_valor=comissao_por_uso,
            commit=False,
        )

        db.execute(
            """
            UPDATE agendamentos
            SET status = 'concluido'
            WHERE id = ?
            """,
            (int(agendamento_id),),
        )

        usos_restantes_final = int(cp["usos_restantes"] or 0) - 1

        db.commit()

        return {
            "cliente_plano_id": int(cliente_plano_id),
            "agendamento_id": int(agendamento_id),
            "descricao": descricao,
            "comissao_valor": float(comissao_por_uso),
            "usos_restantes": usos_restantes_final,
        }

    except Exception:
        db.execute("ROLLBACK")
        raise


def obter_cliente_plano_por_id(cliente_plano_id):
    db = get_db()

    row = db.execute(
        """
        SELECT
            cp.id,
            cp.cliente_id,
            cp.plano_id,
            cp.data_inicio,
            cp.proximo_vencimento,
            cp.usos_totais,
            cp.usos_restantes,
            cp.forma_pagamento,
            cp.status
        FROM clientes_planos cp
        WHERE cp.id = ?
        LIMIT 1
        """,
        (int(cliente_plano_id),),
    ).fetchone()

    if not row:
        raise ValueError("Plano do cliente não encontrado")

    return dict(row)


def atualizar_cliente_plano(
    cliente_plano_id,
    data_inicio=None,
    proximo_vencimento=None,
    usos_totais=None,
    usos_restantes=None,
    forma_pagamento=None,
    status=None,
):
    db = get_db()

    existente = db.execute(
        """
        SELECT
            id,
            usos_totais,
            usos_restantes
        FROM clientes_planos
        WHERE id = ?
        LIMIT 1
        """,
        (int(cliente_plano_id),),
    ).fetchone()

    if not existente:
        raise ValueError("Plano do cliente não encontrado")

    # Correção: manter intenção do payload para atualização de campos
    enviou_data_inicio = data_inicio is not None
    enviou_proximo_vencimento = proximo_vencimento is not None

    data_inicio = _normalizar_data_iso_opcional(data_inicio)
    proximo_vencimento = _normalizar_data_iso_opcional(proximo_vencimento)

    if status is not None:
        status = _normalizar_status(status, default=status)

    forma_pagamento = _normalizar_forma_pagamento(
        forma_pagamento, obrigatorio=False)

    usos_totais_final = int(existente["usos_totais"] or 0)
    usos_restantes_final = int(existente["usos_restantes"] or 0)

    campos = []
    valores = []

    if enviou_data_inicio:
        campos.append("data_inicio = ?")
        valores.append(data_inicio)

    if enviou_proximo_vencimento:
        campos.append("proximo_vencimento = ?")
        valores.append(proximo_vencimento)

    if usos_totais is not None:
        usos_totais = int(usos_totais)
        if usos_totais < 0:
            raise ValueError("usos_totais inválido")
        usos_totais_final = usos_totais
        campos.append("usos_totais = ?")
        valores.append(usos_totais)

    if usos_restantes is not None:
        usos_restantes = int(usos_restantes)
        if usos_restantes < 0:
            raise ValueError("usos_restantes inválido")
        usos_restantes_final = usos_restantes
        campos.append("usos_restantes = ?")
        valores.append(usos_restantes)

    if usos_restantes_final > usos_totais_final:
        raise ValueError("usos_restantes não pode ser maior que usos_totais")

    if forma_pagamento is not None:
        campos.append("forma_pagamento = ?")
        valores.append(forma_pagamento)

    if status is not None:
        campos.append("status = ?")
        valores.append(status)

    if not campos:
        raise ValueError("Nenhum campo enviado para atualização")

    valores.append(int(cliente_plano_id))

    db.execute(
        f"""
        UPDATE clientes_planos
        SET {", ".join(campos)}
        WHERE id = ?
        """,
        tuple(valores),
    )

    db.commit()
    return obter_cliente_plano_por_id(cliente_plano_id)


def cancelar_plano(cliente_plano_id):
    db = get_db()

    row = db.execute(
        """
        SELECT id
        FROM clientes_planos
        WHERE id = ?
        """,
        (int(cliente_plano_id),),
    ).fetchone()

    if not row:
        raise ValueError("Plano do cliente não encontrado")

    db.execute(
        """
        UPDATE clientes_planos
        SET status = 'cancelado'
        WHERE id = ?
        """,
        (int(cliente_plano_id),),
    )

    db.commit()
