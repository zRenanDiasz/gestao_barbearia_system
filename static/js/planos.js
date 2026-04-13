document.addEventListener("DOMContentLoaded", () => {
    initPlanos().catch((err) => notify(err?.message || "Erro ao iniciar Planos.", "error"));
});

/* =========================
   Helpers
========================= */
function brl(n) {
    return `R$ ${Number(n || 0).toFixed(2).replace(".", ",")}`;
}

function escapeHtml(str) {
    return String(str || "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

function formatDataBR(iso) {
    if (!iso || !String(iso).includes("-")) return iso || "—";
    const [y, m, d] = String(iso).slice(0, 10).split("-");
    return `${d}/${m}/${y}`;
}

function todayISO() {
    const d = new Date();
    const yyyy = d.getFullYear();
    const mm = String(d.getMonth() + 1).padStart(2, "0");
    const dd = String(d.getDate()).padStart(2, "0");
    return `${yyyy}-${mm}-${dd}`;
}

function addDaysISO(iso, days) {
    const [y, m, d] = String(iso).split("-").map(Number);
    const dt = new Date(y, m - 1, d);
    dt.setDate(dt.getDate() + Number(days || 0));
    const yy = dt.getFullYear();
    const mm = String(dt.getMonth() + 1).padStart(2, "0");
    const dd = String(dt.getDate()).padStart(2, "0");
    return `${yy}-${mm}-${dd}`;
}

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

function qs(id) {
    return document.getElementById(id);
}

function toDateInputValue(value) {
    const v = String(value || "").slice(0, 10);
    return /^\d{4}-\d{2}-\d{2}$/.test(v) ? v : "";
}

function findClientePlanoById(id) {
    return state.planoAtualClientes.find(c => String(c.id || c.cliente_plano_id) === String(id)) || null;
}

function getFormaPagamentoSafe(valor, fallback = "pix") {
    const v = String(valor || "").trim().toLowerCase();
    return ["dinheiro", "debito", "pix", "credito"].includes(v) ? v : fallback;
}

function getDefaultRenewDate(clientePlano) {
    const base = toDateInputValue(clientePlano?.proximo_vencimento) || todayISO();
    return addDaysISO(base, 30);
}

/* =========================
   State
========================= */
let debounceTimer = null;
let menuEl = null;
let servicosAll = [];
let servicosSelecionados = new Map();

const state = {
    view: "lista",
    planos: [],
    planosFiltrados: [],
    planoAtual: null,
    planoAtualClientes: [],
    clientesFiltrados: [],
    buscaPlanos: "",
    filtroStatusPlanos: "",
    buscaClientesPlano: "",
    clientePlanoSelecionado: null,
};

/* =========================
   Boot
========================= */
async function initPlanos() {
    wireListeners();

    bindModalOverlayClose("modal-novo-plano");
    bindModalOverlayClose("modal-vincular-cliente");
    bindModalOverlayClose("modal-renovar-cliente-plano");
    bindModalOverlayClose("modal-editar-cliente-plano");

    qs("btn-fechar-novo-plano")?.addEventListener("click", () => modalClose("modal-novo-plano"));
    qs("btn-cancelar-novo-plano")?.addEventListener("click", () => modalClose("modal-novo-plano"));

    qs("btn-fechar-vincular")?.addEventListener("click", () => modalClose("modal-vincular-cliente"));
    qs("btn-cancelar-vincular")?.addEventListener("click", () => modalClose("modal-vincular-cliente"));

    qs("btn-fechar-renovar")?.addEventListener("click", () => modalClose("modal-renovar-cliente-plano"));
    qs("btn-cancelar-renovar")?.addEventListener("click", () => modalClose("modal-renovar-cliente-plano"));

    qs("btn-fechar-editar")?.addEventListener("click", () => modalClose("modal-editar-cliente-plano"));
    qs("btn-cancelar-editar")?.addEventListener("click", () => modalClose("modal-editar-cliente-plano"));

    bindMultiSelectServicos();
    bindForms();

    await carregarTelaLista();
}

/* =========================
   Listeners
========================= */
function wireListeners() {
    qs("busca-planos")?.addEventListener("input", () => {
        state.buscaPlanos = (qs("busca-planos")?.value || "").trim().toLowerCase();
        carregarListaDebounced();
    });

    qs("filtro-status-planos")?.addEventListener("change", () => {
        state.filtroStatusPlanos = (qs("filtro-status-planos")?.value || "").trim().toLowerCase();
        carregarListaSafe();
    });

    qs("btn-novo-plano")?.addEventListener("click", () => {
        abrirModalNovoPlano().catch((e) => notify(e?.message || "Erro ao abrir modal.", "error"));
    });

    qs("btn-voltar-planos")?.addEventListener("click", () => {
        trocarView("lista");
    });

    qs("busca-clientes-plano")?.addEventListener("input", () => {
        state.buscaClientesPlano = (qs("busca-clientes-plano")?.value || "").trim().toLowerCase();
        renderTabelaClientesPlano();
    });

    qs("btn-vincular-cliente")?.addEventListener("click", () => {
        if (!state.planoAtual?.id) return;
        abrirModalVincularCliente().catch((e) => notify(e?.message || "Erro ao abrir modal.", "error"));
    });

    document.addEventListener("click", (e) => {
        const btnPlano = e.target.closest('[data-action="plano-menu"]');
        const btnCli = e.target.closest('[data-action="clienteplano-menu"]');

        if (!btnPlano && !btnCli) {
            fecharMenuAcoes();
        }

        if (btnPlano) {
            e.preventDefault();
            e.stopPropagation();
            abrirMenuPlano(btnPlano, btnPlano.dataset.id);
            return;
        }

        if (btnCli) {
            e.preventDefault();
            e.stopPropagation();
            abrirMenuClientePlano(btnCli, btnCli.dataset.id);
            return;
        }
    });

    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape") {
            fecharMenuAcoes();
            fecharDropdownServicos();
        }
    });
}

