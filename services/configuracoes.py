# services/configuracoes.py
from __future__ import annotations

from datetime import datetime
from typing import Dict, Any, List

from database.db import get_db


# =========================
# GERAL
# =========================
def get_config_geral() -> Dict[str, Any]:
    db = get_db()
    row = db.execute("""
        SELECT id, nome, telefone, endereco, email, cnpj, atualizado_em
        FROM configuracoes_geral
        WHERE id = 1
        LIMIT 1
    """).fetchone()

    if not row:
        return {
            "id": 1,
            "nome": "",
            "telefone": "",
            "endereco": "",
            "email": "",
            "cnpj": "",
            "atualizado_em": None,
        }

    return dict(row)


def update_config_geral(payload: Dict[str, Any]) -> Dict[str, Any]:
    db = get_db()

    nome = (payload.get("nome") or "").strip()
    telefone = (payload.get("telefone") or "").strip()
    endereco = (payload.get("endereco") or "").strip()
    email = (payload.get("email") or "").strip()
    cnpj = (payload.get("cnpj") or "").strip()

    db.execute("""
        UPDATE configuracoes_geral
        SET nome = ?, telefone = ?, endereco = ?, email = ?, cnpj = ?,
            atualizado_em = datetime('now')
        WHERE id = 1
    """, (nome, telefone, endereco, email, cnpj))
    db.commit()

    return get_config_geral()


# =========================
# HORÁRIOS
# =========================
def get_config_horarios() -> List[Dict[str, Any]]:
    db = get_db()
    rows = db.execute("""
        SELECT dia_semana, aberto, hora_inicio, hora_fim, atualizado_em
        FROM configuracoes_horarios
        ORDER BY dia_semana
    """).fetchall()
    return [dict(r) for r in rows]


def update_config_horarios(horarios: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    horarios: [{dia_semana:0..6, aberto:0/1, hora_inicio:"09:00", hora_fim:"19:00"}, ...]
    """
    if not isinstance(horarios, list) or len(horarios) != 7:
        raise ValueError(
            "horarios inválido: envie uma lista com 7 itens (0..6).")

    db = get_db()

    for item in horarios:
        try:
            dia = int(item.get("dia_semana"))
        except Exception:
            raise ValueError("dia_semana inválido")

        if dia < 0 or dia > 6:
            raise ValueError("dia_semana deve estar entre 0 e 6")

        try:
            aberto = int(item.get("aberto", 1))
        except Exception:
            raise ValueError("aberto inválido (use 0 ou 1)")
        if aberto not in (0, 1):
            raise ValueError("aberto inválido (use 0 ou 1)")

        hi = (item.get("hora_inicio") or "09:00").strip()
        hf = (item.get("hora_fim") or "19:00").strip()

        if aberto == 1:
            if not (len(hi) == 5 and hi[2] == ":" and len(hf) == 5 and hf[2] == ":"):
                raise ValueError("hora_inicio/hora_fim inválidos (use HH:MM)")
            if not (hi < hf):
                raise ValueError("hora_inicio deve ser menor que hora_fim")

        db.execute("""
            UPDATE configuracoes_horarios
            SET aberto = ?, hora_inicio = ?, hora_fim = ?, atualizado_em = datetime('now')
            WHERE dia_semana = ?
        """, (aberto, hi, hf, dia))

    db.commit()
    return get_config_horarios()


# =========================
# AGENDA (regra do dia)
# =========================
def regra_do_dia(data_iso: str) -> Dict[str, Any]:
    """
    data_iso: 'YYYY-MM-DD'
    Retorna regra do dia com base em configuracoes_horarios.
    """
    if not data_iso or len(data_iso) < 10:
        raise ValueError("data inválida")

    # datetime.weekday(): seg=0..dom=6
    # nossa tabela: dom=0..sab=6
    dt = datetime.strptime(data_iso[:10], "%Y-%m-%d")
    weekday_seg0 = dt.weekday()
    dia_semana_dom0 = (weekday_seg0 + 1) % 7  # seg->1 ... dom->0

    db = get_db()
    row = db.execute("""
        SELECT dia_semana, aberto, hora_inicio, hora_fim
        FROM configuracoes_horarios
        WHERE dia_semana = ?
        LIMIT 1
    """, (dia_semana_dom0,)).fetchone()

    if not row:
        return {"dia_semana": dia_semana_dom0, "aberto": 1, "hora_inicio": "09:00", "hora_fim": "19:00"}

    return dict(row)


def validar_agendamento_por_config(data_iso: str, horario: str) -> None:
    """
    - Se o dia estiver fechado, bloqueia
    - Se aberto, só permite se hi <= horario < hf
    """
    regra = regra_do_dia(data_iso)
    if int(regra.get("aberto", 1)) != 1:
        raise ValueError("Barbearia fechada neste dia.")

    hi = regra.get("hora_inicio", "09:00")
    hf = regra.get("hora_fim", "19:00")

    if not (hi <= horario < hf):
        raise ValueError(f"Horário fora do funcionamento ({hi} às {hf}).")
