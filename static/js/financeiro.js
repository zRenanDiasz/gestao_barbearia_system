document.addEventListener("DOMContentLoaded", () => {
    initFinanceiro().catch((err) => notify(err?.message || "Erro ao iniciar o Financeiro.", "error"));
});

/* =========================
   Small helpers
========================= */
function brl(n) {
    return `R$ ${Number(n || 0).toFixed(2).replace(".", ",")}`;
}

function todayISO() {
    const d = new Date();
    const yyyy = d.getFullYear();
    const mm = String(d.getMonth() + 1).padStart(2, "0");
    const dd = String(d.getDate()).padStart(2, "0");
    return `${yyyy}-${mm}-${dd}`;
}

function formatDataBR(iso) {
    if (!iso || !iso.includes("-")) return iso || "";
    const [y, m, d] = iso.split("-");
    return `${d}/${m}/${y}`;
}

function formatPagamento(fp) {
    const v = (fp || "").toLowerCase();
    const map = {
        dinheiro: "Dinheiro",
        debito: "Cartão Débito",
        credito: "Cartão Crédito",
        pix: "PIX",
        transferencia: "Transferência",
    };
    return map[v] || (fp || "—");
}

function setText(id, txt) {
    const el = document.getElementById(id);
    if (el) el.textContent = txt;
}