/* =========================
   API
========================= */
async function apiListarPlanos() {
    const data = await API.get("/planos");
    return Array.isArray(data) ? data : [];
}

async function apiKPIsPlanos() {
    try {
        return await API.get("/planos/kpis");
    } catch (_) {
        return null;
    }
}

async function apiAtualizarStatusPlano(planoId, ativo) {
    return await API.put(`/planos/${encodeURIComponent(planoId)}`, { ativo });
}

async function apiListarClientesDoPlano(planoId) {
    try {
        const data = await API.get(`/planos/${encodeURIComponent(planoId)}/clientes`);
        return Array.isArray(data) ? data : [];
    } catch (_) {
        return [];
    }
}

async function apiRegistrarUsoPlano(clientePlanoId) {
    return await API.post(`/clientes_planos/${encodeURIComponent(clientePlanoId)}/uso`, {});
}

async function apiRenovarClientePlano(clientePlanoId, payload) {
    return await API.post(`/clientes_planos/${encodeURIComponent(clientePlanoId)}/renovar`, payload);
}

async function apiAtualizarClientePlano(clientePlanoId, payload) {
    return await API.put(`/clientes_planos/${encodeURIComponent(clientePlanoId)}`, payload);
}

async function apiCancelarClientePlano(clientePlanoId) {
    return await API.put(`/clientes_planos/${encodeURIComponent(clientePlanoId)}/cancelar`, {});
}

async function apiListarServicosAtivos() {
    try {
        const s = await API.get("/servicos");
        return Array.isArray(s) ? s.filter(x => Boolean(x.ativo) !== false) : [];
    } catch (_) {
        const s = await API.get("/servicos?status=ativo");
        return Array.isArray(s) ? s : [];
    }
}

async function apiListarClientes() {
    const c = await API.get("/clientes");
    return Array.isArray(c) ? c : [];
}

/* =========================
   Load / Views
========================= */
function carregarListaDebounced() {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => carregarListaSafe(), 200);
}

function carregarListaSafe() {
    carregarTelaLista().catch((e) => notify(e?.message || "Erro ao carregar Planos.", "error"));
}

function trocarView(view) {
    state.view = view;

    const vLista = qs("view-planos-lista");
    const vDet = qs("view-plano-detalhe");

    if (view === "detalhe") {
        vLista?.classList.add("hidden");
        vDet?.classList.remove("hidden");
        setPageHeader("Planos", "Combos e estatísticas de uso");
    } else {
        vDet?.classList.add("hidden");
        vLista?.classList.remove("hidden");
        setPageHeader("Planos", "Combos e estatísticas de uso");
    }
}

function setPageHeader(title, subtitle) {
    const t = qs("page-title");
    const s = qs("page-subtitle");
    if (t) t.textContent = title || "Planos";
    if (s) s.textContent = subtitle || "";
}

async function carregarTelaLista() {
    trocarView("lista");

    const planos = await apiListarPlanos();
    state.planos = planos;

    aplicarFiltrosPlanos();
    await renderKPIsPlanos();
    renderTabelaPlanos();
}

async function recarregarTudoMantendoContexto() {
    const planoId = state.planoAtual?.id || null;
    await carregarTelaLista();
    if (planoId) {
        await abrirDetalhePlano(planoId);
    }
}

