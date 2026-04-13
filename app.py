from flask import Flask, request, render_template
from flask_cors import CORS
import sqlite3

from config import DB_PATH, TEMPLATES_DIR, STATIC_DIR
from database.db import close_db, get_db
from utils.responses import ok, fail

# migrations
from database.migrations import (
    ensure_servicos_ativo_column,
    ensure_movimentacoes_caixa_table,
    ensure_movimentacoes_caixa_status_column,
    ensure_movimentacoes_caixa_comissao_column,
    ensure_vendas_produtos_table,
    ensure_profissionais_comissao_columns,
    ensure_comissoes_profissionais_table,
    ensure_estoque_tables,
    ensure_produtos_extra_columns,
    ensure_clientes_criado_em_column,
    ensure_profissionais_agenda_columns,
    ensure_bloqueios_dia_inteiro_column,
    ensure_servicos_extra_columns,
    ensure_configuracoes_tables,
    ensure_planos_tables,
    ensure_movimentacoes_caixa_planos_rules,
)

from services.configuracoes import (
    get_config_geral,
    update_config_geral,
    get_config_horarios,
    update_config_horarios,
)

from services.clientes import (
    listar_clientes,
    criar_cliente,
    atualizar_cliente,
    excluir_cliente,
    buscar_cliente_por_telefone
)

from services.planos import (
    criar_plano,
    listar_planos_com_servicos_e_qtd,
    vincular_cliente_plano,
    obter_plano_ativo_cliente,
    registrar_uso_plano,
    usar_plano_em_agendamento,
    renovar_plano,
    cancelar_plano,
    listar_clientes_do_plano,
    atualizar_status_plano,
    obter_kpis_planos,
    obter_cliente_plano_por_id,
    atualizar_cliente_plano,
)

from services.profissionais_service import (
    listar_profissionais,
    criar_profissional,
    atualizar_comissao_profissional,
    criar_comissao_profissional,
    listar_comissoes_profissional,
    atualizar_profissional,
    set_profissional_ativo,
    listar_bloqueios,
    excluir_bloqueio,
)

from services.servicos import (
    listar_servicos,
    criar_servico,
    buscar_servico_por_id,
    atualizar_servico,
    set_servico_ativo,
    excluir_servico,
    kpis_servicos,
)

from services.agendamentos import (
    criar_agendamento,
    listar_agendamentos,
    listar_horarios_disponiveis,
    listar_agendamentos_por_profissional_e_data,
    atualizar_status_agendamento,
    editar_agendamento,
    pagar_agendamento,
)

from services.bloqueios import criar_bloqueio

from services.caixa import (
    criar_movimentacao_caixa,
    listar_movimentacoes_caixa,
    fechamento_caixa_por_data,
    calcular_comissao_por_data,
    calcular_comissao_diaria,
    calcular_comissao_mensal,
    resumo_caixa_mensal,
    atualizar_status_movimentacao_restrito,
    obter_comissao_vigente,
)

from services.produtos import (
    criar_produto,
    listar_produtos,
    listar_produtos_baixo_estoque,
    atualizar_produto,
    entrada_estoque,
    saida_estoque,
)

from services.relatorios import (
    listar_profissionais_relatorio,
    resumo_relatorio,
    listar_movimentacoes,
)
from utils.relatorios_pdf import gerar_pdf_relatorio


app = Flask(__name__, template_folder=TEMPLATES_DIR, static_folder=STATIC_DIR)
CORS(app)
app.config["DATABASE"] = DB_PATH


def get_json_body():
    return request.get_json(silent=True) or {}


def parse_int_field(value, field_name):
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} inválido")


def parse_optional_int_field(value, field_name):
    if value is None or value == "":
        return None
    return parse_int_field(value, field_name)


def map_service_error(message: str):
    msg = (message or "").strip()
    low = msg.lower()

    if "não encontrado" in low:
        return fail(msg, status=404)

    if "já está concluído" in low:
        return fail(msg, status=409)

    if "já possui pagamento" in low:
        return fail(msg, status=409)

    if "já consumiu um uso de plano" in low:
        return fail(msg, status=409)

    if "já possui plano ativo" in low:
        return fail(msg, status=409)

    if "estoque insuficiente" in low:
        return fail(msg, status=409)

    if "horário indisponível" in low:
        return fail(msg, status=409)

    if "cancelado" in low and "não pode" in low:
        return fail(msg, status=409)

    return fail(msg, status=400)


def run_startup_migrations() -> None:
    with app.app_context():
        ensure_servicos_ativo_column()

        ensure_movimentacoes_caixa_table()
        ensure_movimentacoes_caixa_status_column()
        ensure_movimentacoes_caixa_comissao_column()
        ensure_vendas_produtos_table()

        ensure_profissionais_comissao_columns()
        ensure_comissoes_profissionais_table()

        ensure_estoque_tables()
        ensure_produtos_extra_columns()

        ensure_clientes_criado_em_column()
        ensure_profissionais_agenda_columns()
        ensure_bloqueios_dia_inteiro_column()
        ensure_servicos_extra_columns()
        ensure_configuracoes_tables()

        ensure_planos_tables()
        ensure_movimentacoes_caixa_planos_rules()


@app.route("/")
def home():
    return "Sistema de agendamento - backend ativo"


@app.route("/agenda-page")
def agenda_page():
    return render_template("agenda.html")


@app.route("/financeiro-page")
def financeiro_page():
    return render_template("financeiro.html")


@app.route("/estoque-page")
def estoque_page():
    return render_template("estoque.html")


