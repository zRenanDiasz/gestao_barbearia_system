from __future__ import annotations

from datetime import datetime

from database.db import get_db
from services.caixa import criar_movimentacao_por_agendamento, obter_comissao_vigente
from services.configuracoes import validar_agendamento_por_config, regra_do_dia


STATUS_AGUARDANDO = "aguardando"
STATUS_CONFIRMADO = "confirmado"
STATUS_CANCELADO = "cancelado"
STATUS_CONCLUIDO = "concluido"

FORMAS_PAGAMENTO_AGENDAMENTO_VALIDAS = {"dinheiro", "pix", "debito", "credito"}


def _validar_data_iso(data_str: str, campo: str = "data") -> str:
    valor = (data_str or "").strip()
    if not valor:
        raise ValueError(f"{campo} é obrigatória")

    try:
        data_obj = datetime.strptime(valor, "%Y-%m-%d").date()
    except Exception:
        raise ValueError(f"{campo} inválida")

    return data_obj.isoformat()


def _validar_horario_hhmm(horario: str, campo: str = "horario") -> str:
    valor = (horario or "").strip()
    if not valor:
        raise ValueError(f"{campo} é obrigatório")

    try:
        hora_obj = datetime.strptime(valor, "%H:%M")
    except Exception:
        raise ValueError(f"{campo} inválido")

    return hora_obj.strftime("%H:%M")


def _validar_data_hora_iso_opcional(data_hora: str | None) -> str | None:
    if data_hora is None:
        return None

    valor = str(data_hora).strip()
    if not valor:
        raise ValueError("data_hora inválida")

    try:
        return datetime.fromisoformat(valor).isoformat(timespec="seconds")
    except Exception:
        raise ValueError("data_hora inválida")


def _horario_para_minutos(horario: str) -> int:
    h, m = horario.split(":")
    return int(h) * 60 + int(m)


