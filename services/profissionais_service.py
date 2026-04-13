from __future__ import annotations

from datetime import datetime

from database.db import get_db


TIPOS_COMISSAO_VALIDOS = {"percentual", "fixo"}


# =============================================================================
# Helpers internos
# =============================================================================
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


def _clean_str(v):
    return (v or "").strip()


def _normalizar_tipo_comissao(tipo_comissao: str) -> str:
    tipo = _clean_str(tipo_comissao).lower()
    if tipo not in TIPOS_COMISSAO_VALIDOS:
        raise ValueError("tipo_comissao inválido (use 'percentual' ou 'fixo')")
    return tipo


def _validar_valor_comissao(tipo_comissao: str, valor_comissao) -> float:
    if valor_comissao is None or valor_comissao == "":
        raise ValueError("valor_comissao é obrigatório")

    valor = _to_float(valor_comissao, "valor_comissao")

    if valor < 0:
        raise ValueError("valor_comissao não pode ser negativo")

    if tipo_comissao == "percentual" and valor > 100:
        raise ValueError("percentual não pode ser maior que 100")

    return valor


def _validar_data_iso(data_str: str, field_name: str = "data"):
    data_str = _clean_str(data_str)
    if not data_str:
        raise ValueError(f"{field_name} é obrigatório (YYYY-MM-DD)")

    try:
        datetime.strptime(data_str, "%Y-%m-%d")
    except Exception:
        raise ValueError(f"{field_name} inválido (use YYYY-MM-DD)")

    return data_str


def _buscar_profissional(db, profissional_id: int):
    return db.execute(
        """
        SELECT id, ativo
        FROM profissionais
        WHERE id = ?
        """,
        (profissional_id,),
    ).fetchone()


# =============================================================================
# PROFISSIONAIS (CRUD + STATUS)
# =============================================================================
def listar_profissionais():
    db = get_db()
    return db.execute(
        """
        SELECT
            id,
            nome,
            telefone,
            dias_trabalho,
            hora_inicio,
            hora_fim,
            ativo,
            tipo_comissao,
            valor_comissao
        FROM profissionais
        ORDER BY nome
        """
    ).fetchall()