@app.route("/clientes-page")
def clientes_page():
    return render_template("clientes.html")


@app.route("/profissionais-page")
def profissionais_page():
    return render_template("profissionais.html")


@app.route("/servicos-page")
def servicos_page():
    return render_template("servicos.html")


@app.route("/relatorios-page")
def relatorios_page():
    return render_template("relatorios.html")


@app.route("/configuracoes-page")
def configuracoes_page():
    return render_template("configuracoes.html")


@app.route("/planos-page")
def planos_page():
    return render_template("planos.html")


@app.route("/clientes", methods=["GET"])
def get_clientes():
    clientes = listar_clientes()
    return ok(data=[dict(c) for c in clientes], status=200)


@app.route("/clientes", methods=["POST"])
def post_cliente():
    data = get_json_body()
    nome = data.get("nome")
    telefone = data.get("telefone")
    observacoes = data.get("observacoes")

    if not nome or not telefone:
        return fail("Nome e telefone são obrigatórios", status=400)

    try:
        cliente_id = criar_cliente(nome, telefone, observacoes)
    except ValueError as e:
        return map_service_error(str(e))

    return ok(data={"id": cliente_id}, mensagem="Cliente criado com sucesso", status=201)


@app.route("/clientes/busca", methods=["GET"])
def busca_clientes():
    termo = request.args.get("q", "").strip()
    if not termo:
        return ok(data=[], status=200)

    db = get_db()
    rows = db.execute(
        """
        SELECT id, nome, telefone
        FROM clientes
        WHERE nome LIKE ?
           OR telefone LIKE ?
        ORDER BY nome
        LIMIT 20
        """,
        (f"%{termo}%", f"%{termo}%"),
    ).fetchall()

    return ok(data=[dict(r) for r in rows], status=200)


@app.route("/clientes/<int:cliente_id>", methods=["PUT"])
def put_cliente(cliente_id):
    data = get_json_body()

    nome = data.get("nome")
    telefone = data.get("telefone")
    observacoes = data.get("observacoes")

    if not nome or not telefone:
        return fail("nome e telefone são obrigatórios", status=400)

    try:
        ok_update = atualizar_cliente(
            cliente_id=cliente_id,
            nome=nome,
            telefone=telefone,
            observacoes=observacoes,
        )
    except ValueError as e:
        return map_service_error(str(e))

    if not ok_update:
        return fail("Cliente não encontrado", status=404)

    return ok(mensagem="Cliente atualizado com sucesso", status=200)


@app.route("/clientes/<int:cliente_id>", methods=["DELETE"])
def delete_cliente(cliente_id):
    try:
        ok_del = excluir_cliente(cliente_id)
        if not ok_del:
            return fail("Cliente não encontrado", status=404)
        return ok(mensagem="Cliente excluído com sucesso", status=200)
    except ValueError as e:
        if str(e) == "CLIENTE_COM_HISTORICO":
            return fail("Cliente possui visitas/histórico e não pode ser excluído.", status=409)
        return map_service_error(str(e))


@app.route("/clientes/por-telefone", methods=["GET"])
def get_cliente_por_telefone():
    telefone = request.args.get("telefone", "").strip()

    if not telefone:
        return ok(data=None, status=200)

    try:
        cliente = buscar_cliente_por_telefone(telefone)
    except ValueError as e:
        return map_service_error(str(e))

    return ok(data=dict(cliente) if cliente else None, status=200)


@app.route("/profissionais", methods=["GET"])
def get_profissionais():
    profissionais = listar_profissionais()
    return ok(data=[dict(p) for p in profissionais], status=200)


@app.route("/profissionais", methods=["POST"])
def post_profissional():
    data = get_json_body()

    try:
        prof_id = criar_profissional(
            nome=data.get("nome"),
            telefone=data.get("telefone"),
            dias_trabalho=data.get("dias_trabalho"),
            hora_inicio=data.get("hora_inicio"),
            hora_fim=data.get("hora_fim"),
            ativo=data.get("ativo", 1),
        )
    except ValueError as e:
        return map_service_error(str(e))

    return ok(data={"id": prof_id}, mensagem="Profissional criado com sucesso", status=201)


@app.route("/profissionais/<int:profissional_id>", methods=["PUT"])
def put_profissional(profissional_id):
    data = get_json_body()

    try:
        ok_upd = atualizar_profissional(
            profissional_id=profissional_id,
            nome=data.get("nome"),
            telefone=data.get("telefone"),
            dias_trabalho=data.get("dias_trabalho"),
            hora_inicio=data.get("hora_inicio"),
            hora_fim=data.get("hora_fim"),
            ativo=data.get("ativo", 1),
        )
    except ValueError as e:
        return map_service_error(str(e))

    if not ok_upd:
        return fail("Profissional não encontrado", status=404)

    return ok(mensagem="Profissional atualizado com sucesso", status=200)


@app.route("/profissionais/<int:profissional_id>/status", methods=["PUT"])
def put_prof_status(profissional_id):
    data = get_json_body()

    ativo = data.get("ativo", None)
    if ativo is None:
        status = (data.get("status") or "").strip().lower()
        if status in ("ativo", "1", "true"):
            ativo = 1
        elif status in ("inativo", "0", "false"):
            ativo = 0
        else:
            return fail("Informe 'ativo' (0/1) ou 'status' ('ativo'/'inativo')", status=400)

    try:
        ok_upd = set_profissional_ativo(profissional_id, int(ativo))
    except ValueError as e:
        return map_service_error(str(e))

    if not ok_upd:
        return fail("Profissional não encontrado", status=404)

    return ok(mensagem="Status atualizado com sucesso", status=200)


