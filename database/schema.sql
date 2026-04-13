PRAGMA foreign_keys = ON;

-- ==========================================================
-- CLIENTES
-- ==========================================================
CREATE TABLE IF NOT EXISTS clientes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    telefone TEXT NOT NULL,
    email TEXT,
    observacoes TEXT,
    criado_em TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_clientes_telefone_unico
ON clientes(telefone);


-- ==========================================================
-- PROFISSIONAIS
-- ==========================================================
CREATE TABLE IF NOT EXISTS profissionais (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    telefone TEXT,
    dias_trabalho TEXT,
    hora_inicio TEXT,
    hora_fim TEXT,
    ativo INTEGER NOT NULL DEFAULT 1 CHECK (ativo IN (0,1)),
    tipo_comissao TEXT DEFAULT 'percentual' CHECK (tipo_comissao IN ('percentual', 'fixo')),
    valor_comissao REAL DEFAULT 0 CHECK (valor_comissao >= 0)
);


CREATE TABLE IF NOT EXISTS comissoes_profissionais (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profissional_id INTEGER NOT NULL,
    tipo_comissao TEXT NOT NULL CHECK (tipo_comissao IN ('percentual', 'fixo')),
    valor_comissao REAL NOT NULL CHECK (valor_comissao >= 0),
    vigente_desde TEXT NOT NULL,
    criado_em TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (profissional_id) REFERENCES profissionais(id)
);

CREATE INDEX IF NOT EXISTS idx_comissoes_profissionais_profissional
ON comissoes_profissionais(profissional_id);

CREATE INDEX IF NOT EXISTS idx_comissoes_profissionais_vigencia
ON comissoes_profissionais(profissional_id, vigente_desde);


-- ==========================================================
-- SERVIÇOS
-- ==========================================================
CREATE TABLE IF NOT EXISTS servicos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    duracao INTEGER NOT NULL,
    preco REAL NOT NULL CHECK (preco >= 0),
    ativo INTEGER NOT NULL DEFAULT 1 CHECK (ativo IN (0,1)),
    categoria TEXT,
    descricao TEXT
);


-- ==========================================================
-- AGENDAMENTOS
-- ==========================================================
CREATE TABLE IF NOT EXISTS agendamentos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cliente_id INTEGER NOT NULL,
    profissional_id INTEGER NOT NULL,
    servico_id INTEGER NOT NULL,
    data TEXT NOT NULL,
    horario TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'aguardando' CHECK (
        lower(status) IN ('aguardando', 'confirmado', 'cancelado', 'concluido')
    ),

    FOREIGN KEY (cliente_id) REFERENCES clientes(id),
    FOREIGN KEY (profissional_id) REFERENCES profissionais(id),
    FOREIGN KEY (servico_id) REFERENCES servicos(id)
);

CREATE INDEX IF NOT EXISTS idx_agendamentos_data
ON agendamentos(data);

CREATE INDEX IF NOT EXISTS idx_agendamentos_profissional_data
ON agendamentos(profissional_id, data);

CREATE INDEX IF NOT EXISTS idx_agendamentos_cliente
ON agendamentos(cliente_id);


-- ==========================================================
-- BLOQUEIOS
-- ==========================================================
CREATE TABLE IF NOT EXISTS bloqueios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profissional_id INTEGER NOT NULL,
    data TEXT NOT NULL,
    hora_inicio TEXT,
    hora_fim TEXT,
    motivo TEXT,
    dia_inteiro INTEGER NOT NULL DEFAULT 1 CHECK (dia_inteiro IN (0,1)),
    FOREIGN KEY (profissional_id) REFERENCES profissionais(id)
);

CREATE INDEX IF NOT EXISTS idx_bloqueios_profissional_data
ON bloqueios(profissional_id, data);


-- ==========================================================
-- PRODUTOS / ESTOQUE
-- ==========================================================
CREATE TABLE IF NOT EXISTS produtos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    categoria TEXT DEFAULT '',
    marca TEXT DEFAULT '',
    preco_custo REAL DEFAULT 0 CHECK (preco_custo >= 0),
    preco_venda REAL DEFAULT 0 CHECK (preco_venda >= 0),
    estoque_atual INTEGER NOT NULL DEFAULT 0 CHECK (estoque_atual >= 0),
    estoque_minimo INTEGER NOT NULL DEFAULT 0 CHECK (estoque_minimo >= 0),
    ativo INTEGER NOT NULL DEFAULT 1 CHECK (ativo IN (0,1)),
    criado_em TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_produtos_ativo