function aplicarFiltrosPlanos() {
    const busca = (state.buscaPlanos || "").toLowerCase();
    const status = (state.filtroStatusPlanos || "").toLowerCase();

    let lista = [...state.planos];

    if (status === "ativo") {
        lista = lista.filter(p => Boolean(p.ativo) === true);
    } else if (status === "inativo") {
        lista = lista.filter(p => Boolean(p.ativo) === false);
    }

    if (busca) {
        lista = lista.filter(p => `${p.nome || ""}`.toLowerCase().includes(busca));
    }

    state.planosFiltrados = lista;
}

/* =========================
   KPIs
========================= */
function setText(id, txt) {
    const el = qs(id);
    if (el) el.textContent = txt;
}

async function renderKPIsPlanos() {
    const k = await apiKPIsPlanos();

    if (k) {
        setText("kpi-planos-ativos", String(k.planos_ativos ?? 0));
        setText("kpi-planos-ativos-sub", `de ${k.planos_total ?? 0} cadastrados`);

        setText("kpi-clientes-com-plano", String(k.clientes_com_plano ?? 0));
        setText("kpi-clientes-com-plano-sub", "assinaturas ativas");

        setText("kpi-proximos-venc", String(k.proximos_vencimentos_7d ?? 0));
        setText("kpi-proximos-venc-sub", "nos próximos 7 dias");

        setText("kpi-plano-popular", k.plano_popular_nome || "—");
        setText("kpi-plano-popular-sub", `${k.plano_popular_qtd ?? 0} clientes vinculados`);
        return;
    }

    const total = state.planos.length;
    const ativos = state.planos.filter(p => Boolean(p.ativo)).length;

    setText("kpi-planos-ativos", String(ativos));
    setText("kpi-planos-ativos-sub", `de ${total} cadastrados`);

    setText("kpi-clientes-com-plano", "—");
    setText("kpi-clientes-com-plano-sub", "assinaturas ativas");

    setText("kpi-proximos-venc", "—");
    setText("kpi-proximos-venc-sub", "nos próximos 7 dias");

    setText("kpi-plano-popular", "—");
    setText("kpi-plano-popular-sub", "0 clientes vinculados");
}

/* =========================
   Tabela de planos
========================= */
function pillStatusPlano(p) {
    return Boolean(p.ativo)
        ? `<span class="pill pill--success">Ativo</span>`
        : `<span class="pill pill--muted">Inativo</span>`;
}

function badgeUsos(p) {
    const u = Number(p.usos_por_mes || 0);
    return `<span class="badge">${escapeHtml(String(u))}x / mês</span>`;
}

function renderServicosIncluidos(p) {
    const arr = Array.isArray(p.servicos_nomes)
        ? p.servicos_nomes
        : Array.isArray(p.servicos)
            ? p.servicos
            : null;

    if (arr && arr.length) return escapeHtml(arr.join(" + "));
    if (p.servicos_texto) return escapeHtml(p.servicos_texto);
    return `<span style="opacity:.65;">—</span>`;
}

function renderClientesLink(p) {
    const qtd = Number(p.qtd_clientes ?? p.clientes ?? 0);
    const label = `${qtd} clientes`;
    return `
        <button type="button" class="linklike" data-action="ver-clientes" data-id="${escapeHtml(String(p.id))}">
            👥 ${escapeHtml(label)}
        </button>
    `;
}

function renderTabelaPlanos() {
    aplicarFiltrosPlanos();

    const tbody = qs("tbody-planos");
    if (!tbody) return;

    tbody.innerHTML = "";

    const lista = state.planosFiltrados;

    if (!lista.length) {
        const tr = document.createElement("tr");
        tr.innerHTML = `<td colspan="7" style="padding:14px; opacity:.75;">Nenhum plano encontrado.</td>`;
        tbody.appendChild(tr);
        return;
    }

    lista.forEach((p) => {
        const tr = document.createElement("tr");

        tr.innerHTML = `
            <td>
                <div class="desc-cell">
                    <div class="desc-title">${escapeHtml(p.nome || "—")}</div>
                </div>
            </td>
            <td>${renderServicosIncluidos(p)}</td>
            <td>${badgeUsos(p)}</td>
            <td><span class="price-green">${brl(p.valor_mensal)}</span></td>
            <td>${renderClientesLink(p)}</td>
            <td>${pillStatusPlano(p)}</td>
            <td class="td-actions">
                <button type="button" class="dots-btn" data-action="plano-menu" data-id="${escapeHtml(String(p.id))}" aria-label="Ações">⋮</button>
            </td>
        `;

        tr.querySelector('[data-action="ver-clientes"]')?.addEventListener("click", async () => {
            await abrirDetalhePlano(p.id);
        });

        tbody.appendChild(tr);
    });
}