def criar_agendamento(cliente_id, profissional_id, servico_id, data, horario):
    db = get_db()

    data = _validar_data_iso(data)
    horario = _validar_horario_hhmm(horario)

    if not profissional_ativo(profissional_id):
        raise ValueError("Profissional inexistente ou inativo")

    validar_agendamento_por_config(data, horario)

    if horario_bloqueado(profissional_id, data, horario):
        return False

    servico = db.execute(
        """
        SELECT duracao
        FROM servicos
        WHERE id = ?
        """,
        (servico_id,),
    ).fetchone()

    if not servico:
        raise ValueError("Serviço inexistente")

    duracao = int(servico["duracao"] or 0)
    if duracao <= 0:
        raise ValueError("Serviço com duração inválida")

    inicio_novo = _horario_para_minutos(horario)
    fim_novo = inicio_novo + duracao

    agendamentos = db.execute(
        """
        SELECT a.horario, s.duracao
        FROM agendamentos a
        JOIN servicos s ON s.id = a.servico_id
        WHERE a.profissional_id = ?
          AND a.data = ?
          AND lower(a.status) != 'cancelado'
        """,
        (profissional_id, data),
    ).fetchall()

    for ag in agendamentos:
        horario_existente = _validar_horario_hhmm(ag["horario"])
        inicio_existente = _horario_para_minutos(horario_existente)
        fim_existente = inicio_existente + int(ag["duracao"] or 0)

        if inicio_novo < fim_existente and fim_novo > inicio_existente:
            return False

    db.execute(
        """
        INSERT INTO agendamentos (
            cliente_id,
            profissional_id,
            servico_id,
            data,
            horario,
            status
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (cliente_id, profissional_id, servico_id, data, horario, STATUS_AGUARDANDO),
    )
    db.commit()
    return True


def listar_agendamentos(data_ref=None):
    db = get_db()

    where = ""
    params = []

    if data_ref:
        data_ref = _validar_data_iso(data_ref, "data")
        where = "WHERE a.data = ?"
        params.append(data_ref)

    rows = db.execute(
        f"""
        SELECT
            a.id,
            a.cliente_id,
            c.nome AS cliente_nome,
            a.profissional_id,
            p.nome AS profissional_nome,
            a.servico_id,
            s.nome AS servico_nome,
            s.preco AS preco,
            a.data,
            a.horario,
            a.status
        FROM agendamentos a
        JOIN clientes c ON c.id = a.cliente_id
        JOIN profissionais p ON p.id = a.profissional_id
        JOIN servicos s ON s.id = a.servico_id
        {where}
        ORDER BY a.data DESC, a.horario ASC
        """,
        params,
    ).fetchall()

    return rows


def listar_horarios_disponiveis(profissional_id, data):
    db = get_db()
    data = _validar_data_iso(data)

    horarios_padrao = [
        "09:00", "10:00", "11:00",
        "13:00", "14:00", "15:00",
        "16:00", "17:00",
    ]

    regra = regra_do_dia(data)
    if int(regra.get("aberto", 1)) != 1:
        return []

    hi = _validar_horario_hhmm(
        regra.get("hora_inicio", "09:00"), "hora_inicio")
    hf = _validar_horario_hhmm(regra.get("hora_fim", "19:00"), "hora_fim")
    horarios_padrao = [h for h in horarios_padrao if hi <= h < hf]

    ocupados = db.execute(
        """
        SELECT horario
        FROM agendamentos
        WHERE profissional_id = ?
          AND data = ?
          AND lower(status) != 'cancelado'
        """,
        (profissional_id, data),
    ).fetchall()

    horarios_ocupados = {row["horario"] for row in ocupados}

    bloqueios = db.execute(
        """
        SELECT
            COALESCE(dia_inteiro, 0) AS dia_inteiro,
            hora_inicio,
            hora_fim
        FROM bloqueios
        WHERE profissional_id = ?
          AND data = ?
        """,
        (profissional_id, data),
    ).fetchall()

    for b in bloqueios:
        if int(b["dia_inteiro"] or 0) == 1:
            return []

    horarios_bloqueados = set()
    for b in bloqueios:
        if not b["hora_inicio"] or not b["hora_fim"]:
            continue

        inicio = _horario_para_minutos(
            _validar_horario_hhmm(b["hora_inicio"], "hora_inicio"))
        fim = _horario_para_minutos(
            _validar_horario_hhmm(b["hora_fim"], "hora_fim"))

        for h in horarios_padrao:
            minutos = _horario_para_minutos(h)
            if inicio <= minutos < fim:
                horarios_bloqueados.add(h)

    indisponiveis = horarios_ocupados | horarios_bloqueados
    return [h for h in horarios_padrao if h not in indisponiveis]


def profissional_ativo(profissional_id):
    db = get_db()
    row = db.execute(
        """
        SELECT ativo
        FROM profissionais
        WHERE id = ?
        """,
        (profissional_id,),
    ).fetchone()
    return row is not None and int(row["ativo"] or 0) == 1


def atualizar_status_agendamento(agendamento_id, novo_status):
    novo_status = (novo_status or "").strip().lower()
    permitidos = {STATUS_CONFIRMADO, STATUS_AGUARDANDO, STATUS_CANCELADO}

    if novo_status not in permitidos:
        raise ValueError(
            "status inválido. Use: confirmado, aguardando, cancelado")

    db = get_db()

    existe = db.execute(
        """
        SELECT id
        FROM agendamentos
        WHERE id = ?
        """,
        (agendamento_id,),
    ).fetchone()

    if not existe:
        raise ValueError("Agendamento não encontrado")

    db.execute(
        """
        UPDATE agendamentos
        SET status = ?
        WHERE id = ?
        """,
        (novo_status, agendamento_id),
    )
    db.commit()


def calcular_faturamento_por_profissional_e_data(profissional_id, data):
    db = get_db()
    data = _validar_data_iso(data)

    row = db.execute(
        """
        SELECT COALESCE(SUM(mc.valor), 0) AS total
        FROM movimentacoes_caixa mc
        WHERE mc.tipo = 'entrada'
          AND mc.status = 'pago'
          AND mc.profissional_id = ?
          AND date(mc.data_hora) = date(?)
        """,
        (profissional_id, data),
    ).fetchone()

    return float(row["total"] or 0)


def horario_bloqueado(profissional_id, data, horario):
    db = get_db()

    data = _validar_data_iso(data)
    horario = _validar_horario_hhmm(horario)

    dia_int = db.execute(
        """
        SELECT 1
        FROM bloqueios
        WHERE profissional_id = ?
          AND data = ?
          AND COALESCE(dia_inteiro, 0) = 1
        LIMIT 1
        """,
        (profissional_id, data),
    ).fetchone()

    if dia_int:
        return True

    row = db.execute(
        """
        SELECT 1
        FROM bloqueios
        WHERE profissional_id = ?
          AND data = ?
          AND COALESCE(dia_inteiro, 0) = 0
          AND ? >= hora_inicio
          AND ? < hora_fim
        LIMIT 1
        """,
        (profissional_id, data, horario, horario),
    ).fetchone()

    return row is not None


def listar_agendamentos_por_profissional_e_data(profissional_id, data):
    db = get_db()
    data = _validar_data_iso(data)

    return db.execute(
        """
        SELECT
            a.id,
            c.nome AS cliente,
            p.nome AS profissional,
            s.nome AS servico,
            a.data,
            a.horario,
            a.status
        FROM agendamentos a
        JOIN clientes c ON c.id = a.cliente_id
        JOIN profissionais p ON p.id = a.profissional_id
        JOIN servicos s ON s.id = a.servico_id
        WHERE a.profissional_id = ?
          AND a.data = ?
        ORDER BY a.horario
        """,
        (profissional_id, data),
    ).fetchall()


def listar_agendamentos_por_mes(profissional_id, ano, mes):
    db = get_db()
    return db.execute(
        """
        SELECT
            data,
            COUNT(*) AS total
        FROM agendamentos
        WHERE profissional_id = ?
          AND strftime('%Y', data) = ?
          AND strftime('%m', data) = ?
        GROUP BY data
        ORDER BY data
        """,
        (profissional_id, str(ano), f"{int(mes):02d}"),
    ).fetchall()


def editar_agendamento(agendamento_id, cliente_id, profissional_id, servico_id, data_agendamento, horario):
    db = get_db()

    data_agendamento = _validar_data_iso(data_agendamento)
    horario = _validar_horario_hhmm(horario)

    ag = db.execute(
        """
        SELECT id
        FROM agendamentos
        WHERE id = ?
        """,
        (agendamento_id,),
    ).fetchone()

    if not ag:
        raise ValueError("Agendamento não encontrado")

    if not profissional_ativo(profissional_id):
        raise ValueError("Profissional inexistente ou inativo")

    servico = db.execute(
        """
        SELECT duracao
        FROM servicos
        WHERE id = ?
        """,
        (servico_id,),
    ).fetchone()

    if not servico:
        raise ValueError("Serviço inexistente")

    duracao = int(servico["duracao"] or 0)
    if duracao <= 0:
        raise ValueError("Serviço com duração inválida")

    validar_agendamento_por_config(data_agendamento, horario)

    if horario_bloqueado(profissional_id, data_agendamento, horario):
        return False

    inicio_novo = _horario_para_minutos(horario)
    fim_novo = inicio_novo + duracao

    conflitos = db.execute(
        """
        SELECT a.horario, s.duracao
        FROM agendamentos a
        JOIN servicos s ON s.id = a.servico_id
        WHERE a.profissional_id = ?
          AND a.data = ?
          AND a.id != ?
          AND lower(a.status) != 'cancelado'
        """,
        (profissional_id, data_agendamento, agendamento_id),
    ).fetchall()

    for conflito in conflitos:
        horario_existente = _validar_horario_hhmm(conflito["horario"])
        inicio_existente = _horario_para_minutos(horario_existente)
        fim_existente = inicio_existente + int(conflito["duracao"] or 0)

        if inicio_novo < fim_existente and fim_novo > inicio_existente:
            return False

    db.execute(
        """
        UPDATE agendamentos
        SET cliente_id = ?, profissional_id = ?, servico_id = ?, data = ?, horario = ?
        WHERE id = ?
        """,
        (cliente_id, profissional_id, servico_id,
         data_agendamento, horario, agendamento_id),
    )
    db.commit()
    return True


def pagar_agendamento(
    agendamento_id: int,
    forma_pagamento: str | None = None,
    valor_servico: float | None = None,
    produtos: list[dict] | None = None,
    data_hora: str | None = None
) -> dict:
    db = get_db()

    try:
        db.execute("BEGIN IMMEDIATE")

        ag = db.execute(
            """
            SELECT
                a.id,
                a.status,
                a.data,
                a.horario,
                a.profissional_id,
                a.servico_id,
                c.nome AS cliente_nome,
                p.nome AS profissional_nome,
                s.nome AS servico_nome,
                s.preco AS preco_servico
            FROM agendamentos a
            JOIN clientes c ON c.id = a.cliente_id
            JOIN profissionais p ON p.id = a.profissional_id
            JOIN servicos s ON s.id = a.servico_id
            WHERE a.id = ?
            """,
            (agendamento_id,),
        ).fetchone()

        if not ag:
            db.execute("ROLLBACK")
            return {
                "ok": False,
                "error": {
                    "code": "NOT_FOUND",
                    "message": "Agendamento não encontrado."
                }
            }

        status_atual = (ag["status"] or "").strip().lower()

        if status_atual == STATUS_CONCLUIDO:
            db.execute("ROLLBACK")
            return {
                "ok": False,
                "error": {
                    "code": "ALREADY_CONCLUDED",
                    "message": "Agendamento já está concluído."
                }
            }

        if status_atual == STATUS_CANCELADO:
            db.execute("ROLLBACK")
            return {
                "ok": False,
                "error": {
                    "code": "CANCELLED",
                    "message": "Agendamento cancelado não pode ser pago."
                }
            }

        valor_servico_final = float(valor_servico) if valor_servico is not None else float(
            ag["preco_servico"] or 0.0)

        if valor_servico_final <= 0:
            db.execute("ROLLBACK")
            return {
                "ok": False,
                "error": {
                    "code": "INVALID_AMOUNT",
                    "message": "Valor inválido para pagamento."
                }
            }

        forma_pagamento = (forma_pagamento or "dinheiro").strip().lower()
        if forma_pagamento == "plano":
            db.execute("ROLLBACK")
            return {
                "ok": False,
                "error": {
                    "code": "INVALID_PAYMENT_METHOD",
                    "message": "forma_pagamento 'plano' é permitida apenas no fluxo próprio de uso de plano."
                }
            }

        if forma_pagamento not in FORMAS_PAGAMENTO_AGENDAMENTO_VALIDAS:
            db.execute("ROLLBACK")
            return {
                "ok": False,
                "error": {
                    "code": "INVALID_PAYMENT_METHOD",
                    "message": "Forma de pagamento inválida."
                }
            }

        data_hora = _validar_data_hora_iso_opcional(data_hora)
        if data_hora is None:
            data_hora = datetime.now().isoformat(timespec="seconds")

        produtos = produtos or []
        itens = []

        for it in produtos:
            try:
                pid = int(it.get("produto_id"))
                qtd = int(it.get("quantidade"))
            except Exception:
                db.execute("ROLLBACK")
                return {
                    "ok": False,
                    "error": {
                        "code": "INVALID_PRODUCTS",
                        "message": "Produtos inválidos."
                    }
                }

            if pid <= 0 or qtd <= 0:
                db.execute("ROLLBACK")
                return {
                    "ok": False,
                    "error": {
                        "code": "INVALID_PRODUCTS",
                        "message": "Produtos inválidos."
                    }
                }

            itens.append({
                "produto_id": pid,
                "quantidade": qtd
            })

        com_row = obter_comissao_vigente(
            db, int(ag["profissional_id"]), ag["data"])
        comissao_valor = 0.0
        com_tipo = None
        com_cfg = None

        if com_row:
            com_tipo = (com_row["tipo_comissao"] or "").strip().lower()
            com_cfg = float(com_row["valor_comissao"] or 0)

            if com_tipo == "percentual":
                comissao_valor = valor_servico_final * (com_cfg / 100.0)
            elif com_tipo == "fixo":
                comissao_valor = com_cfg

        total_produtos = 0.0
        produtos_detalhe = []

        if itens:
            for it in itens:
                p = db.execute(
                    """
                    SELECT id, nome, preco_venda, estoque_atual, ativo
                    FROM produtos
                    WHERE id = ?
                    """,
                    (it["produto_id"],),
                ).fetchone()

                if not p or int(p["ativo"] or 0) != 1:
                    db.execute("ROLLBACK")
                    return {
                        "ok": False,
                        "error": {
                            "code": "INVALID_PRODUCT",
                            "message": "Produto não encontrado ou inativo."
                        }
                    }

                estoque_atual = int(p["estoque_atual"] or 0)
                qtd = int(it["quantidade"])

                if qtd > estoque_atual:
                    db.execute("ROLLBACK")
                    return {
                        "ok": False,
                        "error": {
                            "code": "NO_STOCK",
                            "message": f"Estoque insuficiente para {p['nome']}."
                        }
                    }

                preco_venda = float(p["preco_venda"] or 0.0)
                subtotal = preco_venda * qtd
                total_produtos += subtotal

                produtos_detalhe.append({
                    "produto_id": int(p["id"]),
                    "nome": p["nome"],
                    "preco_venda": preco_venda,
                    "quantidade": qtd,
                    "subtotal": subtotal,
                })

        total_receber = float(valor_servico_final) + float(total_produtos)

        desc_prod = ""
        if produtos_detalhe:
            parts = [
                f"{d['nome']} x{d['quantidade']}" for d in produtos_detalhe]
            desc_prod = " | Produtos: " + ", ".join(parts)

        descricao = f"Pagamento - {ag['cliente_nome']} - {ag['servico_nome']}{desc_prod}"

        if produtos_detalhe:
            for d in produtos_detalhe:
                row_estoque = db.execute(
                    """
                    SELECT estoque_atual
                    FROM produtos
                    WHERE id = ?
                    """,
                    (d["produto_id"],),
                ).fetchone()

                atual = int(row_estoque["estoque_atual"] or 0)
                novo = atual - int(d["quantidade"])

                if novo < 0:
                    db.execute("ROLLBACK")
                    return {
                        "ok": False,
                        "error": {
                            "code": "NO_STOCK",
                            "message": f"Estoque insuficiente para {d['nome']}."
                        }
                    }

                db.execute(
                    """
                    UPDATE produtos
                    SET estoque_atual = ?
                    WHERE id = ?
                    """,
                    (novo, d["produto_id"]),
                )

        mov = criar_movimentacao_por_agendamento(
            agendamento_id=agendamento_id,
            valor=total_receber,
            forma_pagamento=forma_pagamento,
            descricao=descricao,
            status="pago",
            tipo="entrada",
            data_hora=data_hora,
            profissional_id=int(
                ag["profissional_id"]) if ag["profissional_id"] is not None else None,
            servico_id=int(ag["servico_id"]
                           ) if ag["servico_id"] is not None else None,
            comissao_valor=float(comissao_valor),
            commit=False,
        )

        if not mov.get("ok"):
            db.execute("ROLLBACK")
            return mov

        mov_data = mov.get("data") or {}
        mov_id = int(mov_data.get("movimentacao_id") or 0)

        if not mov_id:
            db.execute("ROLLBACK")
            return {
                "ok": False,
                "error": {
                    "code": "MOV_ERROR",
                    "message": "Erro ao gerar movimentação financeira."
                }
            }

        if produtos_detalhe:
            for d in produtos_detalhe:
                db.execute(
                    """
                    INSERT INTO movimentacoes_estoque (
                        produto_id,
                        tipo,
                        quantidade,
                        data_hora,
                        descricao
                    )
                    VALUES (?, 'saida', ?, ?, ?)
                    """,
                    (
                        d["produto_id"],
                        int(d["quantidade"]),
                        data_hora,
                        f"Venda agendamento #{agendamento_id}",
                    ),
                )

                db.execute(
                    """
                    INSERT INTO vendas_produtos (
                        movimentacao_id,
                        produto_id,
                        nome,
                        quantidade,
                        preco_unit,
                        subtotal
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        mov_id,
                        d["produto_id"],
                        d["nome"],
                        int(d["quantidade"]),
                        float(d["preco_venda"]),
                        float(d["subtotal"]),
                    ),
                )

        db.execute(
            """
            UPDATE agendamentos
            SET status = ?
            WHERE id = ?
            """,
            (STATUS_CONCLUIDO, agendamento_id),
        )

        db.commit()

        return {
            "ok": True,
            "data": {
                "agendamento_id": agendamento_id,
                "novo_status": STATUS_CONCLUIDO,
                "movimentacao": mov_data,
                "valor_servico": float(valor_servico_final),
                "total_produtos": float(total_produtos),
                "total_receber": float(total_receber),
                "comissao": {
                    "tipo": com_tipo,
                    "valor_config": com_cfg,
                    "valor_calculado": float(comissao_valor),
                    "base": "servico",
                },
            },
        }

    except Exception as e:
        try:
            db.execute("ROLLBACK")
        except Exception:
            pass

        return {
            "ok": False,
            "error": {
                "code": "INTERNAL_ERROR",
                "message": f"Erro ao processar pagamento: {str(e)}"
            }
        }


def atualizar_status_manual_agendamento(agendamento_id: int, status: str) -> dict:
    status = (status or "").strip().lower()

    if status not in (STATUS_AGUARDANDO, STATUS_CANCELADO):
        return {
            "ok": False,
            "error": {
                "code": "INVALID_STATUS",
                "message": "Status manual permitido apenas: aguardando, cancelado."
            },
        }

    db = get_db()

    ag = db.execute(
        """
        SELECT id
        FROM agendamentos
        WHERE id = ?
        """,
        (agendamento_id,),
    ).fetchone()

    if not ag:
        return {
            "ok": False,
            "error": {
                "code": "NOT_FOUND",
                "message": "Agendamento não encontrado."
            }
        }

    db.execute(
        """
        UPDATE agendamentos
        SET status = ?
        WHERE id = ?
        """,
        (status, agendamento_id),
    )
    db.commit()

    return {
        "ok": True,
        "data": {
            "agendamento_id": agendamento_id,
            "novo_status": status
        }
    }