@app.route("/bloqueios", methods=["GET"])
def get_bloqueios():
    data = request.args.get("data")
    rows = listar_bloqueios(data=data)
    return ok(data=[dict(r) for r in rows], status=200)


@app.route("/bloqueios", methods=["POST"])
def post_bloqueio():
    data = get_json_body()

    try:
        bloqueio_id = criar_bloqueio(
            profissional_id=data.get("profissional_id"),
            data=data.get("data"),
            dia_inteiro=data.get("dia_inteiro", 1),
            hora_inicio=data.get("hora_inicio"),
            hora_fim=data.get("hora_fim"),
            motivo=data.get("motivo"),
        )
    except ValueError as e:
        return map_service_error(str(e))

    return ok(data={"id": bloqueio_id}, mensagem="Bloqueio criado com sucesso", status=201)


@app.route("/bloqueios/<int:bloqueio_id>", methods=["DELETE"])
def delete_bloqueio(bloqueio_id):
    ok_del = excluir_bloqueio(bloqueio_id)
    if not ok_del:
        return fail("Bloqueio não encontrado", status=404)
    return ok(mensagem="Folga removida com sucesso", status=200)


@app.route("/profissionais/<int:profissional_id>/comissao", methods=["PUT"])
def put_comissao_profissional(profissional_id):
    data = get_json_body()
    tipo_comissao = data.get("tipo_comissao")
    valor_comissao = data.get("valor_comissao")

    if tipo_comissao is None or valor_comissao is None:
        return fail("tipo_comissao e valor_comissao são obrigatórios", status=400)

    try:
        ok_update = atualizar_comissao_profissional(
            profissional_id, tipo_comissao, valor_comissao)
    except ValueError as e:
        return map_service_error(str(e))

    if not ok_update:
        return fail("Profissional não encontrado ou inativo", status=404)

    return ok(mensagem="Comissão atualizada com sucesso", status=200)


@app.route("/profissionais/<int:profissional_id>/comissoes", methods=["POST"])
def post_comissao_profissional(profissional_id):
    data = get_json_body()
    tipo_comissao = data.get("tipo_comissao")
    valor_comissao = data.get("valor_comissao")
    vigente_desde = data.get("vigente_desde")

    if tipo_comissao is None or valor_comissao is None or vigente_desde is None:
        return fail("tipo_comissao, valor_comissao e vigente_desde são obrigatórios", status=400)

    try:
        comissao_id = criar_comissao_profissional(
            profissional_id, tipo_comissao, valor_comissao, vigente_desde)
    except ValueError as e:
        return map_service_error(str(e))

    return ok(mensagem="Comissão registrada com sucesso", data={"id": comissao_id}, status=201)


@app.route("/profissionais/<int:profissional_id>/comissoes", methods=["GET"])
def get_comissoes_profissional(profissional_id):
    try:
        comissoes = listar_comissoes_profissional(profissional_id)
    except ValueError as e:
        return map_service_error(str(e))

    return ok(data=[dict(c) for c in comissoes], status=200)


@app.route("/profissionais/<int:profissional_id>/comissao/vigente", methods=["GET"])
def get_comissao_vigente_profissional(profissional_id):
    data_ref = request.args.get("data")
    if not data_ref:
        return fail("data é obrigatória (YYYY-MM-DD)", status=400)

    db = get_db()
    row = obter_comissao_vigente(db, profissional_id, data_ref)

    if not row:
        return ok(data={"tipo_comissao": None, "valor_comissao": None}, status=200)

    return ok(
        data={
            "tipo_comissao": row["tipo_comissao"],
            "valor_comissao": float(row["valor_comissao"]),
        },
        status=200,
    )


@app.route("/comissoes/fechamento", methods=["GET"])
def get_comissao_fechamento():
    profissional_id = request.args.get("profissional_id")
    data_ref = request.args.get("data")

    if not profissional_id or not data_ref:
        return fail("profissional_id e data são obrigatórios (YYYY-MM-DD)", status=400)

    try:
        profissional_id = int(profissional_id)
    except ValueError:
        return fail("profissional_id inválido", status=400)

    resumo = calcular_comissao_por_data(profissional_id, data_ref)
    return ok(data=resumo, status=200)


@app.route("/comissoes/diaria", methods=["GET"])
def get_comissao_diaria():
    profissional_id = request.args.get("profissional_id")
    data_ref = request.args.get("data")

    if not profissional_id or not data_ref:
        return fail("profissional_id e data são obrigatórios (YYYY-MM-DD)", status=400)

    try:
        profissional_id = int(profissional_id)
    except ValueError:
        return fail("profissional_id inválido", status=400)

    try:
        resumo = calcular_comissao_diaria(profissional_id, data_ref)
    except ValueError as e:
        return map_service_error(str(e))

    return ok(data=resumo, status=200)


@app.route("/comissoes/mensal", methods=["GET"])
def get_comissao_mensal():
    profissional_id = request.args.get("profissional_id")
    ano = request.args.get("ano")
    mes = request.args.get("mes")

    if not profissional_id or not ano or not mes:
        return fail("profissional_id, ano e mes são obrigatórios", status=400)

    try:
        profissional_id = int(profissional_id)
    except ValueError:
        return fail("profissional_id inválido", status=400)

    try:
        resumo = calcular_comissao_mensal(profissional_id, ano, mes)
    except ValueError as e:
        return map_service_error(str(e))

    return ok(data=resumo, status=200)


