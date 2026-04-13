from __future__ import annotations

from datetime import date, timedelta
from typing import Optional, Tuple, Dict, Any, List

from database.db import get_db

FORMAS = ("dinheiro", "pix", "debito", "credito", "plano")


def _parse_periodo(periodo: str) -> Tuple[str, str, str]:
    hoje = date.today()
    p = (periodo or "este_mes").strip().lower()

    def first_day(d: date) -> date:
        return d.replace(day=1)

    def add_months(d: date, months: int) -> date:
        y = d.year + (d.month - 1 + months) // 12
        m = (d.month - 1 + months) % 12 + 1
        return date(y, m, 1)

    if p == "semana":
        ini = hoje - timedelta(days=hoje.weekday())
        fim = hoje + timedelta(days=1)
        label = f"{ini.strftime('%d/%m/%Y')} a {(fim - timedelta(days=1)).strftime('%d/%m/%Y')}"
    elif p == "este_mes":
        ini = first_day(hoje)
        fim = add_months(ini, 1)
        label = f"{ini.strftime('%d/%m/%Y')} a {(fim - timedelta(days=1)).strftime('%d/%m/%Y')}"
    elif p == "mes_passado":
        ini = add_months(first_day(hoje), -1)
        fim = add_months(ini, 1)
        label = f"{ini.strftime('%d/%m/%Y')} a {(fim - timedelta(days=1)).strftime('%d/%m/%Y')}"
    elif p == "ultimos_3_meses":
        ini = add_months(first_day(hoje), -2)
        fim = add_months(first_day(hoje), 1)
        label = f"{ini.strftime('%d/%m/%Y')} a {(fim - timedelta(days=1)).strftime('%d/%m/%Y')}"
    elif p == "este_ano":
        ini = date(hoje.year, 1, 1)
        fim = date(hoje.year + 1, 1, 1)
        label = f"{ini.strftime('%d/%m/%Y')} a {(fim - timedelta(days=1)).strftime('%d/%m/%Y')}"
    elif p == "ultimo_ano":
        ini = date(hoje.year - 1, 1, 1)
        fim = date(hoje.year, 1, 1)
        label = f"{ini.strftime('%d/%m/%Y')} a {(fim - timedelta(days=1)).strftime('%d/%m/%Y')}"
    else:
        raise ValueError("periodo inválido")

    return ini.isoformat(), fim.isoformat(), label


def listar_profissionais_relatorio():
    db = get_db()
    return db.execute(
        """
        SELECT id, nome, ativo
        FROM profissionais
        ORDER BY nome
        """
    ).fetchall()


def _where_profissional(profissional_id: Optional[int], alias: str = "mc") -> Tuple[str, list]:
    if profissional_id is None:
        return "", []
    return f" AND {alias}.profissional_id = ? ", [int(profissional_id)]


def _where_profissional_agendamento(profissional_id: Optional[int], alias: str = "a") -> Tuple[str, list]:
    if profissional_id is None:
        return "", []
    return f" AND {alias}.profissional_id = ? ", [int(profissional_id)]


def _month_start_from_iso(iso_date: str) -> date:
    y, m, _ = iso_date.split("-")
    return date(int(y), int(m), 1)


def _add_months(d: date, months: int) -> date:
    y = d.year + (d.month - 1 + months) // 12
    m = (d.month - 1 + months) % 12 + 1
    return date(y, m, 1)


def _build_por_forma(db, ini: str, fim: str, profissional_id: Optional[int]) -> Dict[str, Dict[str, float]]:
    wprof_mc, pprof_mc = _where_profissional(profissional_id, "mc")

    rows = db.execute(
        f"""
        SELECT
            mc.forma_pagamento,
            mc.tipo,
            COALESCE(SUM(mc.valor), 0) AS total
        FROM movimentacoes_caixa mc
        WHERE mc.status = 'pago'
          AND date(mc.data_hora) >= date(?)
          AND date(mc.data_hora) < date(?)
          {wprof_mc}
        GROUP BY mc.forma_pagamento, mc.tipo
        """,
        [ini, fim, *pprof_mc],
    ).fetchall()

    por_forma: Dict[str, Dict[str, float]] = {
        forma: {"entrada": 0.0, "saida": 0.0} for forma in FORMAS
    }

    for r in rows:
        forma = (r["forma_pagamento"] or "").strip().lower()
        tipo = (r["tipo"] or "").strip().lower()
        total = float(r["total"] or 0)

        if forma not in por_forma:
            por_forma[forma] = {"entrada": 0.0, "saida": 0.0}

        if tipo in ("entrada", "saida"):
            por_forma[forma][tipo] = total

    return por_forma


