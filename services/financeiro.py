from database.db import get_db


def calcular_faturamento_por_data(data):
    """
    Faturamento deve ser baseado no que foi efetivamente pago (caixa),
    e não no preço atual do serviço.

    Isso evita inconsistência histórica quando preços mudam.
    """
    db = get_db()

    resultado = db.execute(
        """
        SELECT COALESCE(SUM(valor), 0) AS total
        FROM movimentacoes_caixa
        WHERE date(data_hora) = date(?)
          AND tipo = 'entrada'
          AND status = 'pago'
        """,
        (data,)
    ).fetchone()

    return float(resultado["total"] or 0)