@app.route("/servicos", methods=["GET"])
def get_servicos():
    q = request.args.get("q")
    categoria = request.args.get("categoria")
    status = request.args.get("status")

    try:
        servicos = listar_servicos(q=q, categoria=categoria, status=status)
    except ValueError as e:
        return map_service_error(str(e))

    return ok(data=[dict(s) for s in servicos], status=200)


@app.route("/servicos/kpis", methods=["GET"])
def get_servicos_kpis():
    try:
        data = kpis_servicos()
    except ValueError as e:
        return map_service_error(str(e))
    return ok(data=data, status=200)


@app.route("/servicos", methods=["POST"])
def post_servico():
    data = get_json_body()

    try:
        servico_id = criar_servico(
            nome=data.get("nome"),
            duracao=data.get("duracao"),
            preco=data.get("preco"),
            categoria=data.get("categoria"),
            descricao=data.get("descricao"),
            ativo=data.get("ativo", 1),
        )
    except ValueError as e:
        return map_service_error(str(e))

    return ok(data={"id": servico_id}, mensagem="Serviço criado com sucesso", status=201)


@app.route("/servicos/<int:servico_id>", methods=["GET"])
def get_servico_por_id(servico_id):
    servico = buscar_servico_por_id(servico_id)
    if not servico:
        return fail("Serviço não encontrado", status=404)
    return ok(data=dict(servico), status=200)


@app.route("/servicos/<int:servico_id>", methods=["PUT"])
def put_servico(servico_id):
    data = get_json_body()

    try:
        ok_upd = atualizar_servico(
            servico_id=servico_id,
            nome=data.get("nome"),
            duracao=data.get("duracao"),
            preco=data.get("preco"),
            categoria=data.get("categoria"),
            descricao=data.get("descricao"),
            ativo=data.get("ativo", 1),
        )
    except ValueError as e:
        return map_service_error(str(e))

    if not ok_upd:
        return fail("Serviço não encontrado", status=404)

    return ok(mensagem="Serviço atualizado com sucesso", status=200)


@app.route("/servicos/<int:servico_id>/status", methods=["PUT"])
def put_servico_status(servico_id):
    data = get_json_body()

    ativo = data.get("ativo", None)
    if ativo is None:
        status = (data.get("status") or "").strip().lower()
        if status in ("ativo", "1", "true"):
            ativo = 1
        elif status in ("inativo", "0", "false"):
            ativo = 0
        else:
            return fail("Informe 'ativo' (0/1) ou 'status' ('ativo'/'inativo')", status=400)

    try:
        ok_upd = set_servico_ativo(servico_id, int(ativo))
    except ValueError as e:
        return map_service_error(str(e))

    if not ok_upd:
        return fail("Serviço não encontrado", status=404)

    return ok(mensagem="Status atualizado com sucesso", status=200)


@app.route("/servicos/<int:servico_id>", methods=["DELETE"])
def delete_servico(servico_id):
    try:
        ok_del = excluir_servico(servico_id)
    except ValueError as e:
        if str(e) == "SERVICO_COM_HISTORICO":
            return fail("Serviço já foi usado em agendamentos e não pode ser excluído.", status=409)
        return map_service_error(str(e))

    if not ok_del:
        return fail("Serviço não encontrado", status=404)

    return ok(mensagem="Serviço excluído com sucesso", status=200)


@app.route("/agendamentos", methods=["POST"])
def post_agendamento():
    data = get_json_body()

    cliente_id = data.get("cliente_id")
    profissional_id = data.get("profissional_id")
    servico_id = data.get("servico_id")
    data_agendamento = data.get("data")
    horario = data.get("horario")

    if not all([cliente_id, profissional_id, servico_id, data_agendamento, horario]):
        return fail("Todos os campos são obrigatórios", status=400)

    try:
        cliente_id = parse_int_field(cliente_id, "cliente_id")
        profissional_id = parse_int_field(profissional_id, "profissional_id")
        servico_id = parse_int_field(servico_id, "servico_id")

        sucesso = criar_agendamento(
            cliente_id,
            profissional_id,
            servico_id,
            data_agendamento,
            horario,
        )
    except ValueError as e:
        return map_service_error(str(e))

    if not sucesso:
        return fail("Horário indisponível para este profissional", status=409)

    return ok(mensagem="Agendamento criado com sucesso", status=201)


@app.route("/agendamentos", methods=["GET"])
def get_agendamentos():
    data_ref = request.args.get("data")

    try:
        agendamentos = listar_agendamentos(data_ref)
    except ValueError as e:
        return map_service_error(str(e))
    except Exception as e:
        return fail(f"Erro interno ao listar agendamentos: {str(e)}", status=500)

    return ok(data=[dict(a) for a in agendamentos], status=200)


@app.route("/agendamentos/filtro", methods=["GET"])
def get_agendamentos_por_profissional_e_data():
    profissional_id = request.args.get("profissional_id")
    data_ref = request.args.get("data")

    if not profissional_id or not data_ref:
        return fail("profissional_id e data são obrigatórios", status=400)

    try:
        profissional_id = int(profissional_id)
    except ValueError:
        return fail("profissional_id inválido", status=400)

    agendamentos = listar_agendamentos_por_profissional_e_data(
        profissional_id, data_ref)
    return ok(data=[dict(a) for a in agendamentos], status=200)