def _build_faturamento_mensal_6m(db, fim: str, profissional_id: Optional[int]) -> List[dict]:
    wprof_mc, pprof_mc = _where_profissional(profissional_id, "mc")

    fim_month = _month_start_from_iso(fim)
    start_6m = _add_months(fim_month, -5)
    end_6m = _add_months(fim_month, 1)

    rows = db.execute(
        f"""
        SELECT
            strftime('%Y-%m', mc.data_hora) AS ym,
            COALESCE(SUM(mc.valor), 0) AS total
        FROM movimentacoes_caixa mc
        WHERE mc.tipo = 'entrada'
          AND mc.status = 'pago'
          AND date(mc.data_hora) >= date(?)
          AND date(mc.data_hora) < date(?)
          {wprof_mc}
        GROUP BY strftime('%Y-%m', mc.data_hora)
        ORDER BY ym ASC
        """,
        [start_6m.isoformat(), end_6m.isoformat(), *pprof_mc],
    ).fetchall()

    return [
        {
            "ym": r["ym"],
            "total": float(r["total"] or 0),
        }
        for r in rows
    ]


def _build_top_servicos(db, ini: str, fim: str, profissional_id: Optional[int]) -> List[dict]:
    wprof_mc, pprof_mc = _where_profissional(profissional_id, "mc")

    rows = db.execute(
        f"""
        SELECT
            COALESCE(s.nome, 'Sem serviço') AS servico_nome,
            COUNT(*) AS qtd,
            COALESCE(SUM(mc.valor), 0) AS total,
            COALESCE(SUM(COALESCE(mc.comissao_valor, 0)), 0) AS comissao_total,
            COALESCE(SUM(mc.valor - COALESCE(mc.comissao_valor, 0)), 0) AS lucro_liquido
        FROM movimentacoes_caixa mc
        LEFT JOIN servicos s ON s.id = mc.servico_id
        WHERE mc.tipo = 'entrada'
          AND mc.status = 'pago'
          AND mc.agendamento_id IS NOT NULL
          AND mc.servico_id IS NOT NULL
          AND date(mc.data_hora) >= date(?)
          AND date(mc.data_hora) < date(?)
          {wprof_mc}
        GROUP BY mc.servico_id, COALESCE(s.nome, 'Sem serviço')
        ORDER BY qtd DESC, total DESC, servico_nome ASC
        LIMIT 10
        """,
        [ini, fim, *pprof_mc],
    ).fetchall()

    return [
        {
            "servico_nome": r["servico_nome"],
            "qtd": int(r["qtd"] or 0),
            "total": float(r["total"] or 0),
            "comissao_total": float(r["comissao_total"] or 0),
            "lucro_liquido": float(r["lucro_liquido"] or 0),
        }
        for r in rows
    ]


def _build_top_profissionais(db, ini: str, fim: str, profissional_id: Optional[int]) -> List[dict]:
    wprof_mc, pprof_mc = _where_profissional(profissional_id, "mc")

    rows = db.execute(
        f"""
        SELECT
            COALESCE(p.nome, 'Sem profissional') AS profissional_nome,
            COUNT(*) AS atendimentos,
            COALESCE(SUM(mc.valor), 0) AS total,
            COALESCE(SUM(COALESCE(mc.comissao_valor, 0)), 0) AS comissao_total,
            COALESCE(SUM(mc.valor - COALESCE(mc.comissao_valor, 0)), 0) AS lucro_liquido
        FROM movimentacoes_caixa mc
        LEFT JOIN profissionais p ON p.id = mc.profissional_id
        WHERE mc.tipo = 'entrada'
          AND mc.status = 'pago'
          AND mc.agendamento_id IS NOT NULL
          AND date(mc.data_hora) >= date(?)
          AND date(mc.data_hora) < date(?)
          {wprof_mc}
        GROUP BY mc.profissional_id, COALESCE(p.nome, 'Sem profissional')
        ORDER BY total DESC, atendimentos DESC, profissional_nome ASC
        LIMIT 10
        """,
        [ini, fim, *pprof_mc],
    ).fetchall()

    return [
        {
            "profissional_nome": r["profissional_nome"],
            "atendimentos": int(r["atendimentos"] or 0),
            "total": float(r["total"] or 0),
            "comissao_total": float(r["comissao_total"] or 0),
            "lucro_liquido": float(r["lucro_liquido"] or 0),
        }
        for r in rows
    ]