/* =========================
   Detalhe do plano
========================= */
async function abrirDetalhePlano(planoId) {
    const plano = state.planos.find(p => String(p.id) === String(planoId));
    if (!plano) return;

    state.planoAtual = plano;
    state.buscaClientesPlano = "";

    if (qs("busca-clientes-plano")) {
        qs("busca-clientes-plano").value = "";
    }

    setText("det-plano-nome", plano.nome || "Plano");

    const statusEl = qs("det-plano-status");
    if (statusEl) {
        statusEl.textContent = Boolean(plano.ativo) ? "Ativo" : "Inativo";
        statusEl.className = Boolean(plano.ativo) ? "pill pill--success" : "pill pill--muted";
    }

    const sub = [];
    const servTxt = (() => {
        const arr = Array.isArray(plano.servicos_nomes)
            ? plano.servicos_nomes
            : Array.isArray(plano.servicos)
                ? plano.servicos
                : null;

        if (arr && arr.length) return arr.join(" + ");
        if (plano.servicos_texto) return plano.servicos_texto;
        return "";
    })();

    if (servTxt) sub.push(servTxt);
    sub.push(`${Number(plano.usos_por_mes || 0)}x por mês`);
    sub.push(brl(plano.valor_mensal));

    setText("det-plano-sub", sub.filter(Boolean).join(" • "));

    trocarView("detalhe");

    const clientes = await apiListarClientesDoPlano(planoId);
    state.planoAtualClientes = clientes;
    state.clientesFiltrados = clientes;

    renderTabelaClientesPlano();
}

function pillStatusClientePlano(s) {
    const v = String(s || "").toLowerCase();

    if (v === "ativo") return `<span class="pill pill--success">Ativo</span>`;
    if (v === "atrasado") return `<span class="pill pill--danger">Atrasado</span>`;
    if (v === "aguardando_pagamento") return `<span class="pill pill--warn">Aguardando</span>`;
    if (v === "cancelado") return `<span class="pill pill--muted">Cancelado</span>`;
    return `<span class="pill pill--muted">${escapeHtml(s || "—")}</span>`;
}

function renderUsosRestantesBar(usosRest, usosTot) {
    const rest = Math.max(0, Number(usosRest || 0));
    const tot = Math.max(0, Number(usosTot || 0));

    const circles = [];
    const maxDots = Math.max(4, Math.min(8, tot || 4));
    const filled = tot ? Math.round((rest / tot) * maxDots) : 0;

    for (let i = 0; i < maxDots; i++) {
        circles.push(`<span class="dotdot ${i < filled ? "on" : ""}"></span>`);
    }

    return `
        <div class="usos-wrap">
            <div class="dots">${circles.join("")}</div>
            <div class="usos-txt">${escapeHtml(String(rest))}x</div>
        </div>
    `;
}

function isVencimentoEm7d(iso) {
    if (!iso || !String(iso).includes("-")) return false;
    const hoje = todayISO();
    const limite = addDaysISO(hoje, 7);
    return String(iso).slice(0, 10) >= hoje && String(iso).slice(0, 10) <= limite;
}

function renderProximoPagamentoCell(iso) {
    const d = String(iso || "").slice(0, 10);
    if (!d || !d.includes("-")) return `<span style="opacity:.65;">—</span>`;

    if (isVencimentoEm7d(d)) {
        return `<span class="due-soon">${formatDataBR(d)} <span class="tag-red">em 7d</span></span>`;
    }

    return escapeHtml(formatDataBR(d));
}

function aplicarFiltroClientesPlano() {
    const busca = (state.buscaClientesPlano || "").toLowerCase();
    let lista = [...state.planoAtualClientes];

    if (busca) {
        lista = lista.filter(c => `${c.cliente_nome || c.nome || ""}`.toLowerCase().includes(busca));
    }

    state.clientesFiltrados = lista;
}

function renderTabelaClientesPlano() {
    aplicarFiltroClientesPlano();

    const tbody = qs("tbody-clientes-plano");
    if (!tbody) return;

    tbody.innerHTML = "";

    const lista = state.clientesFiltrados;

    if (!lista.length) {
        const tr = document.createElement("tr");
        tr.innerHTML = `<td colspan="8" style="padding:14px; opacity:.75;">Nenhum cliente vinculado encontrado.</td>`;
        tbody.appendChild(tr);
        return;
    }

    lista.forEach((c) => {
        const tr = document.createElement("tr");

        const clienteNome = c.cliente_nome || c.nome || "Cliente";
        const inicio = c.data_inicio ? String(c.data_inicio).slice(0, 10) : "";
        const prox = c.proximo_vencimento ? String(c.proximo_vencimento).slice(0, 10) : "";
        const usosTot = Number(c.usos_totais ?? c.usos_por_mes ?? state.planoAtual?.usos_por_mes ?? 0);
        const usosRest = Number(c.usos_restantes ?? 0);

        tr.innerHTML = `
            <td>
                <div class="cliente-cell">
                    <div class="avatar">${escapeHtml((clienteNome[0] || "C").toUpperCase())}</div>
                    <div>
                        <div class="desc-title">${escapeHtml(clienteNome)}</div>
                    </div>
                </div>
            </td>
            <td>${inicio ? escapeHtml(formatDataBR(inicio)) : `<span style="opacity:.65;">—</span>`}</td>
            <td>${renderProximoPagamentoCell(prox)}</td>
            <td>${escapeHtml(String(usosTot))}x</td>
            <td>${renderUsosRestantesBar(usosRest, usosTot)}</td>
            <td>${escapeHtml((c.forma_pagamento || "—"))}</td>
            <td>${pillStatusClientePlano(c.status)}</td>
            <td class="td-actions">
                <button type="button" class="dots-btn" data-action="clienteplano-menu" data-id="${escapeHtml(String(c.id || c.cliente_plano_id))}" aria-label="Ações">⋮</button>
            </td>
        `;

        tbody.appendChild(tr);
    });
}