@app.route("/agendamentos/<int:agendamento_id>/pagar", methods=["POST"])
def pagar_agendamento_route(agendamento_id):
    data = get_json_body()

    forma_pagamento = (data.get("forma_pagamento") or "").strip().lower()
    valor_servico = data.get("valor_servico")
    produtos = data.get("produtos")
    data_hora = data.get("data_hora")

    if forma_pagamento == "plano":
        return fail(
            "forma_pagamento 'plano' não é permitida neste fluxo. Use o fluxo próprio de usar plano no agendamento.",
            status=400,
        )

    if produtos is not None and not isinstance(produtos, list):
        return fail("produtos deve ser uma lista", status=400)

    db = get_db()
    ag = db.execute(
        """
        SELECT status
        FROM agendamentos
        WHERE id = ?
        """,
        (agendamento_id,),
    ).fetchone()

    if not ag:
        return fail("Agendamento não encontrado", status=404)

    status_atual = (ag["status"] or "").strip().lower()
    if status_atual == "concluido":
        return fail("Agendamento já está concluído", status=409)
    if status_atual == "cancelado":
        return fail("Agendamento cancelado não pode ser pago", status=409)

    resp = pagar_agendamento(
        agendamento_id=agendamento_id,
        forma_pagamento=forma_pagamento,
        valor_servico=valor_servico,
        produtos=produtos,
        data_hora=data_hora,
    )

    if not resp.get("ok"):
        err = resp.get("error", {})
        code = (err.get("code") or "").upper()
        msg = err.get("message") or "Erro ao processar pagamento."

        if code == "NOT_FOUND":
            return fail(msg, status=404)
        if code in {"ALREADY_CONCLUDED", "ALREADY_PAID", "ALREADY_EXISTS", "NO_STOCK", "CANCELLED"}:
            return fail(msg, status=409)
        if code in {"INVALID_AMOUNT", "INVALID_PRODUCTS", "INVALID_PRODUCT", "MOV_ERROR", "INVALID_PAYMENT_METHOD"}:
            return fail(msg, status=400)
        if code == "INTERNAL_ERROR":
            return fail(msg, status=500)

        return fail(msg, status=400)

    return ok(data=resp["data"], mensagem="Agendamento pago e concluído", status=200)


@app.route("/agendamentos/<int:agendamento_id>/status", methods=["PUT"])
def put_status_agendamento(agendamento_id):
    data = get_json_body()
    novo_status = (data.get("status") or "").strip().lower()

    if not novo_status:
        return fail("status é obrigatório", status=400)

    permitidos = {"confirmado", "aguardando", "cancelado"}
    if novo_status not in permitidos:
        return fail("status inválido. Use: confirmado, aguardando, cancelado", status=400)

    try:
        atualizar_status_agendamento(agendamento_id, novo_status)
    except ValueError as e:
        return map_service_error(str(e))

    return ok(mensagem="Status atualizado com sucesso", status=200)


@app.route("/agendamentos/<int:agendamento_id>", methods=["PUT"])
def put_agendamento(agendamento_id):
    data = get_json_body()

    cliente_id = data.get("cliente_id")
    profissional_id = data.get("profissional_id")
    servico_id = data.get("servico_id")
    data_agendamento = data.get("data")
    horario = data.get("horario")

    if not all([cliente_id, profissional_id, servico_id, data_agendamento, horario]):
        return fail("Todos os campos são obrigatórios", status=400)

    try:
        sucesso = editar_agendamento(
            agendamento_id,
            parse_int_field(cliente_id, "cliente_id"),
            parse_int_field(profissional_id, "profissional_id"),
            parse_int_field(servico_id, "servico_id"),
            data_agendamento,
            horario,
        )
    except ValueError as e:
        return map_service_error(str(e))
    except sqlite3.OperationalError as e:
        return fail(str(e), status=500)

    if not sucesso:
        return fail("Horário indisponível para este profissional", status=409)

    return ok(mensagem="Agendamento atualizado com sucesso", status=200)


@app.route("/produtos", methods=["GET"])
def get_produtos():
    somente_ativos = request.args.get("ativos") == "1"
    produtos = listar_produtos(somente_ativos=somente_ativos)
    return ok(data=[dict(p) for p in produtos], status=200)


@app.route("/produtos", methods=["POST"])
def post_produto():
    data = get_json_body()

    try:
        produto_id = criar_produto(
            nome=data.get("nome"),
            categoria=data.get("categoria"),
            marca=data.get("marca"),
            preco_custo=data.get("preco_custo", 0),
            preco_venda=data.get("preco_venda", 0),
            estoque_inicial=data.get("estoque_inicial", 0),
            estoque_minimo=data.get("estoque_minimo", 0),
        )
    except ValueError as e:
        return map_service_error(str(e))

    return ok(mensagem="Produto criado com sucesso", data={"id": produto_id}, status=201)


@app.route("/produtos/<int:produto_id>", methods=["PUT"])
def put_produto(produto_id):
    data = get_json_body()

    try:
        ok_update = atualizar_produto(
            produto_id=produto_id,
            nome=data.get("nome"),
            categoria=data.get("categoria"),
            marca=data.get("marca"),
            preco_custo=data.get("preco_custo", 0),
            preco_venda=data.get("preco_venda", 0),
            estoque_minimo=data.get("estoque_minimo", 0),
            ativo=data.get("ativo", 1),
        )
    except ValueError as e:
        return map_service_error(str(e))

    if not ok_update:
        return fail("Produto não encontrado", status=404)

    return ok(mensagem="Produto atualizado com sucesso", status=200)


@app.route("/produtos/baixo_estoque", methods=["GET"])
def get_produtos_baixo_estoque():
    produtos = listar_produtos_baixo_estoque()
    return ok(data=[dict(p) for p in produtos], status=200)


