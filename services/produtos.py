from __future__ import annotations

from datetime import datetime
from typing import Optional, Dict, Any

from database.db import get_db

FORMAS_FINANCEIRAS_ESTOQUE = ("dinheiro", "pix", "debito", "credito")


def _to_float(v, field: str) -> float:
    try:
        return float(v or 0)
    except Exception:
        raise ValueError(f"{field} inválido")


def _to_int(v, field: str) -> int:
    try:
        return int(v or 0)
    except Exception:
        raise ValueError(f"{field} inválido")


def _norm_text(v: Optional[str]) -> Optional[str]:
    s = (v or "").strip()
    return s if s else None


def _validar_data_hora_iso_opcional(data_hora: Optional[str]) -> str:
    if data_hora is None:
        return datetime.now().isoformat(timespec="seconds")

    valor = str(data_hora).strip()
    if not valor:
        raise ValueError("data_hora inválida")

    try:
        return datetime.fromisoformat(valor).isoformat(timespec="seconds")
    except Exception:
        raise ValueError("data_hora inválida")


def _validar_forma_pagamento_estoque(forma_pagamento: Optional[str]) -> str:
    forma = (forma_pagamento or "").strip().lower()
    if forma not in FORMAS_FINANCEIRAS_ESTOQUE:
        raise ValueError("forma_pagamento inválida")
    return forma


def _montar_descricao_financeira(
    *,
    tipo_mov_estoque: str,
    nome_produto: str,
    descricao: Optional[str],
) -> str:
    base = (
        f"Reposição de estoque - {nome_produto}"
        if tipo_mov_estoque == "entrada"
        else f"Venda avulsa de produto - {nome_produto}"
    )

    extra = _norm_text(descricao)
    if extra:
        return f"{base} | {extra}"
    return base


def _registrar_movimentacao_financeira_estoque(
    db,
    *,
    tipo_caixa: str,
    forma_pagamento: str,
    valor: float,
    data_hora: str,
    descricao: str,
):
    db.execute(
        """
        INSERT INTO movimentacoes_caixa
            (
                tipo,
                forma_pagamento,
                valor,
                data_hora,
                descricao,
                agendamento_id,
                profissional_id,
                servico_id,
                status,
                comissao_valor
            )
        VALUES
            (?, ?, ?, ?, ?, NULL, NULL, NULL, 'pago', 0)
        """,
        (
            tipo_caixa,
            forma_pagamento,
            float(valor or 0),
            data_hora,
            descricao,
        ),
    )


# =========================
# PRODUTOS
# =========================
def criar_produto(
    nome: str,
    categoria: Optional[str] = None,
    marca: Optional[str] = None,
    preco_custo: float = 0,
    preco_venda: float = 0,
    estoque_inicial: int = 0,
    estoque_minimo: int = 0,
) -> int:
    nome = (nome or "").strip()
    if not nome:
        raise ValueError("nome é obrigatório")

    categoria = _norm_text(categoria)
    marca = _norm_text(marca)

    preco_custo = _to_float(preco_custo, "preco_custo")
    preco_venda = _to_float(preco_venda, "preco_venda")
    estoque_inicial = _to_int(estoque_inicial, "estoque_inicial")
    estoque_minimo = _to_int(estoque_minimo, "estoque_minimo")

    if preco_custo < 0 or preco_venda < 0:
        raise ValueError("preços não podem ser negativos")
    if estoque_inicial < 0 or estoque_minimo < 0:
        raise ValueError("estoques não podem ser negativos")

    db = get_db()
    cur = db.execute(
        """
        INSERT INTO produtos
            (nome, categoria, marca, preco_custo, preco_venda, estoque_atual, estoque_minimo, ativo)
        VALUES
            (?, ?, ?, ?, ?, ?, ?, 1)
        """,
        (nome, categoria, marca, preco_custo,
         preco_venda, estoque_inicial, estoque_minimo),
    )
    db.commit()
    return cur.lastrowid


def listar_produtos(somente_ativos: bool = False):
    db = get_db()
    if somente_ativos:
        return db.execute(
            """
            SELECT id, nome, categoria, marca, preco_custo, preco_venda,
                   estoque_atual, estoque_minimo, ativo, criado_em
            FROM produtos
            WHERE ativo = 1
            ORDER BY nome
            """
        ).fetchall()

    return db.execute(
        """
        SELECT id, nome, categoria, marca, preco_custo, preco_venda,
               estoque_atual, estoque_minimo, ativo, criado_em
        FROM produtos
        ORDER BY nome
        """
    ).fetchall()


def listar_produtos_baixo_estoque():
    db = get_db()
    return db.execute(
        """
        SELECT id, nome, categoria, marca, preco_custo, preco_venda,
               estoque_atual, estoque_minimo, ativo
        FROM produtos
        WHERE ativo = 1
          AND estoque_atual <= estoque_minimo
        ORDER BY (estoque_minimo - estoque_atual) DESC, nome
        """
    ).fetchall()