ON produtos(ativo);


CREATE TABLE IF NOT EXISTS movimentacoes_estoque (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    produto_id INTEGER NOT NULL,
    tipo TEXT NOT NULL CHECK (tipo IN ('entrada', 'saida')),
    quantidade INTEGER NOT NULL CHECK (quantidade > 0),
    data_hora TEXT NOT NULL,
    descricao TEXT,
    criado_em TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (produto_id) REFERENCES produtos(id)
);

CREATE INDEX IF NOT EXISTS idx_movimentacoes_estoque_produto
ON movimentacoes_estoque(produto_id);

CREATE INDEX IF NOT EXISTS idx_movimentacoes_estoque_data
ON movimentacoes_estoque(data_hora);


-- ==========================================================
-- CAIXA
-- ==========================================================
CREATE TABLE IF NOT EXISTS movimentacoes_caixa (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo TEXT NOT NULL CHECK (tipo IN ('entrada', 'saida')),
    forma_pagamento TEXT NOT NULL CHECK (
        forma_pagamento IN ('dinheiro', 'pix', 'debito', 'credito', 'plano')
    ),
    valor REAL NOT NULL CHECK (valor >= 0),
    data_hora TEXT NOT NULL,
    descricao TEXT,
    agendamento_id INTEGER,
    profissional_id INTEGER,
    servico_id INTEGER,
    status TEXT NOT NULL DEFAULT 'pendente' CHECK (
        status IN ('pago', 'pendente', 'cancelado')
    ),
    comissao_valor REAL NOT NULL DEFAULT 0 CHECK (comissao_valor >= 0),
    criado_em TEXT NOT NULL DEFAULT (datetime('now')),

    FOREIGN KEY (agendamento_id) REFERENCES agendamentos(id),
    FOREIGN KEY (profissional_id) REFERENCES profissionais(id),
    FOREIGN KEY (servico_id) REFERENCES servicos(id)
);

CREATE INDEX IF NOT EXISTS idx_movimentacoes_caixa_data
ON movimentacoes_caixa(data_hora);

CREATE INDEX IF NOT EXISTS idx_movimentacoes_caixa_status
ON movimentacoes_caixa(status);

CREATE INDEX IF NOT EXISTS idx_movimentacoes_caixa_agendamento
ON movimentacoes_caixa(agendamento_id);

CREATE INDEX IF NOT EXISTS idx_movimentacoes_caixa_profissional
ON movimentacoes_caixa(profissional_id);

CREATE INDEX IF NOT EXISTS idx_movimentacoes_caixa_servico
ON movimentacoes_caixa(servico_id);


CREATE TABLE IF NOT EXISTS vendas_produtos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    movimentacao_id INTEGER NOT NULL,
    produto_id INTEGER NOT NULL,
    nome TEXT NOT NULL,
    quantidade INTEGER NOT NULL CHECK (quantidade > 0),
    preco_unit REAL NOT NULL CHECK (preco_unit >= 0),
    subtotal REAL NOT NULL CHECK (subtotal >= 0),
    criado_em TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (movimentacao_id) REFERENCES movimentacoes_caixa(id),
    FOREIGN KEY (produto_id) REFERENCES produtos(id)
);

CREATE INDEX IF NOT EXISTS idx_vendas_produtos_movimentacao
ON vendas_produtos(movimentacao_id);

CREATE INDEX IF NOT EXISTS idx_vendas_produtos_produto
ON vendas_produtos(produto_id);


-- ==========================================================
-- PLANOS
-- ==========================================================
CREATE TABLE IF NOT EXISTS planos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    valor_mensal REAL NOT NULL CHECK (valor_mensal >= 0),
    usos_por_mes INTEGER NOT NULL CHECK (usos_por_mes > 0),
    ativo INTEGER NOT NULL DEFAULT 1 CHECK (ativo IN (0,1)),
    criado_em TEXT NOT NULL DEFAULT (datetime('now'))
);