function escapeHtml(str) {
    return String(str || "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

/**
 * notify(): unified message handler (only for validation/errors)
 * Tries UI.toast/UI.notify if present, fallback to alert().
 */
function notify(message, variant = "info") {
    try {
        if (window.UI) {
            if (typeof window.UI.toast === "function") {
                try { window.UI.toast(message, variant); return; } catch (_) { }
                try { window.UI.toast({ message, variant }); return; } catch (_) { }
                try { window.UI.toast(message); return; } catch (_) { }
            }
            if (typeof window.UI.notify === "function") {
                try { window.UI.notify({ message, variant }); return; } catch (_) { }
                try { window.UI.notify(message, variant); return; } catch (_) { }
                try { window.UI.notify(message); return; } catch (_) { }
            }
        }
    } catch (_) { }
    alert(message);
}

/* =========================
   Date helpers (week range)
   Padrão: semana de SEG a DOM (pagamento semanal normalmente fecha assim)
========================= */
function isoToDate(iso) {
    const [y, m, d] = String(iso).split("-").map(Number);
    return new Date(y, m - 1, d);
}

function dateToISO(dt) {
    const y = dt.getFullYear();
    const m = String(dt.getMonth() + 1).padStart(2, "0");
    const d = String(dt.getDate()).padStart(2, "0");
    return `${y}-${m}-${d}`;
}

function getWeekRangeISO(baseISO) {
    const dt = isoToDate(baseISO || todayISO());
    // JS: 0=dom,1=seg...
    const day = dt.getDay();
    // queremos seg (1) como início
    const diffToMon = (day === 0) ? -6 : (1 - day);
    const start = new Date(dt);
    start.setDate(dt.getDate() + diffToMon);

    const end = new Date(start);
    end.setDate(start.getDate() + 6);

    return { inicio: dateToISO(start), fim: dateToISO(end) };
}

/* =========================
   Screen state
========================= */
let debounceTimer = null;
let movsNaTela = []; // list rendered in table (used by status menu)
let mensalCacheKey = null;     // "YYYY-MM"
let mensalCacheValue = null;   // number

// Cached lookups (id -> name)
let profById = new Map();
let servById = new Map();

/* =========================
   Boot / init
========================= */
async function initFinanceiro() {
    // Defaults
    const dataInput = document.getElementById("filtro-data");
    if (dataInput) dataInput.value = todayISO();

    // filtro padrão
    const periodoSel = document.getElementById("filtro-periodo");
    if (periodoSel && !periodoSel.value) periodoSel.value = "dia";

    // Listeners
    document.getElementById("filtro-data")?.addEventListener("change", carregarTelaSafe);
    document.getElementById("filtro-periodo")?.addEventListener("change", carregarTelaSafe);
    document.getElementById("filtro-profissional")?.addEventListener("change", carregarTelaSafe);
    document.getElementById("filtro-tipo")?.addEventListener("change", carregarTelaSafe);
    document.getElementById("filtro-status")?.addEventListener("change", carregarTelaSafe);
    document.getElementById("busca")?.addEventListener("input", carregarTelaDebounced);

    initModalTransacao();
    initMenuStatusMov();

    // load lookups before first render
    await carregarLookups();
    await popularFiltroProfissionais();

    await carregarTela();
}

function carregarTelaSafe() {
    carregarTela().catch((e) => notify(e?.message || "Erro ao carregar dados.", "error"));
}

function carregarTelaDebounced() {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => carregarTelaSafe(), 200);
}

/* =========================
   Load + filter data
========================= */
async function carregarTela() {
    const data = document.getElementById("filtro-data")?.value || todayISO();
    const periodo = (document.getElementById("filtro-periodo")?.value || "dia").toLowerCase();
    const tipoFiltro = (document.getElementById("filtro-tipo")?.value || "").toLowerCase();
    const statusFiltro = (document.getElementById("filtro-status")?.value || "").toLowerCase();
    const busca = (document.getElementById("busca")?.value || "").toLowerCase().trim();

    const profissional_id_raw = document.getElementById("filtro-profissional")?.value || "";
    const profissional_id = profissional_id_raw ? Number(profissional_id_raw) : null;

    // API params:
    // - dia:   /caixa/movimentacoes?data=YYYY-MM-DD&profissional_id=...
    // - semana:/caixa/movimentacoes?inicio=YYYY-MM-DD&fim=YYYY-MM-DD&profissional_id=...
    let url = "";
    let labelPeriodo = "";

    if (periodo === "semana") {
        const { inicio, fim } = getWeekRangeISO(data);
        labelPeriodo = `Semana ${formatDataBR(inicio)} — ${formatDataBR(fim)}`;
        url = `/caixa/movimentacoes?inicio=${encodeURIComponent(inicio)}&fim=${encodeURIComponent(fim)}`;
    } else {
        labelPeriodo = `Dia ${formatDataBR(data)}`;
        url = `/caixa/movimentacoes?data=${encodeURIComponent(data)}`;
    }

    if (profissional_id) {
        url += `&profissional_id=${encodeURIComponent(String(profissional_id))}`;
    }

    const movs = await API.get(url);
    let lista = Array.isArray(movs) ? movs : [];

    // Local filters
    if (tipoFiltro) lista = lista.filter((m) => String(m.tipo || "").toLowerCase() === tipoFiltro);
    if (statusFiltro) lista = lista.filter((m) => String(m.status || "").toLowerCase() === statusFiltro);

    if (busca) {
        lista = lista.filter((m) => {
            const hay = `${m.descricao || ""} ${m.produtos || ""}`.toLowerCase();
            return hay.includes(busca);
        });
    }

    movsNaTela = lista;

    renderLabelsPeriodo(periodo, labelPeriodo);
    renderKPIs(lista, periodo, labelPeriodo);
    renderTabela(lista, periodo, data);
    await atualizarReceitaMensal(data);
}

function renderLabelsPeriodo(periodo, labelPeriodo) {
    const l1 = document.getElementById("kpi-label-receita");
    const l2 = document.getElementById("kpi-label-despesa");
    const l3 = document.getElementById("kpi-label-saldo");

    if (periodo === "semana") {
        if (l1) l1.textContent = "Receita da Semana";
        if (l2) l2.textContent = "Despesas da Semana";
        if (l3) l3.textContent = "Saldo da Semana";
    } else {
        if (l1) l1.textContent = "Receita do Dia";
        if (l2) l2.textContent = "Despesas do Dia";
        if (l3) l3.textContent = "Saldo do Dia";
    }

    setText("kpi-receita-sub", labelPeriodo);
    setText("kpi-despesa-sub", labelPeriodo);
    setText("kpi-saldo-sub", labelPeriodo);
}

/* =========================
   KPIs
========================= */
function renderKPIs(lista, periodo, labelPeriodo) {
    const entradas = lista.filter((m) => String(m.tipo || "").toLowerCase() === "entrada");
    const saidas = lista.filter((m) => String(m.tipo || "").toLowerCase() === "saida");

    const receita = entradas.reduce((s, m) => s + Number(m.valor || 0), 0);
    const despesa = saidas.reduce((s, m) => s + Number(m.valor || 0), 0);
    const saldo = receita - despesa;

    setText("kpi-receita-dia", brl(receita));
    setText("kpi-despesa-dia", brl(despesa));
    setText("kpi-saldo-dia", brl(saldo));

    // Por pagamento (período)
    const porPag = (forma) =>
        lista
            .filter(m => (m.forma_pagamento || "").toLowerCase() === forma)
            .reduce((s, m) => s + Number(m.valor || 0), 0);

    const dinheiro = porPag("dinheiro");
    const debito = porPag("debito");
    const pix = porPag("pix");
    const credito = porPag("credito");

    setText("kpi-dinheiro", brl(dinheiro));
    setText("kpi-debito", brl(debito));
    setText("kpi-pix", brl(pix));
    setText("kpi-credito", brl(credito));

    // percentuais (base: total movimentado)
    const totalMov = lista.reduce((s, m) => s + Number(m.valor || 0), 0);
    setText("kpi-dinheiro-sub", totalMov ? `${Math.round((dinheiro / totalMov) * 100)}% do total` : "—");
    setText("kpi-debito-sub", totalMov ? `${Math.round((debito / totalMov) * 100)}% do total` : "—");
    setText("kpi-pix-sub", totalMov ? `${Math.round((pix / totalMov) * 100)}% do total` : "—");
    setText("kpi-credito-sub", totalMov ? `${Math.round((credito / totalMov) * 100)}% do total` : "—");
}

/* =========================
   MONTHLY KPI (Receita Mensal)
========================= */
async function atualizarReceitaMensal(dataISO) {
    const key = String(dataISO || "").slice(0, 7); // "YYYY-MM"
    if (!key || !key.includes("-")) return;

    if (mensalCacheKey === key && mensalCacheValue != null) {
        setText("kpi-receita-mensal", brl(mensalCacheValue));
        setText("kpi-mensal-sub", `Mês ${key.split("-")[1]}/${key.split("-")[0]}`);
        return;
    }

    const [ano, mes] = key.split("-");

    try {
        const resumo = await API.get(`/caixa/resumo/mensal?ano=${encodeURIComponent(ano)}&mes=${encodeURIComponent(mes)}`);
        const totalEntradas = Number(resumo?.total_entradas || 0);

        mensalCacheKey = key;
        mensalCacheValue = totalEntradas;

        setText("kpi-receita-mensal", brl(totalEntradas));
        setText("kpi-mensal-sub", `Mês ${mes}/${ano}`);
    } catch (_) {
        setText("kpi-receita-mensal", brl(0));
        setText("kpi-mensal-sub", "—");
    }
}

/* =========================
   Table rendering
========================= */
function badgeStatusMov(mov) {
    const s = String(mov.status || "pendente").toLowerCase();
    const id = mov.id;
    const locked = Boolean(mov.agendamento_id);

    const map = {
        pago: { label: "Pago", cls: "badge-ok" },
        pendente: { label: "Pendente", cls: "badge-warn" },
        cancelado: { label: "Cancelado", cls: "badge-danger" },
    };

    const b = map[s] || map.pendente;

    const title = locked
        ? "Status travado (pagamento de agendamento)"
        : "Clique para alterar status";

    return `
    <button type="button"
            class="badge-pill ${b.cls} badge-btn"
            data-action="mov-status"
            data-id="${id}"
            title="${title}">
      ${b.label}
    </button>
  `;
}

function renderComissao(m) {
    // mostra comissão só quando for entrada vinculada a profissional
    const isEntrada = String(m.tipo || "").toLowerCase() === "entrada";
    const v = Number(m.comissao_valor || 0);

    if (!isEntrada) return `<span style="opacity:.6;">—</span>`;
    if (!m.profissional_id) return `<span style="opacity:.6;">—</span>`;
    return `<span style="font-weight:700; color:#d97706;">${brl(v)}</span>`;
}

function renderTabela(lista, periodo, dataISO) {
    const tbody = document.getElementById("tbody-transacoes");
    if (!tbody) return;

    tbody.innerHTML = "";

    if (!lista || lista.length === 0) {
        const tr = document.createElement("tr");
        tr.innerHTML = `<td colspan="7" style="padding:14px; opacity:.75;">Nenhuma transação encontrada para os filtros.</td>`;
        tbody.appendChild(tr);
        return;
    }

    // Sort by data_hora desc when present
    const ordenada = [...lista].sort((a, b) =>
        String(b.data_hora || "").localeCompare(String(a.data_hora || ""))
    );

    ordenada.forEach((m) => {
        const tr = document.createElement("tr");

        const tipo = String(m.tipo || "").toLowerCase();
        const badgeTipo =
            tipo === "entrada"
                ? `<span class="badge-pill badge-in">Receita</span>`
                : `<span class="badge-pill badge-out">Despesa</span>`;

        const valor = Number(m.valor || 0);
        const valorTxt = tipo === "saida" ? `- ${brl(valor)}` : `+ ${brl(valor)}`;

        // data exibida:
        // - semana: usa date(data_hora) se vier; senão "—"
        // - dia: continua igual (data selecionada)
        let dataExibida = formatDataBR(dataISO);
        if (periodo === "semana") {
            const dh = String(m.data_hora || "");
            // tenta extrair YYYY-MM-DD do começo
            const d = dh.slice(0, 10);
            dataExibida = d && d.includes("-") ? formatDataBR(d) : "—";
        }

        tr.innerHTML = `
      <td>${dataExibida}</td>
      <td>${renderDescricaoMov(m)}</td>
      <td>${badgeTipo}</td>
      <td>${formatPagamento(m.forma_pagamento)}</td>
      <td>${valorTxt}</td>
      <td>${renderComissao(m)}</td>
      <td>${badgeStatusMov(m)}</td>
    `;

        tbody.appendChild(tr);
    });
}

/* =========================
   LOOKUPS (Profissionais / Serviços)
========================= */
async function carregarLookups() {
    // Profissionais
    try {
        const profs = await API.get("/profissionais");
        const lista = Array.isArray(profs) ? profs : [];
        profById = new Map(lista.map(p => [String(p.id), String(p.nome || "")]));
    } catch (_) {
        profById = new Map();
    }

    // Serviços
    try {
        const servs = await API.get("/servicos");
        const lista = Array.isArray(servs) ? servs : [];
        servById = new Map(lista.map(s => [String(s.id), String(s.nome || "")]));
    } catch (_) {
        try {
            const servs = await API.get("/servicos?status=ativo");
            const lista = Array.isArray(servs) ? servs : [];
            servById = new Map(lista.map(s => [String(s.id), String(s.nome || "")]));
        } catch (_) {
            servById = new Map();
        }
    }
}

async function popularFiltroProfissionais() {
    const sel = document.getElementById("filtro-profissional");
    if (!sel) return;

    const atual = sel.value || "";
    sel.innerHTML = `<option value="">Todos os Profissionais</option>`;

    // usa o cache profById
    const arr = [...profById.entries()]
        .map(([id, nome]) => ({ id, nome }))
        .sort((a, b) => String(a.nome).localeCompare(String(b.nome)));

    arr.forEach(p => {
        const opt = document.createElement("option");
        opt.value = String(p.id);
        opt.textContent = p.nome;
        sel.appendChild(opt);
    });

    // restaura
    if (atual && [...sel.options].some(o => o.value === atual)) sel.value = atual;
}

/* =========================
   Descrição (inclui produtos reais)
========================= */
function parsePagamentoDescricao(desc) {
    // Supports: "Pagamento - CLIENTE - SERVIÇO | Produtos: A x1, B x2"
    const raw = String(desc || "").trim();

    const parts = raw.split(" - ").map(s => s.trim()).filter(Boolean);
    if (parts.length >= 3 && parts[0].toLowerCase().startsWith("pagamento")) {
        return {
            cliente: parts[1] || "",
            servico: parts.slice(2).join(" - ") || "",
        };
    }
    return { cliente: "", servico: "" };
}

function renderDescricaoMov(m) {
    const isAgendamento = Boolean(m.agendamento_id);

    let linha1 = m.descricao || "—";
    let linha2 = "";
    let linha3 = "";

    if (isAgendamento) {
        const parsed = parsePagamentoDescricao(m.descricao);

        const cliente = parsed.cliente || "Cliente";
        const servico = servById.get(String(m.servico_id)) || parsed.servico || "";
        const profissional = profById.get(String(m.profissional_id)) || "";

        linha1 = cliente;
        linha2 = servico;

        // ✅ produtos reais (backend manda m.produtos como texto já pronto)
        // Ex: "Produtos: Óleo p/ Barba x1, Pomada x2"
        const produtosTxt = String(m.produtos || "").trim();
        if (produtosTxt) {
            // exibe como mais uma linha “muted”
            linha3 = `${profissional}${profissional && produtosTxt ? " • " : ""}${produtosTxt}`;
        } else {
            linha3 = profissional;
        }
    } else {
        // Movimentações manuais
        const tipo = String(m.tipo || "").toLowerCase();
        linha2 = (tipo === "saida") ? "Estoque" : "Caixa";
    }

    return `
      <div class="desc-cell">
        <div class="desc-title">${escapeHtml(linha1)}</div>
        ${linha2 ? `<div class="desc-sub">${escapeHtml(linha2)}</div>` : ""}
        ${linha3 ? `<div class="desc-sub muted">${escapeHtml(linha3)}</div>` : ""}
      </div>
    `;
}

/* =========================
   Modal: New transaction
========================= */
function initModalTransacao() {
    const btnAbrir = document.getElementById("btn-nova-transacao");
    const overlay = document.getElementById("modal-transacao");
    const btnFechar = document.getElementById("btn-fechar-transacao");
    const btnCancelar = document.getElementById("btn-cancelar-transacao");
    const form = document.getElementById("form-transacao");

    if (!btnAbrir || !overlay || !form) return;

    const fechar = () => overlay.classList.remove("is-open");

    btnAbrir.addEventListener("click", () => {
        form.reset();

        const baseDate = document.getElementById("filtro-data")?.value || todayISO();
        const dataEl = document.getElementById("tr-data");
        if (dataEl) dataEl.value = baseDate;

        overlay.classList.add("is-open");
    });

    btnFechar?.addEventListener("click", fechar);
    btnCancelar?.addEventListener("click", fechar);

    overlay.addEventListener("click", (e) => {
        if (e.target === overlay) fechar();
    });

    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape") fechar();
    });

    form.addEventListener("submit", async (e) => {
        e.preventDefault();

        try {
            const tipo = document.getElementById("tr-tipo")?.value;
            const data = document.getElementById("tr-data")?.value;
            const descricao = (document.getElementById("tr-descricao")?.value || "").trim();
            const valor = Number(document.getElementById("tr-valor")?.value || 0);
            const forma_pagamento = document.getElementById("tr-pagamento")?.value;
            const status = document.getElementById("tr-status")?.value;

            if (!tipo || !data || !descricao || !valor || !forma_pagamento || !status) {
                return notify("Preencha todos os campos.", "warning");
            }
            if (valor <= 0) return notify("Valor deve ser maior que zero.", "warning");

            const data_hora = `${data} 12:00`;

            await API.post("/caixa/movimentacoes", {
                tipo,
                forma_pagamento,
                valor,
                data_hora,
                descricao,
                status,
            });

            fechar();
            await carregarTela();
        } catch (err) {
            notify(err?.message || "Erro ao salvar transação.", "error");
        }
    });
}