def atualizar_produto(
    produto_id: int,
    nome: str,
    categoria: Optional[str],
    marca: Optional[str],
    preco_custo: float,
    preco_venda: float,
    estoque_minimo: int,
    ativo: int,
) -> bool:
    produto_id = _to_int(produto_id, "produto_id")

    nome = (nome or "").strip()
    if not nome:
        raise ValueError("nome é obrigatório")

    categoria = _norm_text(categoria)
    marca = _norm_text(marca)

    preco_custo = _to_float(preco_custo, "preco_custo")
    preco_venda = _to_float(preco_venda, "preco_venda")
    estoque_minimo = _to_int(estoque_minimo, "estoque_minimo")
    ativo = _to_int(ativo, "ativo")

    if ativo not in (0, 1):
        raise ValueError("ativo inválido (use 0 ou 1)")
    if preco_custo < 0 or preco_venda < 0:
        raise ValueError("preços não podem ser negativos")
    if estoque_minimo < 0:
        raise ValueError("estoque_minimo não pode ser negativo")

    db = get_db()

    existe = db.execute(
        "SELECT id FROM produtos WHERE id = ?", (produto_id,)
    ).fetchone()
    if not existe:
        return False

    cur = db.execute(
        """
        UPDATE produtos
        SET nome = ?, categoria = ?, marca = ?, preco_custo = ?, preco_venda = ?,
            estoque_minimo = ?, ativo = ?
        WHERE id = ?
        """,
        (nome, categoria, marca, preco_custo,
         preco_venda, estoque_minimo, ativo, produto_id),
    )
    db.commit()
    return cur.rowcount > 0


# =========================
# MOVIMENTAÇÕES DE ESTOQUE
# =========================
def _registrar_mov(
    db,
    produto_id: int,
    tipo: str,
    quantidade: int,
    descricao: Optional[str],
    data_hora: str,
):
    db.execute(
        """
        INSERT INTO movimentacoes_estoque
            (produto_id, tipo, quantidade, data_hora, descricao)
        VALUES
            (?, ?, ?, ?, ?)
        """,
        (produto_id, tipo, quantidade, data_hora, _norm_text(descricao)),
    )


def entrada_estoque(
    produto_id: int,
    quantidade: int,
    descricao: Optional[str] = None,
    data_hora: Optional[str] = None,
    forma_pagamento: Optional[str] = None,
) -> Dict[str, Any]:
    produto_id = _to_int(produto_id, "produto_id")
    quantidade = _to_int(quantidade, "quantidade")
    if quantidade <= 0:
        raise ValueError("quantidade deve ser maior que zero")

    forma_pagamento = _validar_forma_pagamento_estoque(forma_pagamento)
    data_hora_normalizada = _validar_data_hora_iso_opcional(data_hora)

    db = get_db()
    p = db.execute(
        """
        SELECT id, nome, estoque_atual, preco_custo
        FROM produtos
        WHERE id = ?
        """,
        (produto_id,),
    ).fetchone()

    if not p:
        raise ValueError("Produto não encontrado")

    nome_produto = p["nome"]
    preco_custo = float(p["preco_custo"] or 0)
    novo = int(p["estoque_atual"] or 0) + quantidade
    valor_movimentacao = quantidade * preco_custo
    descricao_financeira = _montar_descricao_financeira(
        tipo_mov_estoque="entrada",
        nome_produto=nome_produto,
        descricao=descricao,
    )

    db.execute("BEGIN IMMEDIATE")
    try:
        db.execute(
            "UPDATE produtos SET estoque_atual = ? WHERE id = ?",
            (novo, produto_id),
        )

        _registrar_mov(
            db,
            produto_id,
            "entrada",
            quantidade,
            descricao,
            data_hora_normalizada,
        )

        _registrar_movimentacao_financeira_estoque(
            db,
            tipo_caixa="saida",
            forma_pagamento=forma_pagamento,
            valor=valor_movimentacao,
            data_hora=data_hora_normalizada,
            descricao=descricao_financeira,
        )

        db.commit()
    except Exception:
        db.execute("ROLLBACK")
        raise

    return {
        "produto_id": produto_id,
        "novo_estoque": novo,
        "valor_movimentacao": valor_movimentacao,
        "tipo_financeiro": "saida",
        "forma_pagamento": forma_pagamento,
    }


def saida_estoque(
    produto_id: int,
    quantidade: int,
    descricao: Optional[str] = None,
    data_hora: Optional[str] = None,
    forma_pagamento: Optional[str] = None,
) -> Dict[str, Any]:
    produto_id = _to_int(produto_id, "produto_id")
    quantidade = _to_int(quantidade, "quantidade")
    if quantidade <= 0:
        raise ValueError("quantidade deve ser maior que zero")

    forma_pagamento = _validar_forma_pagamento_estoque(forma_pagamento)
    data_hora_normalizada = _validar_data_hora_iso_opcional(data_hora)

    db = get_db()
    p = db.execute(
        """
        SELECT id, nome, estoque_atual, preco_venda
        FROM produtos
        WHERE id = ?
        """,
        (produto_id,),
    ).fetchone()

    if not p:
        raise ValueError("Produto não encontrado")

    atual = int(p["estoque_atual"] or 0)
    if quantidade > atual:
        raise ValueError("Saída maior que o estoque atual")

    nome_produto = p["nome"]
    preco_venda = float(p["preco_venda"] or 0)
    novo = atual - quantidade
    valor_movimentacao = quantidade * preco_venda
    descricao_financeira = _montar_descricao_financeira(
        tipo_mov_estoque="saida",
        nome_produto=nome_produto,
        descricao=descricao,
    )

    db.execute("BEGIN IMMEDIATE")
    try:
        db.execute(
            "UPDATE produtos SET estoque_atual = ? WHERE id = ?",
            (novo, produto_id),
        )

        _registrar_mov(
            db,
            produto_id,
            "saida",
            quantidade,
            descricao,
            data_hora_normalizada,
        )

        _registrar_movimentacao_financeira_estoque(
            db,
            tipo_caixa="entrada",
            forma_pagamento=forma_pagamento,
            valor=valor_movimentacao,
            data_hora=data_hora_normalizada,
            descricao=descricao_financeira,
        )

        db.commit()
    except Exception:
        db.execute("ROLLBACK")
        raise

    return {
        "produto_id": produto_id,
        "novo_estoque": novo,
        "valor_movimentacao": valor_movimentacao,
        "tipo_financeiro": "entrada",
        "forma_pagamento": forma_pagamento,
    }