/* =========================
   Menus de ações
========================= */
function abrirMenuPlano(anchorBtn, planoId) {
    fecharMenuAcoes();

    const plano = state.planos.find(p => String(p.id) === String(planoId));
    if (!plano) return;

    const rect = anchorBtn.getBoundingClientRect();
    const labelToggle = Boolean(plano.ativo) ? "Inativar Plano" : "Ativar Plano";
    const iconToggle = Boolean(plano.ativo) ? "🚫" : "✅";

    menuEl = document.createElement("div");
    menuEl.className = "action-menu";
    menuEl.innerHTML = `
        <button type="button" class="am-opt" data-opt="ver-clientes" data-id="${escapeHtml(String(planoId))}">👥 Ver Clientes</button>
        <button type="button" class="am-opt" data-opt="toggle-ativo" data-id="${escapeHtml(String(planoId))}">${iconToggle} ${escapeHtml(labelToggle)}</button>
    `;

    document.body.appendChild(menuEl);
    posicionarMenu(menuEl, rect);

    menuEl.addEventListener("click", async (e) => {
        const opt = e.target.closest(".am-opt");
        if (!opt) return;

        const oid = opt.dataset.id;
        const action = opt.dataset.opt;

        fecharMenuAcoes();

        if (action === "ver-clientes") {
            await abrirDetalhePlano(oid);
            return;
        }

        if (action === "toggle-ativo") {
            try {
                const novoAtivo = !Boolean(plano.ativo);
                const res = await apiAtualizarStatusPlano(oid, novoAtivo);

                notify(
                    res?.mensagem || (novoAtivo ? "Plano ativado com sucesso." : "Plano inativado com sucesso."),
                    "success"
                );

                await carregarTelaLista();
            } catch (err) {
                notify(err?.message || "Erro ao atualizar status do plano.", "error");
            }
        }
    });
}

function abrirMenuClientePlano(anchorBtn, clientePlanoId) {
    fecharMenuAcoes();

    const rect = anchorBtn.getBoundingClientRect();

    menuEl = document.createElement("div");
    menuEl.className = "action-menu";
    menuEl.innerHTML = `
        <button type="button" class="am-opt" data-opt="registrar-uso" data-id="${escapeHtml(String(clientePlanoId))}">⭕ Registrar Uso</button>
        <button type="button" class="am-opt" data-opt="renovar" data-id="${escapeHtml(String(clientePlanoId))}">🔄 Renovar Plano</button>
        <button type="button" class="am-opt" data-opt="editar" data-id="${escapeHtml(String(clientePlanoId))}">✏️ Editar</button>
        <button type="button" class="am-opt am-danger" data-opt="cancelar" data-id="${escapeHtml(String(clientePlanoId))}">❌ Cancelar Plano</button>
    `;

    document.body.appendChild(menuEl);
    posicionarMenu(menuEl, rect);

    menuEl.addEventListener("click", async (e) => {
        const opt = e.target.closest(".am-opt");
        if (!opt) return;

        const id = opt.dataset.id;
        const action = opt.dataset.opt;

        fecharMenuAcoes();

        if (action === "registrar-uso") {
            try {
                const res = await apiRegistrarUsoPlano(id);
                notify(res?.mensagem || "Uso registrado com sucesso.", "success");
                await recarregarTudoMantendoContexto();
            } catch (err) {
                notify(err?.message || "Erro ao registrar uso.", "error");
            }
            return;
        }

        if (action === "renovar") {
            abrirModalRenovarClientePlano(id);
            return;
        }

        if (action === "editar") {
            abrirModalEditarClientePlano(id);
            return;
        }

        if (action === "cancelar") {
            try {
                await apiCancelarClientePlano(id);
                notify("Plano cancelado.", "success");
                await recarregarTudoMantendoContexto();
            } catch (err) {
                notify(err?.message || "Erro ao cancelar plano.", "error");
            }
        }
    });
}

