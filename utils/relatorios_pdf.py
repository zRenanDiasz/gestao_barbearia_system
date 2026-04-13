from __future__ import annotations

from io import BytesIO
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.lib.units import cm
from xml.sax.saxutils import escape


def _brl(v: float) -> str:
    try:
        return f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "R$ 0,00"


def _dt_br(iso: str) -> str:
    if not iso:
        return ""
    s = str(iso).replace("T", " ")
    try:
        dt = datetime.fromisoformat(s)
        return dt.strftime("%d/%m/%Y %H:%M")
    except Exception:
        return s


def _num(v, default=0.0) -> float:
    try:
        if v is None or v == "":
            return float(default)
        return float(v)
    except Exception:
        return float(default)


def _get_comissao(item: dict) -> float:
    if not isinstance(item, dict):
        return 0.0

    if "comissao_valor" in item:
        return _num(item.get("comissao_valor"), 0.0)

    if "comissao_total" in item:
        return _num(item.get("comissao_total"), 0.0)

    if "comissao" in item:
        return _num(item.get("comissao"), 0.0)

    return 0.0


def _P(text: str, style: ParagraphStyle) -> Paragraph:
    t = escape(str(text or "")).replace("\n", "<br/>")
    return Paragraph(t, style)


def _table(data, col_widths=None, repeat_rows: int = 1, align_right_cols=None):
    t = Table(data, colWidths=col_widths, repeatRows=repeat_rows)

    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#111827")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),

        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [
            colors.whitesmoke,
            colors.HexColor("#F3F4F6")
        ]),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D1D5DB")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]

    for col_idx in (align_right_cols or []):
        style_cmds.append(("ALIGN", (col_idx, 1), (col_idx, -1), "RIGHT"))

    t.setStyle(TableStyle(style_cmds))
    return t


def _montar_comissao_por_profissional(entradas: list[dict]) -> list[dict]:
    acc = {}

    for e in entradas or []:
        nome = (e.get("profissional_nome") or "").strip() or "Sem profissional"
        valor = _num(e.get("valor"))
        comissao = _get_comissao(e)

        if nome not in acc:
            acc[nome] = {
                "profissional_nome": nome,
                "atendimentos": 0,
                "faturamento": 0.0,
                "comissao_total": 0.0,
                "liquido": 0.0,
            }

        acc[nome]["atendimentos"] += 1
        acc[nome]["faturamento"] += valor
        acc[nome]["comissao_total"] += comissao
        acc[nome]["liquido"] += (valor - comissao)

    rows = list(acc.values())
    rows.sort(key=lambda x: (-x["comissao_total"], -
              x["faturamento"], x["profissional_nome"]))
    return rows