def resumo_relatorio(periodo: str, profissional_id: Optional[int] = None) -> Dict[str, Any]:
    db = get_db()
    ini, fim, label = _parse_periodo(periodo)

    wprof_mc, pprof_mc = _where_profissional(profissional_id, "mc")
    wprof_ag, pprof_ag = _where_profissional_agendamento(profissional_id, "a")

    row = db.execute(
        f"""
        SELECT
            COALESCE(SUM(CASE WHEN mc.tipo='entrada' AND mc.status='pago' THEN mc.valor END), 0) AS entradas_pagas,
            COALESCE(SUM(CASE WHEN mc.tipo='saida'   AND mc.status='pago' THEN mc.valor END), 0) AS saidas_pagas,
            COALESCE(SUM(CASE WHEN mc.tipo='entrada' AND mc.status='pago' THEN COALESCE(mc.comissao_valor, 0) END), 0) AS comissao_total
        FROM movimentacoes_caixa mc
        WHERE date(mc.data_hora) >= date(?)
          AND date(mc.data_hora) < date(?)
          {wprof_mc}
        """,
        [ini, fim, *pprof_mc],
    ).fetchone()

    entradas = float(row["entradas_pagas"] or 0)
    saidas = float(row["saidas_pagas"] or 0)
    comissao_total = float(row["comissao_total"] or 0)

    saldo = entradas - saidas
    lucro_liquido = entradas - saidas - comissao_total

    row2 = db.execute(
        f"""
        SELECT COUNT(*) AS atendimentos
        FROM movimentacoes_caixa mc
        WHERE mc.tipo='entrada'
          AND mc.status='pago'
          AND mc.agendamento_id IS NOT NULL
          AND mc.forma_pagamento != 'plano'
          AND date(mc.data_hora) >= date(?)
          AND date(mc.data_hora) < date(?)
          {wprof_mc}
        """,
        [ini, fim, *pprof_mc],
    ).fetchone()

    atendimentos = int(row2["atendimentos"] or 0)

    row3 = db.execute(
        f"""
        SELECT COUNT(DISTINCT a.cliente_id) AS total
        FROM agendamentos a
        WHERE date(a.data) >= date(?)
          AND date(a.data) < date(?)
          AND lower(a.status) = 'concluido'
          {wprof_ag}
        """,
        [ini, fim, *pprof_ag],
    ).fetchone()

    clientes_no_periodo = int(row3["total"] or 0)

    row4 = db.execute(
        f"""
        SELECT COUNT(*) AS total
        FROM movimentacoes_caixa mc
        WHERE mc.tipo='entrada'
          AND mc.status='pago'
          AND mc.forma_pagamento='plano'
          AND mc.agendamento_id IS NOT NULL
          AND date(mc.data_hora) >= date(?)
          AND date(mc.data_hora) < date(?)
          {wprof_mc}
        """,
        [ini, fim, *pprof_mc],
    ).fetchone()

    uso_planos = int(row4["total"] or 0)

    ticket_medio = (entradas / atendimentos) if atendimentos > 0 else 0.0

    por_forma = _build_por_forma(
        db=db,
        ini=ini,
        fim=fim,
        profissional_id=profissional_id,
    )

    faturamento_mensal_6m = _build_faturamento_mensal_6m(
        db=db,
        fim=fim,
        profissional_id=profissional_id,
    )

    top_servicos = _build_top_servicos(
        db=db,
        ini=ini,
        fim=fim,
        profissional_id=profissional_id,
    )

    top_profissionais = _build_top_profissionais(
        db=db,
        ini=ini,
        fim=fim,
        profissional_id=profissional_id,
    )

    return {
        "periodo": {
            "inicio": ini,
            "fim_exclusivo": fim,
            "label": label,
        },
        "kpis": {
            "entradas": entradas,
            "saidas": saidas,
            "saldo": saldo,
            "clientes_no_periodo": clientes_no_periodo,
            "atendimentos": atendimentos,
            "comissao_total": comissao_total,
            "lucro_liquido": lucro_liquido,
            "uso_planos": uso_planos,
            "ticket_medio": ticket_medio,
        },
        "por_forma": por_forma,
        "faturamento_mensal_6m": faturamento_mensal_6m,
        "top_servicos": top_servicos,
        "top_profissionais": top_profissionais,
    }


def listar_movimentacoes(periodo: str, profissional_id: Optional[int], tipo: str) -> List[dict]:
    if tipo not in ("entrada", "saida"):
        raise ValueError("tipo inválido")

    db = get_db()
    ini, fim, _ = _parse_periodo(periodo)
    wprof, pprof = _where_profissional(profissional_id, "mc")

    rows = db.execute(
        f"""
        SELECT
            mc.id,
            mc.data_hora,
            mc.forma_pagamento,
            mc.valor,
            COALESCE(mc.comissao_valor, 0) AS comissao_valor,
            mc.descricao,
            mc.status,
            mc.agendamento_id,
            mc.profissional_id,
            mc.servico_id,
            p.nome AS profissional_nome,
            s.nome AS servico_nome
        FROM movimentacoes_caixa mc
        LEFT JOIN profissionais p ON p.id = mc.profissional_id
        LEFT JOIN servicos s ON s.id = mc.servico_id
        WHERE mc.tipo = ?
          AND mc.status = 'pago'
          AND date(mc.data_hora) >= date(?)
          AND date(mc.data_hora) < date(?)
          {wprof}
        ORDER BY date(mc.data_hora) ASC, mc.id ASC
        """,
        [tipo, ini, fim, *pprof],
    ).fetchall()

    out = []
    for r in rows:
        item = dict(r)
        item["valor"] = float(item.get("valor") or 0)
        item["comissao_valor"] = float(item.get("comissao_valor") or 0)
        out.append(item)

    return out