@app.route("/produtos/<int:produto_id>/entrada", methods=["POST"])
def post_entrada(produto_id):
    data = get_json_body()

    try:
        resp = entrada_estoque(
            produto_id=produto_id,
            quantidade=data.get("quantidade"),
            descricao=data.get("descricao"),
            data_hora=data.get("data_hora"),
            forma_pagamento=data.get("forma_pagamento"),
        )
    except ValueError as e:
        return map_service_error(str(e))

    return ok(mensagem="Entrada registrada", data=resp, status=200)


@app.route("/produtos/<int:produto_id>/saida", methods=["POST"])
def post_saida(produto_id):
    data = get_json_body()

    try:
        resp = saida_estoque(
            produto_id=produto_id,
            quantidade=data.get("quantidade"),
            descricao=data.get("descricao"),
            data_hora=data.get("data_hora"),
            forma_pagamento=data.get("forma_pagamento"),
        )
    except ValueError as e:
        return map_service_error(str(e))

    return ok(mensagem="Saída registrada", data=resp, status=200)


@app.route("/planos", methods=["POST"])
def post_plano():
    data = get_json_body()

    try:
        plano_id = criar_plano(
            nome=data.get("nome"),
            valor_mensal=data.get("valor_mensal"),
            usos_por_mes=data.get("usos_por_mes"),
            servicos=data.get("servicos"),
            ativo=data.get("ativo", 1),
        )
    except ValueError as e:
        return map_service_error(str(e))

    return ok(data={"id": plano_id}, mensagem="Plano criado com sucesso", status=201)


@app.route("/planos", methods=["GET"])
def get_planos():
    try:
        db = get_db()
        planos = listar_planos_com_servicos_e_qtd(db)
    except Exception as e:
        return fail(str(e), status=500)

    return ok(data=planos, status=200)


@app.route("/planos/kpis", methods=["GET"])
def get_planos_kpis():
    try:
        data = obter_kpis_planos()
        return ok(data=data, status=200)
    except Exception as e:
        return fail(str(e), status=500)


@app.route("/planos/<int:plano_id>", methods=["PUT"])
def put_plano_status(plano_id):
    data = get_json_body()

    if "ativo" not in data:
        return fail("Campo 'ativo' é obrigatório", status=400)

    try:
        resultado = atualizar_status_plano(plano_id, data.get("ativo"))
    except ValueError as e:
        return map_service_error(str(e))
    except Exception as e:
        return fail(str(e), status=500)

    mensagem = "Plano ativado com sucesso" if resultado["ativo"] else "Plano inativado com sucesso"
    return ok(data=resultado, mensagem=mensagem, status=200)


@app.route("/planos/<int:plano_id>/clientes", methods=["POST"])
def vincular_cliente_plano_route(plano_id):
    data = get_json_body()

    try:
        cliente_plano_id = vincular_cliente_plano(
            cliente_id=data.get("cliente_id"),
            plano_id=plano_id,
            forma_pagamento=data.get("forma_pagamento"),
            data_inicio=data.get("data_inicio"),
            proximo_vencimento=data.get("proximo_vencimento"),
            status=data.get("status", "aguardando_pagamento"),
        )
    except ValueError as e:
        return map_service_error(str(e))

    return ok(data={"id": cliente_plano_id}, mensagem="Cliente vinculado ao plano", status=201)


@app.route("/clientes/<int:cliente_id>/plano_ativo", methods=["GET"])
def get_plano_ativo_cliente(cliente_id):
    plano = obter_plano_ativo_cliente(cliente_id)

    if not plano:
        return ok(data=None, status=200)

    return ok(data=dict(plano), status=200)


@app.route("/clientes_planos/<int:cliente_plano_id>/uso", methods=["POST"])
def registrar_uso_plano_route(cliente_plano_id):
    data = get_json_body()

    try:
        registrar_uso_plano(
            cliente_plano_id=cliente_plano_id,
            agendamento_id=data.get("agendamento_id"),
        )
    except ValueError as e:
        return map_service_error(str(e))

    return ok(mensagem="Uso registrado com sucesso", status=200)


@app.route("/clientes_planos/<int:cliente_plano_id>/usar_agendamento", methods=["POST"])
def usar_plano_em_agendamento_route(cliente_plano_id):
    data = get_json_body()
    agendamento_id = data.get("agendamento_id")

    if not agendamento_id:
        return fail("agendamento_id é obrigatório", status=400)

    try:
        resultado = usar_plano_em_agendamento(
            cliente_plano_id=cliente_plano_id,
            agendamento_id=agendamento_id,
        )
    except ValueError as e:
        return map_service_error(str(e))

    return ok(
        data=resultado,
        mensagem="Plano usado no agendamento com sucesso",
        status=200,
    )


@app.route("/clientes_planos/<int:cliente_plano_id>/renovar", methods=["POST"])
def renovar_plano_route(cliente_plano_id):
    data = get_json_body()

    try:
        atualizado = renovar_plano(
            cliente_plano_id=cliente_plano_id,
            nova_data_vencimento=data.get("proximo_vencimento"),
            forma_pagamento=data.get("forma_pagamento"),
        )
    except ValueError as e:
        return map_service_error(str(e))

    return ok(data=atualizado, mensagem="Plano renovado com sucesso", status=200)


@app.route("/clientes_planos/<int:cliente_plano_id>/cancelar", methods=["PUT"])
def cancelar_plano_route(cliente_plano_id):
    try:
        cancelar_plano(cliente_plano_id)
    except ValueError as e:
        return map_service_error(str(e))

    return ok(mensagem="Plano cancelado com sucesso", status=200)