function fecharMenuAcoes() {
    if (menuEl) {
        menuEl.remove();
        menuEl = null;
    }
}

function posicionarMenu(el, rect) {
    el.style.position = "fixed";
    el.style.zIndex = "9999";

    const margin = 12;
    const menuW = el.offsetWidth;
    const menuH = el.offsetHeight;

    let left = rect.left;
    left = Math.min(Math.max(margin, left), window.innerWidth - menuW - margin);

    let top = rect.bottom + 8;
    if (top + menuH > window.innerHeight - margin) {
        top = rect.top - menuH - 8;
    }
    top = Math.min(Math.max(margin, top), window.innerHeight - menuH - margin);

    el.style.top = `${top}px`;
    el.style.left = `${left}px`;
}

/* =========================
   Modais
========================= */
function modalOpen(id) {
    qs(id)?.classList.add("is-open");
}

function modalClose(id) {
    qs(id)?.classList.remove("is-open");
}

function bindModalOverlayClose(overlayId) {
    const overlay = qs(overlayId);
    if (!overlay) return;

    overlay.addEventListener("click", (e) => {
        if (e.target === overlay) {
            overlay.classList.remove("is-open");
        }
    });
}

function abrirModalRenovarClientePlano(clientePlanoId) {
    const item = findClientePlanoById(clientePlanoId);
    if (!item) {
        notify("Cliente do plano não encontrado.", "error");
        return;
    }

    state.clientePlanoSelecionado = item;

    qs("form-renovar-cliente-plano")?.reset();
    qs("rp-cliente").value = item.cliente_nome || item.nome || "Cliente";
    qs("rp-proximo-vencimento").value = getDefaultRenewDate(item);
    qs("rp-forma").value = getFormaPagamentoSafe(item.forma_pagamento, "pix");

    modalOpen("modal-renovar-cliente-plano");
}

function abrirModalEditarClientePlano(clientePlanoId) {
    const item = findClientePlanoById(clientePlanoId);
    if (!item) {
        notify("Cliente do plano não encontrado.", "error");
        return;
    }

    state.clientePlanoSelecionado = item;

    qs("form-editar-cliente-plano")?.reset();
    qs("ep-cliente").value = item.cliente_nome || item.nome || "Cliente";
    qs("ep-data-inicio").value = toDateInputValue(item.data_inicio);
    qs("ep-proximo-vencimento").value = toDateInputValue(item.proximo_vencimento);
    qs("ep-usos-totais").value = Number(item.usos_totais ?? state.planoAtual?.usos_por_mes ?? 0);
    qs("ep-usos-restantes").value = Number(item.usos_restantes ?? 0);
    qs("ep-forma").value = getFormaPagamentoSafe(item.forma_pagamento, "");
    qs("ep-status").value = item.status || "ativo";

    modalOpen("modal-editar-cliente-plano");
}

/* =========================
   Novo Plano - multiselect
========================= */
function bindMultiSelectServicos() {
    qs("ms-servicos-input")?.addEventListener("click", toggleDropdownServicos);

    qs("ms-servicos-input")?.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            toggleDropdownServicos();
        }
    });

    qs("ms-servicos-busca")?.addEventListener("input", () => {
        const q = (qs("ms-servicos-busca")?.value || "").trim().toLowerCase();
        const filtrada = !q
            ? servicosAll
            : servicosAll.filter(s => String(s.nome || "").toLowerCase().includes(q));
        renderDropdownServicos(filtrada);
    });

    document.addEventListener("click", (e) => {
        const wrap = qs("ms-servicos");
        const dd = qs("ms-servicos-dropdown");
        if (!wrap || !dd || dd.classList.contains("hidden")) return;

        if (!wrap.contains(e.target)) {
            fecharDropdownServicos();
        }
    });
}

async function abrirModalNovoPlano() {
    qs("form-novo-plano")?.reset();
    servicosSelecionados.clear();
    renderChipsServicos();

    servicosAll = await apiListarServicosAtivos();
    renderDropdownServicos(servicosAll);
    fecharDropdownServicos();

    modalOpen("modal-novo-plano");
}

function abrirDropdownServicos() {
    const dd = qs("ms-servicos-dropdown");
    if (!dd) return;
    dd.classList.remove("hidden");
    qs("ms-servicos-input")?.setAttribute("aria-expanded", "true");
    qs("ms-servicos-busca")?.focus();
}

