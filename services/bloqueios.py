from datetime import datetime

from database.db import get_db


def _to_int(v, field):
    try:
        return int(v)
    except Exception:
        raise ValueError(f"{field} inválido")


def _validar_data_iso(data_str, field_name="data"):
    valor = (data_str or "").strip()
    if not valor:
        raise ValueError(f"{field_name} é obrigatória (YYYY-MM-DD)")

    try:
        return datetime.strptime(valor, "%Y-%m-%d").date().isoformat()
    except Exception:
        raise ValueError(f"{field_name} inválida (use YYYY-MM-DD)")


def _validar_hora_hhmm(valor, field_name):
    texto = (valor or "").strip()
    if not texto:
        raise ValueError(f"{field_name} é obrigatório")

    try:
        return datetime.strptime(texto, "%H:%M").strftime("%H:%M")
    except Exception:
        raise ValueError(f"{field_name} inválido (use HH:MM)")


def _hora_para_minutos(hora_hhmm: str) -> int:
    h, m = hora_hhmm.split(":")
    return int(h) * 60 + int(m)


def criar_bloqueio(profissional_id, data, dia_inteiro=1, hora_inicio=None, hora_fim=None, motivo=None) -> int:
    profissional_id = _to_int(profissional_id, "profissional_id")
    data = _validar_data_iso(data, "data")

    dia_inteiro = 1 if str(dia_inteiro).strip().lower() in (
        "1", "true", "sim") or dia_inteiro is True else 0

    if dia_inteiro == 0:
        hora_inicio = _validar_hora_hhmm(hora_inicio, "hora_inicio")
        hora_fim = _validar_hora_hhmm(hora_fim, "hora_fim")

        inicio_min = _hora_para_minutos(hora_inicio)
        fim_min = _hora_para_minutos(hora_fim)

        if inicio_min >= fim_min:
            raise ValueError("hora_inicio deve ser menor que hora_fim")
    else:
        hora_inicio = None
        hora_fim = None

    db = get_db()

    if dia_inteiro == 1:
        dup = db.execute(
            """
            SELECT id
            FROM bloqueios
            WHERE profissional_id = ?
              AND data = ?
              AND COALESCE(dia_inteiro, 0) = 1
            LIMIT 1
            """,
            (profissional_id, data),
        ).fetchone()
        if dup:
            raise ValueError(
                "Já existe bloqueio de dia inteiro para este profissional nesta data")

        conflito_intervalo = db.execute(
            """
            SELECT 1
            FROM bloqueios
            WHERE profissional_id = ?
              AND data = ?
              AND COALESCE(dia_inteiro, 0) = 0
            LIMIT 1
            """,
            (profissional_id, data),
        ).fetchone()
        if conflito_intervalo:
            raise ValueError(
                "Já existem bloqueios por intervalo nesta data; remova-os antes de criar bloqueio de dia inteiro")

    else:
        dup_dia_inteiro = db.execute(
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
        if dup_dia_inteiro:
            raise ValueError("Já existe bloqueio de dia inteiro nesta data")

        existentes = db.execute(
            """
            SELECT hora_inicio, hora_fim
            FROM bloqueios
            WHERE profissional_id = ?
              AND data = ?
              AND COALESCE(dia_inteiro, 0) = 0
            """,
            (profissional_id, data),
        ).fetchall()

        for row in existentes:
            ex_ini = _hora_para_minutos(_validar_hora_hhmm(
                row["hora_inicio"], "hora_inicio"))
            ex_fim = _hora_para_minutos(
                _validar_hora_hhmm(row["hora_fim"], "hora_fim"))

            if inicio_min < ex_fim and fim_min > ex_ini:
                raise ValueError(
                    "Já existe bloqueio conflitante para este intervalo")

    cur = db.execute(
        """
        INSERT INTO bloqueios (profissional_id, data, dia_inteiro, hora_inicio, hora_fim, motivo)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            profissional_id,
            data,
            dia_inteiro,
            hora_inicio,
            hora_fim,
            (motivo or "").strip() or None,
        ),
    )

    db.commit()
    return cur.lastrowid


def listar_bloqueios(data=None):
    db = get_db()

    if data:
        data = _validar_data_iso(data, "data")
        return db.execute(
            """
            SELECT id, profissional_id, data,
                   COALESCE(dia_inteiro, 0) AS dia_inteiro,
                   hora_inicio, hora_fim,
                   motivo
            FROM bloqueios
            WHERE data = ?
            ORDER BY id DESC
            """,
            (data,),
        ).fetchall()

    return db.execute(
        """
        SELECT id, profissional_id, data,
               COALESCE(dia_inteiro, 0) AS dia_inteiro,
               hora_inicio, hora_fim,
               motivo
        FROM bloqueios
        ORDER BY id DESC
        """
    ).fetchall()


def excluir_bloqueio(bloqueio_id: int) -> bool:
    bloqueio_id = _to_int(bloqueio_id, "bloqueio_id")

    db = get_db()
    cur = db.execute("DELETE FROM bloqueios WHERE id = ?", (bloqueio_id,))
    db.commit()
    return cur.rowcount > 0