def gerar_pdf_relatorio(
    *,
    resumo: dict,
    entradas: list[dict],
    saidas: list[dict],
) -> bytes:
    buf = BytesIO()

    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=0.9 * cm,
        rightMargin=0.9 * cm,
        topMargin=0.9 * cm,
        bottomMargin=0.9 * cm,
        title="Relatório Financeiro",
    )

    styles = getSampleStyleSheet()
    h1 = styles["Heading1"]
    h2 = styles["Heading2"]
    p = styles["BodyText"]

    cell = ParagraphStyle(
        "cell",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=7.2,
        leading=8.8,
        spaceBefore=0,
        spaceAfter=0,
    )

    story = []

    periodo_label = ((resumo or {}).get("periodo") or {}).get("label", "—")
    k = ((resumo or {}).get("kpis") or {})
    por_forma = ((resumo or {}).get("por_forma") or {})
    mensal = ((resumo or {}).get("faturamento_mensal_6m") or [])
    top_servicos = ((resumo or {}).get("top_servicos") or [])
    top_profissionais = ((resumo or {}).get("top_profissionais") or [])

    comissao_entradas = sum(_get_comissao(e) for e in (entradas or []))
    comissao_kpi = _num(k.get("comissao_total"), comissao_entradas)
    if comissao_kpi == 0 and comissao_entradas > 0:
        comissao_kpi = comissao_entradas

    entradas_total = _num(k.get("entradas"))
    saidas_total = _num(k.get("saidas"))
    lucro_liquido = _num(k.get("lucro_liquido"),
                         entradas_total - saidas_total - comissao_kpi)
    atendimentos = int(_num(k.get("atendimentos"), 0))
    clientes = int(_num(k.get("clientes_no_periodo"), 0))
    uso_planos = int(_num(k.get("uso_planos"), 0))
    saldo = _num(k.get("saldo"), entradas_total - saidas_total)
    ticket_medio = _num(
        k.get("ticket_medio"),
        (entradas_total / atendimentos) if atendimentos > 0 else 0
    )

    comissao_por_profissional = _montar_comissao_por_profissional(entradas)

    story.append(Paragraph("Relatório Financeiro", h1))
    story.append(Paragraph(f"<b>Período:</b> {escape(periodo_label)}", p))
    story.append(Spacer(1, 10))

    story.append(Paragraph("Resumo Executivo", h2))
    resumo_tbl = [
        [
            "Faturamento",
            "Comissão",
            "Saídas",
            "Lucro líquido",
            "Atendimentos",
            "Clientes",
        ],
        [
            _brl(entradas_total),
            _brl(comissao_kpi),
            _brl(saidas_total),
            _brl(lucro_liquido),
            str(atendimentos),
            str(clientes),
        ],
    ]
    story.append(
        _table(
            resumo_tbl,
            col_widths=[3.0*cm, 2.8*cm, 2.4*cm, 3.0*cm, 2.4*cm, 2.4*cm],
            repeat_rows=1,
            align_right_cols=[0, 1, 2, 3],
        )
    )
    story.append(Spacer(1, 8))

    story.append(Paragraph("Indicadores Operacionais", h2))
    indicadores_tbl = [
        ["Ticket médio", "Uso de planos", "Saldo operacional"],
        [
            _brl(ticket_medio),
            str(uso_planos),
            _brl(saldo),
        ],
    ]
    story.append(
        _table(
            indicadores_tbl,
            col_widths=[5.4*cm, 5.2*cm, 5.8*cm],
            repeat_rows=1,
            align_right_cols=[0, 2],
        )
    )
    story.append(Spacer(1, 12))

    story.append(Paragraph("Totais por forma de pagamento", h2))
    rows = [["Forma", "Entradas", "Saídas", "Saldo"]]

    formas_ordenadas = ["dinheiro", "pix", "debito", "credito", "plano"]
    extras = [fp for fp in por_forma.keys() if fp not in formas_ordenadas]

    for fp in formas_ordenadas + sorted(extras):
        v = por_forma.get(fp, {})
        ent = _num((v or {}).get("entrada"))
        sai = _num((v or {}).get("saida"))
        rows.append([
            str(fp),
            _brl(ent),
            _brl(sai),
            _brl(ent - sai),
        ])

    story.append(
        _table(
            rows,
            col_widths=[4.0*cm, 4.0*cm, 4.0*cm, 4.0*cm],
            repeat_rows=1,
            align_right_cols=[1, 2, 3],
        )
    )
    story.append(Spacer(1, 12))

    story.append(Paragraph("Faturamento mensal (últimos 6 meses)", h2))
    mrows = [["Mês", "Total"]]
    for it in mensal:
        mrows.append([
            str(it.get("ym") or ""),
            _brl(_num(it.get("total"))),
        ])

    if len(mrows) == 1:
        mrows.append(["Sem dados", _brl(0)])

    story.append(
        _table(
            mrows,
            col_widths=[5.0*cm, 11.0*cm],
            repeat_rows=1,
            align_right_cols=[1],
        )
    )
    story.append(Spacer(1, 12))

    story.append(Paragraph("Top serviços", h2))
    tsrows = [["Serviço", "Qtd", "Faturamento", "Comissão", "Líquido"]]

    if top_servicos:
        for s in top_servicos:
            total = _num(s.get("total"))
            comissao = _num(s.get("comissao_total"))
            liquido = _num(s.get("lucro_liquido"), total - comissao)

            tsrows.append([
                str(s.get("servico_nome") or ""),
                str(int(_num(s.get("qtd"), 0))),
                _brl(total),
                _brl(comissao),
                _brl(liquido),
            ])
    else:
        tsrows.append(["Sem dados", "-", "-", "-", "-"])

    story.append(
        _table(
            tsrows,
            col_widths=[6.0*cm, 1.8*cm, 2.8*cm, 2.8*cm, 2.8*cm],
            repeat_rows=1,
            align_right_cols=[1, 2, 3, 4],
        )
    )
    story.append(Spacer(1, 12))

    story.append(Paragraph("Top profissionais", h2))
    tprows = [["Profissional", "Atendimentos",
               "Faturamento", "Comissão", "Líquido"]]

    if top_profissionais:
        for prof in top_profissionais:
            total = _num(prof.get("total"))
            comissao = _num(prof.get("comissao_total"))
            liquido = _num(prof.get("lucro_liquido"), total - comissao)

            tprows.append([
                str(prof.get("profissional_nome") or ""),
                str(int(_num(prof.get("atendimentos"), 0))),
                _brl(total),
                _brl(comissao),
                _brl(liquido),
            ])
    else:
        tprows.append(["Sem dados", "-", "-", "-", "-"])

    story.append(
        _table(
            tprows,
            col_widths=[5.0*cm, 2.5*cm, 2.8*cm, 2.8*cm, 2.8*cm],
            repeat_rows=1,
            align_right_cols=[1, 2, 3, 4],
        )
    )
    story.append(Spacer(1, 12))

    story.append(Paragraph("Comissão detalhada por profissional", h2))
    cprows = [["Profissional", "Atendimentos",
               "Faturamento", "Comissão", "Líquido"]]

    if comissao_por_profissional:
        for prof in comissao_por_profissional:
            cprows.append([
                str(prof["profissional_nome"]),
                str(int(prof["atendimentos"])),
                _brl(_num(prof["faturamento"])),
                _brl(_num(prof["comissao_total"])),
                _brl(_num(prof["liquido"])),
            ])
    else:
        cprows.append(["Sem dados", "-", "-", "-", "-"])

    story.append(
        _table(
            cprows,
            col_widths=[5.0*cm, 2.5*cm, 2.8*cm, 2.8*cm, 2.8*cm],
            repeat_rows=1,
            align_right_cols=[1, 2, 3, 4],
        )
    )
    story.append(Spacer(1, 12))

    story.append(Paragraph("Detalhamento — Entradas", h2))
    erows = [
        [
            "Data/Hora",
            "Forma",
            "Valor",
            "Comissão",
            "Líquido",
            "Profissional",
            "Serviço",
            "Descrição",
        ]
    ]

    for e in entradas or []:
        valor = _num(e.get("valor"))
        comissao = _get_comissao(e)
        liquido = valor - comissao

        erows.append([
            _P(_dt_br(e.get("data_hora")), cell),
            _P((e.get("forma_pagamento") or ""), cell),
            _P(_brl(valor), cell),
            _P(_brl(comissao), cell),
            _P(_brl(liquido), cell),
            _P((e.get("profissional_nome") or ""), cell),
            _P((e.get("servico_nome") or ""), cell),
            _P((e.get("descricao") or ""), cell),
        ])

    if len(erows) == 1:
        erows.append([
            _P("Sem entradas no período", cell),
            _P("-", cell),
            _P("-", cell),
            _P("-", cell),
            _P("-", cell),
            _P("-", cell),
            _P("-", cell),
            _P("-", cell),
        ])

    story.append(
        _table(
            erows,
            col_widths=[2.0*cm, 1.7*cm, 1.8*cm, 1.8 *
                        cm, 1.8*cm, 2.7*cm, 2.5*cm, 4.4*cm],
            repeat_rows=1,
            align_right_cols=[2, 3, 4],
        )
    )
    story.append(Spacer(1, 12))

    story.append(Paragraph("Detalhamento — Saídas", h2))
    srows = [["Data/Hora", "Forma", "Valor", "Descrição"]]

    for s in saidas or []:
        srows.append([
            _P(_dt_br(s.get("data_hora")), cell),
            _P((s.get("forma_pagamento") or ""), cell),
            _P(_brl(_num(s.get("valor"))), cell),
            _P((s.get("descricao") or ""), cell),
        ])

    if len(srows) == 1:
        srows.append([
            _P("Sem saídas no período", cell),
            _P("-", cell),
            _P("-", cell),
            _P("-", cell),
        ])

    story.append(
        _table(
            srows,
            col_widths=[3.0*cm, 2.5*cm, 2.5*cm, 8.0*cm],
            repeat_rows=1,
            align_right_cols=[2],
        )
    )

    doc.build(story)
    return buf.getvalue()
