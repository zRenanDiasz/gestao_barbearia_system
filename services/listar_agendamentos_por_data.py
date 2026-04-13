from database.db import get_db


def listar_agendamentos_por_data(data_ref):
    db = get_db()
    rows = db.execute("""
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
        WHERE a.data = ?
        ORDER BY a.horario ASC
    """, (data_ref,)).fetchall()
    return rows