function fecharDropdownServicos() {
    const dd = qs("ms-servicos-dropdown");
    if (!dd) return;
    dd.classList.add("hidden");
    qs("ms-servicos-input")?.setAttribute("aria-expanded", "false");
    if (qs("ms-servicos-busca")) qs("ms-servicos-busca").value = "";
}

function toggleDropdownServicos() {
    const dd = qs("ms-servicos-dropdown");
    if (!dd) return;
    dd.classList.contains("hidden") ? abrirDropdownServicos() : fecharDropdownServicos();
}

function renderDropdownServicos(lista) {
    const box = qs("ms-servicos-lista");
    if (!box) return;

    if (!lista || !lista.length) {
        box.innerHTML = `<div style="opacity:.7; padding:10px;">Nenhum serviço encontrado.</div>`;
        return;
    }

    box.innerHTML = lista.map(s => {
        const sid = String(s.id);
        const checked = servicosSelecionados.has(sid) ? "checked" : "";
        return `
            <label class="ms-item" data-id="${escapeHtml(sid)}">
                <input type="checkbox" ${checked} />
                <div>
                    <div class="name">${escapeHtml(s.nome || "Serviço")}</div>
                    <div class="sub">${escapeHtml(s.categoria || "")}</div>
                </div>
            </label>
        `;
    }).join("");

    box.querySelectorAll(".ms-item").forEach(item => {
        item.addEventListener("click", (e) => {
            if (e.target.tagName.toLowerCase() === "input") return;

            const sid = String(item.dataset.id);
            const input = item.querySelector("input");
            if (!input) return;

            input.checked = !input.checked;
            onServicoCheckboxChange(sid, input.checked);
        });

        const sid = String(item.dataset.id);
        const input = item.querySelector("input");
        input?.addEventListener("change", () => onServicoCheckboxChange(sid, input.checked));
    });
}

function onServicoCheckboxChange(sid, isChecked) {
    const s = servicosAll.find(x => String(x.id) === String(sid));
    if (!s) return;

    if (isChecked) {
        servicosSelecionados.set(String(sid), { id: s.id, nome: s.nome || "Serviço" });
    } else {
        servicosSelecionados.delete(String(sid));
    }

    renderChipsServicos();
}

function renderChipsServicos() {
    const chips = qs("ms-servicos-chips");
    if (!chips) return;

    const arr = [...servicosSelecionados.values()];
    if (!arr.length) {
        chips.innerHTML = `<span class="ms-placeholder">Selecione serviços...</span>`;
        return;
    }

    chips.innerHTML = arr.map(s => `
        <span class="ms-chip">
            ${escapeHtml(s.nome)}
            <button type="button" aria-label="Remover" data-remove="${escapeHtml(String(s.id))}">×</button>
        </span>
    `).join("");

    chips.querySelectorAll("button[data-remove]").forEach(btn => {
        btn.addEventListener("click", (e) => {
            e.stopPropagation();
            const id = String(btn.dataset.remove);
            servicosSelecionados.delete(id);

            const item = qs("ms-servicos-lista")?.querySelector(`.ms-item[data-id="${CSS.escape(id)}"] input`);
            if (item) item.checked = false;

            renderChipsServicos();
        });
    });
}