/* =========================
   Status menu (click badge)
========================= */
let movStatusMenuEl = null;

function initMenuStatusMov() {
    document.addEventListener("click", (e) => {
        const btn = e.target.closest('[data-action="mov-status"]');
        if (!btn) {
            fecharMovStatusMenu();
            return;
        }

        e.preventDefault();
        e.stopPropagation();

        const mov = movsNaTela.find((m) => String(m.id) === String(btn.dataset.id));
        if (mov && mov.agendamento_id) {
            fecharMovStatusMenu();
            return;
        }

        abrirMovStatusMenu(btn, btn.dataset.id);
    });

    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape") fecharMovStatusMenu();
    });
}

function abrirMovStatusMenu(anchorBtn, id) {
    fecharMovStatusMenu();

    const rect = anchorBtn.getBoundingClientRect();

    movStatusMenuEl = document.createElement("div");
    movStatusMenuEl.className = "status-menu";
    movStatusMenuEl.innerHTML = `
    <button type="button" class="status-opt" data-status="pago" data-id="${id}">
      <span class="dot success"></span> Pago
    </button>
    <button type="button" class="status-opt" data-status="pendente" data-id="${id}">
      <span class="dot warning"></span> Pendente
    </button>
    <button type="button" class="status-opt" data-status="cancelado" data-id="${id}">
      <span class="dot danger"></span> Cancelado
    </button>
  `;

    document.body.appendChild(movStatusMenuEl);

    movStatusMenuEl.style.position = "fixed";
    movStatusMenuEl.style.zIndex = "9999";

    const margin = 12;
    const menuW = movStatusMenuEl.offsetWidth;
    const menuH = movStatusMenuEl.offsetHeight;

    let left = rect.left;
    left = Math.min(Math.max(margin, left), window.innerWidth - menuW - margin);

    let top = rect.bottom + 8;
    if (top + menuH > window.innerHeight - margin) {
        top = rect.top - menuH - 8;
    }
    top = Math.min(Math.max(margin, top), window.innerHeight - menuH - margin);

    movStatusMenuEl.style.top = `${top}px`;
    movStatusMenuEl.style.left = `${left}px`;

    movStatusMenuEl.addEventListener("click", async (e) => {
        const opt = e.target.closest(".status-opt");
        if (!opt) return;

        const novoStatus = opt.dataset.status;
        const mid = opt.dataset.id;

        await atualizarStatusMovimentacao(mid, novoStatus);
        fecharMovStatusMenu();
    });
}

function fecharMovStatusMenu() {
    if (movStatusMenuEl) {
        movStatusMenuEl.remove();
        movStatusMenuEl = null;
    }
}

async function atualizarStatusMovimentacao(id, status) {
    try {
        await API.put(`/caixa/movimentacoes/${id}/status`, { status });
        await carregarTela();
    } catch (err) {
        notify(err?.message || "Erro ao atualizar status.", "error");
    }
}