CREATE TABLE IF NOT EXISTS planos_servicos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plano_id INTEGER NOT NULL,
    servico_id INTEGER NOT NULL,
    FOREIGN KEY (plano_id) REFERENCES planos(id),
    FOREIGN KEY (servico_id) REFERENCES servicos(id)
);

CREATE INDEX IF NOT EXISTS idx_planos_servicos_plano
ON planos_servicos(plano_id);

CREATE INDEX IF NOT EXISTS idx_planos_servicos_servico
ON planos_servicos(servico_id);


CREATE TABLE IF NOT EXISTS clientes_planos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cliente_id INTEGER NOT NULL,
    plano_id INTEGER NOT NULL,
    data_inicio TEXT,
    proximo_vencimento TEXT,
    usos_totais INTEGER NOT NULL CHECK (usos_totais >= 0),
    usos_restantes INTEGER NOT NULL CHECK (usos_restantes >= 0),
    forma_pagamento TEXT,
    status TEXT NOT NULL CHECK (
        status IN ('ativo', 'aguardando_pagamento', 'atrasado', 'cancelado')
    ),
    criado_em TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (cliente_id) REFERENCES clientes(id),
    FOREIGN KEY (plano_id) REFERENCES planos(id)
);

CREATE INDEX IF NOT EXISTS idx_clientes_planos_cliente
ON clientes_planos(cliente_id);

CREATE INDEX IF NOT EXISTS idx_clientes_planos_plano
ON clientes_planos(plano_id);

CREATE INDEX IF NOT EXISTS idx_clientes_planos_status
ON clientes_planos(status);


CREATE TABLE IF NOT EXISTS clientes_planos_usos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cliente_plano_id INTEGER NOT NULL,
    agendamento_id INTEGER,
    data_uso TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (cliente_plano_id) REFERENCES clientes_planos(id),
    FOREIGN KEY (agendamento_id) REFERENCES agendamentos(id)
);

CREATE INDEX IF NOT EXISTS idx_clientes_planos_usos_plano
ON clientes_planos_usos(cliente_plano_id);

CREATE INDEX IF NOT EXISTS idx_clientes_planos_usos_agendamento
ON clientes_planos_usos(agendamento_id);


-- ==========================================================
-- CONFIGURAÇÕES
-- ==========================================================
CREATE TABLE IF NOT EXISTS configuracoes_geral (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    nome TEXT DEFAULT '',
    telefone TEXT DEFAULT '',
    endereco TEXT DEFAULT '',
    email TEXT DEFAULT '',
    cnpj TEXT DEFAULT '',
    atualizado_em TEXT DEFAULT (datetime('now'))
);

INSERT OR IGNORE INTO configuracoes_geral (id) VALUES (1);


CREATE TABLE IF NOT EXISTS configuracoes_horarios (
    dia_semana INTEGER NOT NULL CHECK (dia_semana BETWEEN 0 AND 6),
    aberto INTEGER NOT NULL DEFAULT 1 CHECK (aberto IN (0,1)),
    hora_inicio TEXT NOT NULL DEFAULT '09:00',
    hora_fim TEXT NOT NULL DEFAULT '19:00',
    atualizado_em TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (dia_semana)
);

INSERT OR IGNORE INTO configuracoes_horarios (dia_semana, aberto, hora_inicio, hora_fim) VALUES (0, 0, '09:00', '19:00');
INSERT OR IGNORE INTO configuracoes_horarios (dia_semana, aberto, hora_inicio, hora_fim) VALUES (1, 1, '09:00', '19:00');
INSERT OR IGNORE INTO configuracoes_horarios (dia_semana, aberto, hora_inicio, hora_fim) VALUES (2, 1, '09:00', '19:00');
INSERT OR IGNORE INTO configuracoes_horarios (dia_semana, aberto, hora_inicio, hora_fim) VALUES (3, 1, '09:00', '19:00');
INSERT OR IGNORE INTO configuracoes_horarios (dia_semana, aberto, hora_inicio, hora_fim) VALUES (4, 1, '09:00', '19:00');
INSERT OR IGNORE INTO configuracoes_horarios (dia_semana, aberto, hora_inicio, hora_fim) VALUES (5, 1, '09:00', '19:00');
INSERT OR IGNORE INTO configuracoes_horarios (dia_semana, aberto, hora_inicio, hora_fim) VALUES (6, 1, '09:00', '19:00');