def criar_profissional(
    nome,
    telefone,
    dias_trabalho=None,
    hora_inicio=None,
    hora_fim=None,
    ativo=1,
):
    db = get_db()

    nome = _clean_str(nome)
    telefone = _clean_str(telefone)
    dias_trabalho = _clean_str(dias_trabalho) or None
    hora_inicio = _clean_str(hora_inicio) or None
    hora_fim = _clean_str(hora_fim) or None
    ativo = _to_int(ativo, "ativo")

    if not nome:
        raise ValueError("nome é obrigatório")
    if not telefone:
        raise ValueError("telefone é obrigatório")
    if ativo not in (0, 1):
        raise ValueError("ativo inválido (use 0 ou 1)")

    dup = db.execute(
        """
        SELECT id
        FROM profissionais
        WHERE telefone = ?
        LIMIT 1
        """,
        (telefone,),
    ).fetchone()
    if dup:
        raise ValueError("Já existe um profissional com esse telefone")

    cur = db.execute(
        """
        INSERT INTO profissionais (
            nome,
            telefone,
            dias_trabalho,
            hora_inicio,
            hora_fim,
            ativo
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (nome, telefone, dias_trabalho, hora_inicio, hora_fim, ativo),
    )

    db.commit()
    return cur.lastrowid


def atualizar_profissional(
    profissional_id: int,
    nome: str | None,
    telefone: str | None,
    dias_trabalho: str | None,
    hora_inicio: str | None,
    hora_fim: str | None,
    ativo: int = 1,
):
    profissional_id = _to_int(profissional_id, "profissional_id")
    ativo = _to_int(ativo, "ativo")

    nome = _clean_str(nome)
    telefone = _clean_str(telefone)

    if not nome:
        raise ValueError("nome é obrigatório")
    if not telefone:
        raise ValueError("telefone é obrigatório")
    if ativo not in (0, 1):
        raise ValueError("ativo inválido (use 0 ou 1)")

    dias_trabalho = _clean_str(dias_trabalho) or None
    hora_inicio = _clean_str(hora_inicio) or None
    hora_fim = _clean_str(hora_fim) or None

    db = get_db()
    existe = _buscar_profissional(db, profissional_id)
    if not existe:
        return False

    dup = db.execute(
        """
        SELECT id
        FROM profissionais
        WHERE telefone = ?
          AND id <> ?
        LIMIT 1
        """,
        (telefone, profissional_id),
    ).fetchone()
    if dup:
        raise ValueError("Já existe um profissional com esse telefone")

    cur = db.execute(
        """
        UPDATE profissionais
        SET
            nome = ?,
            telefone = ?,
            dias_trabalho = ?,
            hora_inicio = ?,
            hora_fim = ?,
            ativo = ?
        WHERE id = ?
        """,
        (nome, telefone, dias_trabalho,
         hora_inicio, hora_fim, ativo, profissional_id),
    )

    db.commit()
    return cur.rowcount > 0


def set_profissional_ativo(profissional_id: int, ativo: int) -> bool:
    profissional_id = _to_int(profissional_id, "profissional_id")
    ativo = _to_int(ativo, "ativo")

    if ativo not in (0, 1):
        raise ValueError("ativo inválido (use 0 ou 1)")

    db = get_db()
    cur = db.execute(
        """
        UPDATE profissionais
        SET ativo = ?
        WHERE id = ?
        """,
        (ativo, profissional_id),
    )
    db.commit()
    return cur.rowcount > 0


# =============================================================================
# COMISSÕES
# Regras:
# - profissionais.tipo_comissao / valor_comissao = regra atual de fallback
# - comissoes_profissionais = histórico por vigência
# =============================================================================
def atualizar_comissao_profissional(
    profissional_id: int,
    tipo_comissao: str,
    valor_comissao: float,
) -> bool:
    """
    Atualiza a comissão atual do profissional no cadastro principal.

    Essa configuração funciona como fallback quando não existe regra histórica
    em comissoes_profissionais para a data do atendimento.
    """
    profissional_id = _to_int(profissional_id, "profissional_id")
    tipo = _normalizar_tipo_comissao(tipo_comissao)
    valor = _validar_valor_comissao(tipo, valor_comissao)

    db = get_db()
    prof = _buscar_profissional(db, profissional_id)

    if not prof:
        raise ValueError("Profissional não encontrado")

    if int(prof["ativo"] or 0) != 1:
        raise ValueError("Profissional não encontrado ou inativo")

    cur = db.execute(
        """
        UPDATE profissionais
        SET tipo_comissao = ?, valor_comissao = ?
        WHERE id = ?
        """,
        (tipo, valor, profissional_id),
    )
    db.commit()
    return cur.rowcount > 0


def criar_comissao_profissional(
    profissional_id: int,
    tipo_comissao: str,
    valor_comissao: float,
    vigente_desde: str,
) -> int:
    """
    Cria uma regra histórica de comissão com data de vigência.

    Também atualiza o cadastro principal do profissional para manter coerência
    com o fallback usado no fechamento e no pagamento do agendamento.
    """
    profissional_id = _to_int(profissional_id, "profissional_id")
    tipo = _normalizar_tipo_comissao(tipo_comissao)
    valor = _validar_valor_comissao(tipo, valor_comissao)
    vigente_desde = _validar_data_iso(vigente_desde, "vigente_desde")

    db = get_db()

    prof = _buscar_profissional(db, profissional_id)
    if not prof:
        raise ValueError("Profissional não encontrado")
    if int(prof["ativo"] or 0) != 1:
        raise ValueError("Profissional não encontrado ou inativo")

    try:
        db.execute("BEGIN IMMEDIATE")

        cur = db.execute(
            """
            INSERT INTO comissoes_profissionais (
                profissional_id,
                tipo_comissao,
                valor_comissao,
                vigente_desde
            )
            VALUES (?, ?, ?, ?)
            """,
            (profissional_id, tipo, valor, vigente_desde),
        )

        db.execute(
            """
            UPDATE profissionais
            SET tipo_comissao = ?, valor_comissao = ?
            WHERE id = ?
            """,
            (tipo, valor, profissional_id),
        )

        db.commit()
        return cur.lastrowid

    except Exception:
        db.execute("ROLLBACK")
        raise


def listar_comissoes_profissional(profissional_id: int):
    profissional_id = _to_int(profissional_id, "profissional_id")

    db = get_db()
    prof = _buscar_profissional(db, profissional_id)
    if not prof:
        raise ValueError("Profissional não encontrado")

    return db.execute(
        """
        SELECT
            id,
            profissional_id,
            tipo_comissao,
            valor_comissao,
            vigente_desde,
            criado_em
        FROM comissoes_profissionais
        WHERE profissional_id = ?
        ORDER BY date(vigente_desde) DESC, id DESC
        """,
        (profissional_id,),
    ).fetchall()


# =============================================================================
# BLOQUEIOS
# =============================================================================
def listar_bloqueios(data=None):
    db = get_db()

    if data:
        return db.execute(
            """
            SELECT
                id,
                profissional_id,
                data,
                COALESCE(dia_inteiro, 1) AS dia_inteiro,
                motivo
            FROM bloqueios
            WHERE data = ?
            ORDER BY id DESC
            """,
            (data,),
        ).fetchall()

    return db.execute(
        """
        SELECT
            id,
            profissional_id,
            data,
            COALESCE(dia_inteiro, 1) AS dia_inteiro,
            motivo
        FROM bloqueios
        ORDER BY id DESC
        """
    ).fetchall()


def excluir_bloqueio(bloqueio_id: int) -> bool:
    bloqueio_id = _to_int(bloqueio_id, "bloqueio_id")

    db = get_db()
    cur = db.execute(
        """
        DELETE FROM bloqueios
        WHERE id = ?
        """,
        (bloqueio_id,),
    )
    db.commit()
    return cur.rowcount > 0