/* =========================
   Forms
========================= */
function bindForms() {
    qs("form-novo-plano")?.addEventListener("submit", async (e) => {
        e.preventDefault();

        try {
            const nome = (qs("pl-nome")?.value || "").trim();
            const valor_mensal = Number(qs("pl-valor")?.value || 0);
            const usos_por_mes = Number(qs("pl-usos")?.value || 0);
            const statusUI = (qs("pl-status")?.value || "ativo").toLowerCase();

            const servicos = [...servicosSelecionados.keys()].map(Number).filter(Boolean);
            const ativo = statusUI === "ativo";

            if (!nome) return notify("Informe o nome do plano.", "warning");
            if (!servicos.length) return notify("Selecione pelo menos 1 serviço.", "warning");
            if (usos_por_mes <= 0) return notify("Usos/mês inválido.", "warning");
            if (valor_mensal <= 0) return notify("Valor inválido.", "warning");

            const res = await API.post("/planos", {
                nome,
                valor_mensal,
                usos_por_mes,
                servicos,
                ativo,
            });

            modalClose("modal-novo-plano");
            notify(res?.mensagem || "Plano criado com sucesso.", "success");

            await carregarTelaLista();
        } catch (err) {
            notify(err?.message || "Erro ao criar plano.", "error");
        }
    });

    qs("form-vincular-cliente")?.addEventListener("submit", async (e) => {
        e.preventDefault();

        try {
            const planoId = state.planoAtual?.id;
            if (!planoId) return;

            const cliente_id = Number(qs("vc-cliente")?.value || 0);
            const forma_pagamento = qs("vc-forma")?.value;
            const status = qs("vc-status")?.value;

            if (!cliente_id) {
                return notify("Selecione um cliente válido.", "warning");
            }
            if (!forma_pagamento) return notify("Selecione a forma de pagamento.", "warning");
            if (!status) return notify("Selecione o status.", "warning");

            const hoje = todayISO();

            const proximo_vencimento =
                status === "ativo"
                    ? addDaysISO(hoje, 30)
                    : null;

            const res = await API.post(`/planos/${encodeURIComponent(planoId)}/clientes`, {
                cliente_id,
                forma_pagamento,
                status,
                data_inicio: hoje,
                proximo_vencimento,
            });

            modalClose("modal-vincular-cliente");
            notify(res?.mensagem || "Cliente vinculado com sucesso.", "success");

            await recarregarTudoMantendoContexto();
        } catch (err) {
            notify(err?.message || "Erro ao vincular cliente.", "error");
        }
    });

    qs("form-renovar-cliente-plano")?.addEventListener("submit", async (e) => {
        e.preventDefault();

        try {
            const item = state.clientePlanoSelecionado;
            if (!item?.id) return notify("Cliente do plano não encontrado.", "error");

            const proximo_vencimento = qs("rp-proximo-vencimento")?.value || "";
            const forma_pagamento = qs("rp-forma")?.value || "";

            if (!proximo_vencimento) return notify("Informe a nova data de vencimento.", "warning");
            if (!forma_pagamento) return notify("Selecione a forma de pagamento.", "warning");

            const res = await apiRenovarClientePlano(item.id, {
                proximo_vencimento,
                forma_pagamento,
            });

            modalClose("modal-renovar-cliente-plano");
            notify(res?.mensagem || "Plano renovado com sucesso.", "success");
            await recarregarTudoMantendoContexto();
        } catch (err) {
            notify(err?.message || "Erro ao renovar plano.", "error");
        }
    });

    qs("form-editar-cliente-plano")?.addEventListener("submit", async (e) => {
        e.preventDefault();

        try {
            const item = state.clientePlanoSelecionado;
            if (!item?.id) return notify("Cliente do plano não encontrado.", "error");

            const data_inicio = qs("ep-data-inicio")?.value || "";
            const proximo_vencimento = qs("ep-proximo-vencimento")?.value || "";
            const usos_totais = Number(qs("ep-usos-totais")?.value || 0);
            const usos_restantes = Number(qs("ep-usos-restantes")?.value || 0);
            const forma_pagamento = qs("ep-forma")?.value || "";
            const status = qs("ep-status")?.value || "ativo";

            if (usos_totais < 0) return notify("Usos totais inválido.", "warning");
            if (usos_restantes < 0) return notify("Usos restantes inválido.", "warning");
            if (usos_restantes > usos_totais) return notify("Usos restantes não podem ser maiores que os usos totais.", "warning");
            if (!status) return notify("Selecione o status.", "warning");

            const res = await apiAtualizarClientePlano(item.id, {
                data_inicio,
                proximo_vencimento,
                usos_totais,
                usos_restantes,
                forma_pagamento,
                status,
            });

            modalClose("modal-editar-cliente-plano");
            notify(res?.mensagem || "Plano do cliente atualizado com sucesso.", "success");
            await recarregarTudoMantendoContexto();
        } catch (err) {
            notify(err?.message || "Erro ao editar plano do cliente.", "error");
        }
    });
}

/* =========================
   Modal Vincular Cliente
========================= */
async function abrirModalVincularCliente() {
    const planoId = state.planoAtual?.id;
    if (!planoId) return;

    qs("form-vincular-cliente")?.reset();

    const input = qs("vc-cliente-busca");
    const resultados = qs("vc-cliente-resultados");
    const hidden = qs("vc-cliente");

    hidden.value = "";
    input.value = "";
    resultados.innerHTML = "";

    let timeout = null;

    input.oninput = () => {
        const termo = input.value.trim();

        clearTimeout(timeout);

        if (termo.length < 2) {
            resultados.innerHTML = "";
            hidden.value = "";
            return;
        }

        timeout = setTimeout(async () => {
            try {
                const res = await API.get(`/clientes/busca?q=${encodeURIComponent(termo)}`);
                const lista = res || [];

                resultados.innerHTML = "";

                lista.forEach(c => {
                    const div = document.createElement("div");
                    div.className = "dropdown-item";
                    div.textContent = `${c.nome} - ${c.telefone}`;

                    div.onclick = () => {
                        input.value = `${c.nome} - ${c.telefone}`;
                        hidden.value = c.id;
                        resultados.innerHTML = "";
                    };

                    resultados.appendChild(div);
                });

            } catch (e) {
                resultados.innerHTML = "";
            }
        }, 300);
    };

    modalOpen("modal-vincular-cliente");
}