@app.route("/planos/<int:plano_id>/clientes", methods=["GET"])
def get_planos_clientes(plano_id):
    try:
        db = get_db()
        rows = listar_clientes_do_plano(db, plano_id)
        return ok(data=rows, status=200)
    except Exception as e:
        return fail(str(e), status=500)


@app.route("/clientes_planos/<int:cliente_plano_id>", methods=["PUT"])
def atualizar_cliente_plano_route(cliente_plano_id):
    data = get_json_body()

    try:
        atualizado = atualizar_cliente_plano(
            cliente_plano_id=cliente_plano_id,
            data_inicio=data.get("data_inicio"),
            proximo_vencimento=data.get("proximo_vencimento"),
            usos_totais=data.get("usos_totais"),
            usos_restantes=data.get("usos_restantes"),
            forma_pagamento=data.get("forma_pagamento"),
            status=data.get("status"),
        )
        return ok(data=atualizado, mensagem="Plano do cliente atualizado com sucesso", status=200)
    except ValueError as e:
        return map_service_error(str(e))
    except Exception as e:
        return fail(str(e), status=500)


@app.route("/financeiro", methods=["GET"])
def get_faturamento_diario():
    data = request.args.get("data")
    if not data:
        return fail("data é obrigatória (YYYY-MM-DD)", status=400)

    try:
        db = get_db()
        row = db.execute(
            """
            SELECT COALESCE(SUM(valor), 0) AS total
            FROM movimentacoes_caixa
            WHERE tipo = 'entrada'
              AND status = 'pago'
              AND date(data_hora) = date(?)
            """,
            (data,),
        ).fetchone()

        total = float(row["total"] or 0)
    except Exception as e:
        return fail(f"Erro ao calcular faturamento: {str(e)}", status=500)

    return ok(data={"data": data, "total": total}, status=200)


@app.route("/caixa/movimentacoes", methods=["POST"])
def post_movimentacao_caixa():
    data = get_json_body()

    try:
        mov_id = criar_movimentacao_caixa(
            tipo=data.get("tipo"),
            forma_pagamento=data.get("forma_pagamento"),
            valor=data.get("valor"),
            data_hora=data.get("data_hora"),
            descricao=data.get("descricao"),
            agendamento_id=data.get("agendamento_id"),
            profissional_id=data.get("profissional_id"),
            servico_id=data.get("servico_id"),
            status=data.get("status", "pendente"),
        )
    except ValueError as e:
        return map_service_error(str(e))

    return ok(data={"id": mov_id}, mensagem="Movimentação registrada com sucesso", status=201)


@app.route("/caixa/movimentacoes", methods=["GET"])
def get_movimentacoes_caixa():
    data = request.args.get("data")
    inicio = request.args.get("inicio")
    fim = request.args.get("fim")
    profissional_id = request.args.get("profissional_id")

    movs = listar_movimentacoes_caixa(
        data=data,
        inicio=inicio,
        fim=fim,
        profissional_id=profissional_id,
    )
    return ok(data=[dict(m) for m in movs], status=200)


@app.route("/caixa/fechamento", methods=["GET"])
def get_fechamento_caixa():
    data = request.args.get("data")
    if not data:
        return fail("data é obrigatória (YYYY-MM-DD)", status=400)

    resumo = fechamento_caixa_por_data(data)
    return ok(data=resumo, status=200)


@app.route("/caixa/resumo/mensal", methods=["GET"])
def get_resumo_caixa_mensal():
    ano = request.args.get("ano")
    mes = request.args.get("mes")

    if not ano or not mes:
        return fail("ano e mes são obrigatórios", status=400)

    try:
        resumo = resumo_caixa_mensal(ano, mes)
    except ValueError as e:
        return map_service_error(str(e))

    return ok(data=resumo, status=200)


@app.route("/caixa/movimentacoes/<int:mov_id>/status", methods=["PUT"])
def put_status_movimentacao(mov_id):
    data = get_json_body()
    status = data.get("status")
    if not status:
        return fail("status é obrigatório", status=400)

    try:
        ok_update = atualizar_status_movimentacao_restrito(mov_id, status)
    except ValueError as e:
        return map_service_error(str(e))

    if not ok_update:
        return fail("Movimentação não encontrada", status=404)

    return ok(mensagem="Status atualizado com sucesso", status=200)


@app.route("/relatorios/profissionais", methods=["GET"])
def get_relatorios_profissionais():
    try:
        rows = listar_profissionais_relatorio()
        return ok(data=[dict(r) for r in rows], status=200)

    except Exception as e:
        return fail(f"Erro ao listar profissionais do relatório: {str(e)}", status=500)


@app.route("/relatorios/resumo", methods=["GET"])
def get_relatorios_resumo():
    periodo = (request.args.get("periodo") or "este_mes").strip().lower()
    profissional_id = request.args.get("profissional_id")

    try:
        if profissional_id in (None, "", "todos"):
            profissional_id = None
        else:
            profissional_id = int(profissional_id)

        data = resumo_relatorio(
            periodo=periodo,
            profissional_id=profissional_id
        )

        return ok(data=data, status=200)

    except ValueError as e:
        return map_service_error(str(e))

    except Exception as e:
        return fail(f"Erro ao gerar resumo do relatório: {str(e)}", status=500)


@app.route("/relatorios/movimentacoes", methods=["GET"])
def get_relatorios_movimentacoes():
    periodo = (request.args.get("periodo") or "este_mes").strip().lower()
    profissional_id = request.args.get("profissional_id")
    tipo = (request.args.get("tipo") or "entrada").strip().lower()

    try:
        if profissional_id in (None, "", "todos"):
            profissional_id = None
        else:
            profissional_id = int(profissional_id)

        rows = listar_movimentacoes(
            periodo=periodo,
            profissional_id=profissional_id,
            tipo=tipo,
        )

        return ok(data=rows, status=200)

    except ValueError as e:
        return map_service_error(str(e))

    except Exception as e:
        return fail(f"Erro ao listar movimentações: {str(e)}", status=500)


@app.route("/relatorios/export/pdf", methods=["GET"])
def exportar_relatorio_pdf():
    periodo = (request.args.get("periodo") or "este_mes").strip().lower()
    profissional_id = request.args.get("profissional_id")

    try:
        if profissional_id in (None, "", "todos"):
            profissional_id = None
        else:
            profissional_id = int(profissional_id)

        resumo = resumo_relatorio(
            periodo=periodo,
            profissional_id=profissional_id
        )

        entradas = listar_movimentacoes(
            periodo=periodo,
            profissional_id=profissional_id,
            tipo="entrada"
        )

        saidas = listar_movimentacoes(
            periodo=periodo,
            profissional_id=profissional_id,
            tipo="saida"
        )

        pdf_bytes = gerar_pdf_relatorio(
            resumo=resumo,
            entradas=entradas,
            saidas=saidas
        )

        return app.response_class(
            pdf_bytes,
            mimetype="application/pdf",
            headers={
                "Content-Disposition": f'inline; filename="relatorio_{periodo}.pdf"'
            },
        )

    except ValueError as e:
        return map_service_error(str(e))

    except Exception as e:
        return fail(f"Erro ao gerar PDF do relatório: {str(e)}", status=500)


@app.route("/public/servicos", methods=["GET"])
def listar_servicos_publico():
    servicos = listar_servicos(status="ativo")
    return ok(data=[dict(s) for s in servicos], status=200)


@app.route("/public/profissionais", methods=["GET"])
def listar_profissionais_publico():
    db = get_db()
    profissionais = db.execute(
        """
        SELECT id, nome
        FROM profissionais
        WHERE ativo = 1
        ORDER BY nome
        """
    ).fetchall()
    return ok(data=[dict(p) for p in profissionais], status=200)


@app.route("/public/agendamentos", methods=["POST"])
def criar_agendamento_publico():
    data = get_json_body()

    cliente_id = data.get("cliente_id")
    profissional_id = data.get("profissional_id")
    servico_id = data.get("servico_id")
    data_agendamento = data.get("data")
    horario = data.get("horario")

    if not all([cliente_id, profissional_id, servico_id, data_agendamento, horario]):
        return fail("Dados incompletos", status=400)

    try:
        cliente_id = parse_int_field(cliente_id, "cliente_id")
        profissional_id = parse_int_field(profissional_id, "profissional_id")
        servico_id = parse_int_field(servico_id, "servico_id")

        sucesso = criar_agendamento(
            cliente_id,
            profissional_id,
            servico_id,
            data_agendamento,
            horario,
        )
    except ValueError as e:
        return map_service_error(str(e))

    if not sucesso:
        return fail("Horário indisponível", status=409)

    return ok(mensagem="Agendamento realizado com sucesso", status=201)


@app.route("/public/horarios", methods=["GET"])
def horarios_disponiveis():
    profissional_id = request.args.get("profissional_id")
    data_ref = request.args.get("data")

    if not profissional_id or not data_ref:
        return fail("profissional_id e data são obrigatórios (YYYY-MM-DD)", status=400)

    try:
        profissional_id = int(profissional_id)
    except ValueError:
        return fail("profissional_id inválido", status=400)

    try:
        horarios = listar_horarios_disponiveis(profissional_id, data_ref)
    except ValueError as e:
        return map_service_error(str(e))

    return ok(data=horarios, status=200)


@app.route("/configuracoes/geral", methods=["GET"])
def get_configuracoes_geral():
    try:
        data = get_config_geral()
        return ok(data=data, status=200)
    except Exception as e:
        return fail(f"Erro ao carregar configurações gerais: {str(e)}", status=500)


@app.route("/configuracoes/geral", methods=["PUT"])
def put_configuracoes_geral():
    data = get_json_body()

    try:
        atualizado = update_config_geral(data)
        return ok(data=atualizado, mensagem="Configurações gerais salvas com sucesso", status=200)
    except ValueError as e:
        return map_service_error(str(e))
    except Exception as e:
        return fail(f"Erro ao salvar configurações gerais: {str(e)}", status=500)


@app.route("/configuracoes/horarios", methods=["GET"])
def get_configuracoes_horarios():
    try:
        data = get_config_horarios()
        return ok(data=data, status=200)
    except Exception as e:
        return fail(f"Erro ao carregar horários: {str(e)}", status=500)


@app.route("/configuracoes/horarios", methods=["PUT"])
def put_configuracoes_horarios():
    data = get_json_body()
    horarios = data.get("horarios", [])

    try:
        atualizado = update_config_horarios(horarios)
        return ok(data=atualizado, mensagem="Horários salvos com sucesso", status=200)
    except ValueError as e:
        return map_service_error(str(e))
    except Exception as e:
        return fail(f"Erro ao salvar horários: {str(e)}", status=500)


@app.teardown_appcontext
def teardown_db(exception):
    close_db()


if __name__ == "__main__":
    from database.bootstrap import ensure_database_exists

    ensure_database_exists()
    run_startup_migrations()
    app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)
