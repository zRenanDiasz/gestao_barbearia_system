let clientesBase = [];
let listaAtual = [];
let agendamentosBase = []; // fallback (só se backend não mandar total_visitas/ultima_visita/status_cliente)

document.addEventListener("DOMContentLoaded", () => {
    initUI();
    carregarTudo().catch(e => alert(e.message));
});

/* =========================
   UTIL
========================= */
function norm(s) { return String(s || "").trim().toLowerCase(); }

function isoParaBR(iso) {
    if (!iso) return "—";
    const s = String(iso).trim();
    const d = s.includes("T") ? s.split("T")[0] : (s.includes(" ") ? s.split(" ")[0] : s);
    if (!d.includes("-")) return s;
    const [yyyy, mm, dd] = d.split("-");
    if (!yyyy || !mm || !dd) return s;
    return `${dd}/${mm}/${yyyy}`;
}

function escapeHtml(str) {
    return String(str)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

function setText(id, val) {
    const el = document.getElementById(id);
    if (el) el.textContent = String(val);
}

/* =========================
   LOAD
========================= */
async function carregarTudo() {
    const dataClientes = await API.get("/clientes");
    clientesBase = Array.isArray(dataClientes) ? dataClientes : [];

    // Só busca agendamentos se REALMENTE precisar (fallback)
    const precisaFallback = clientesBase.some(c =>
        c.total_visitas == null || c.ultima_visita == null || c.status_cliente == null
    );

    if (precisaFallback) {
        try {
            const dataAg = await API.get("/agendamentos");
            agendamentosBase = Array.isArray(dataAg) ? dataAg : [];
        } catch (e) {
            agendamentosBase = [];
        }
    } else {
        agendamentosBase = [];
    }

    aplicarFiltros();
}

/* =========================
   STATS POR CLIENTE
   - prioridade: backend (total_visitas, ultima_visita, status_cliente) ✅
   - fallback: calcula pelos agendamentos
========================= */
function calcClienteStats(c) {
    const hasTotal = c && (c.total_visitas !== undefined && c.total_visitas !== null);
    const hasUltima = c && (c.ultima_visita !== undefined && c.ultima_visita !== null);
    const hasStatus = c && (c.status_cliente !== undefined && c.status_cliente !== null);

    if (hasTotal || hasUltima || hasStatus) {
        const totalVisitas = Number(c.total_visitas || 0);
        const ultimaISO = c.ultima_visita ? String(c.ultima_visita).slice(0, 10) : null;
        const st = norm(c.status_cliente) === "ativo" ? "ativo" : "inativo";
        return { totalVisitas, ultimaISO, status: st };
    }

    // Fallback: considera visita como agendamento concluído/pago/finalizado
    const concluidos = agendamentosBase.filter(a => {
        const sameCliente = String(a.cliente_id) === String(c.id);
        const st = norm(a.status);
        const okStatus = (st === "concluido" || st === "concluído" || st === "finalizado" || st === "pago");
        return sameCliente && okStatus;
    });

    const totalVisitas = concluidos.length;

    let ultimaISO = null;
    for (const a of concluidos) {
        const d = a.data ? String(a.data).slice(0, 10) : null;
        if (!d) continue;
        if (!ultimaISO || d > ultimaISO) ultimaISO = d;
    }

    const ativo = isAtivoPorUltimaVisita(ultimaISO, 60);
    return { totalVisitas, ultimaISO, status: ativo ? "ativo" : "inativo" };
}

function isAtivoPorUltimaVisita(ultimaISO, diasJanela) {
    if (!ultimaISO) return false;
    const dt = new Date(String(ultimaISO).slice(0, 10) + "T00:00:00");
    if (isNaN(dt.getTime())) return false;

    const hoje = new Date();
    const diffMs = hoje.getTime() - dt.getTime();
    const diffDias = Math.floor(diffMs / (1000 * 60 * 60 * 24));
    return diffDias <= diasJanela;
}

/* =========================
   FILTERS + KPIS
========================= */
function aplicarFiltros() {
    const busca = norm(document.getElementById("busca-clientes")?.value);
    const st = document.getElementById("filtro-status")?.value || "";

    let lista = [...clientesBase];

    // Enriquecimento: stats
    lista = lista.map(c => {
        const stats = calcClienteStats(c);
        return {
            ...c,
            __ultimaISO: stats.ultimaISO,
            __totalVisitas: stats.totalVisitas,
            __status: stats.status
        };
    });

    if (busca) {
        lista = lista.filter(c => {
            const n = norm(c.nome);
            const t = norm(c.telefone);
            return n.includes(busca) || t.includes(busca);
        });
    }

    if (st) {
        lista = lista.filter(c => c.__status === st);
    }

    listaAtual = lista;
    renderKPIs(listaAtual);
    renderTabela(listaAtual);
}

function renderKPIs(lista) {
    const total = lista.length;
    const ativos = lista.filter(c => c.__status === "ativo").length;
    const inativos = lista.filter(c => c.__status === "inativo").length;

    setText("kpi-total-clientes", total);
    setText("kpi-ativos", ativos);
    setText("kpi-inativos", inativos);

    const pct = total ? ((ativos / total) * 100).toFixed(1).replace(".", ",") : "0,0";
    setText("kpi-ativos-pct", total ? `${pct}% do total` : "—");

    const novosMes = lista.filter(c => isCriadoEsteMes(c.criado_em)).length;
    setText("kpi-novos-mes", novosMes);
}

function isCriadoEsteMes(criado_em) {
    if (!criado_em) return false;
    const s = String(criado_em).replace(" ", "T");
    const dt = new Date(s);
    if (isNaN(dt.getTime())) return false;

    const hoje = new Date();
    return dt.getFullYear() === hoje.getFullYear() && dt.getMonth() === hoje.getMonth();
}

/* =========================
   TABLE + MENU ⋮
========================= */
let rowMenuEl = null;

function renderTabela(lista) {
    const tbody = document.getElementById("tbody-clientes");
    if (!tbody) return;

    tbody.innerHTML = "";

    lista.forEach(c => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td><strong>${escapeHtml(c.nome || "")}</strong></td>

          <td>
            <div class="contact">
              <span class="ico">📞</span>
              <span>${escapeHtml(c.telefone || "—")}</span>
            </div>
          </td>

          <td>${c.__ultimaISO ? isoParaBR(c.__ultimaISO) : "—"}</td>

          <td><span class="pill count">${Number(c.__totalVisitas || 0)}</span></td>

          <td>${badgeStatus(c.__status)}</td>

          <td class="td-actions">
            <button type="button" class="row-menu-btn" data-action="row-menu" data-id="${c.id}">⋮</button>
          </td>
        `;
        tbody.appendChild(tr);
    });
}

function badgeStatus(st) {
    const s = norm(st);
    if (s === "ativo") return `<span class="pill ativo">Ativo</span>`;
    return `<span class="pill inativo">Inativo</span>`;
}

function abrirRowMenu(anchorBtn, id) {
    fecharRowMenu();

    const c = listaAtual.find(x => String(x.id) === String(id));
    if (!c) return;

    const rect = anchorBtn.getBoundingClientRect();

    rowMenuEl = document.createElement("div");
    rowMenuEl.className = "row-menu";
    rowMenuEl.style.position = "fixed";
    rowMenuEl.style.zIndex = "9999";

    rowMenuEl.innerHTML = `
        <button type="button" class="row-opt" data-act="editar" data-id="${id}">✎ <span>Editar</span></button>
        <button type="button" class="row-opt danger" data-act="excluir" data-id="${id}">🗑 <span>Excluir</span></button>
    `;

    document.body.appendChild(rowMenuEl);

    const menuW = rowMenuEl.offsetWidth;
    const menuH = rowMenuEl.offsetHeight;
    const gap = 8;

    let top = rect.bottom + gap;
    let left = rect.left;

    if (top + menuH > window.innerHeight - 8) {
        top = rect.top - menuH - gap;
    }

    left = Math.min(left, window.innerWidth - menuW - 12);
    left = Math.max(12, left);

    top = Math.max(12, top);
    top = Math.min(window.innerHeight - menuH - 12, top);

    rowMenuEl.style.top = `${top}px`;
    rowMenuEl.style.left = `${left}px`;

    rowMenuEl.addEventListener("click", async (e) => {
        const opt = e.target.closest(".row-opt");
        if (!opt) return;

        const act = opt.dataset.act;
        const cid = opt.dataset.id;

        if (act === "editar") abrirModalCliente(c);
        if (act === "excluir") await excluirCliente(cid);

        fecharRowMenu();
    });

    window.addEventListener("scroll", fecharRowMenu, { once: true, passive: true });
    window.addEventListener("resize", fecharRowMenu, { once: true });
}

function fecharRowMenu() {
    if (rowMenuEl) {
        rowMenuEl.remove();
        rowMenuEl = null;
    }
}

/* =========================
   MODAL CLIENTE
========================= */
const modalCliente = () => document.getElementById("modal-cliente");
const formCliente = () => document.getElementById("form-cliente");

function abrirModalCliente(cliente = null) {
    const m = modalCliente();
    if (!m) return;

    const isEdit = !!cliente;
    document.getElementById("titulo-modal-cliente").textContent = isEdit ? "Editar Cliente" : "Novo Cliente";
    document.getElementById("btn-salvar-cliente").textContent = isEdit ? "Salvar Alterações" : "Adicionar Cliente";

    if (isEdit) {
        m.dataset.editId = String(cliente.id);
        document.getElementById("c-nome").value = cliente.nome || "";
        document.getElementById("c-telefone").value = cliente.telefone || "";
    } else {
        delete m.dataset.editId;
        formCliente()?.reset();
    }

    m.classList.add("is-open");
}

function fecharModalCliente() {
    const m = modalCliente();
    if (!m) return;
    m.classList.remove("is-open");
}

function confirmModal(message) {
    return new Promise((resolve) => {
        const overlay = document.getElementById("modal-confirm");
        const msg = document.getElementById("confirm-msg");
        const btnSim = document.getElementById("btn-confirm-sim");
        const btnNao = document.getElementById("btn-confirm-nao");
        const btnX = document.getElementById("btn-fechar-confirm");

        if (!overlay || !msg || !btnSim || !btnNao || !btnX) {
            resolve(window.confirm(message));
            return;
        }

        msg.textContent = message;

        const fechar = (val) => {
            overlay.classList.remove("is-open");
            overlay.setAttribute("aria-hidden", "true");
            limpar();
            resolve(val);
        };

        const limpar = () => {
            btnSim.onclick = null;
            btnNao.onclick = null;
            btnX.onclick = null;
            overlay.onclick = null;
            document.onkeydown = null;
        };

        btnSim.onclick = () => fechar(true);
        btnNao.onclick = () => fechar(false);
        btnX.onclick = () => fechar(false);

        overlay.onclick = (e) => {
            if (e.target === overlay) fechar(false);
        };

        document.onkeydown = (e) => {
            if (e.key === "Escape") fechar(false);
        };

        overlay.classList.add("is-open");
        overlay.setAttribute("aria-hidden", "false");
    });
}

/* =========================
   AÇÕES
========================= */
async function salvarCliente(e) {
    e.preventDefault();

    const m = modalCliente();
    const editId = m?.dataset.editId || null;

    const nome = document.getElementById("c-nome").value.trim();
    const telefone = document.getElementById("c-telefone").value.trim();

    if (!nome) return alert("Informe o nome do cliente.");
    if (!telefone) return alert("Informe o telefone do cliente.");

    try {
        if (editId) {
            await API.put(`/clientes/${editId}`, { nome, telefone });
        } else {
            await API.post("/clientes", { nome, telefone });
        }

        fecharModalCliente();
        await carregarTudo();
    } catch (err) {
        alert(err.message);
    }
}

async function excluirCliente(id) {
    const ok = await confirmModal("Deseja realmente excluir este cliente?");
    if (!ok) return;

    try {
        await API.delete(`/clientes/${id}`);
        await carregarTudo();
    } catch (err) {
        alert(err.message);
    }
}

/* =========================
   UI INIT
========================= */
function initUI() {
    document.getElementById("busca-clientes")?.addEventListener("input", debounce(aplicarFiltros, 150));
    document.getElementById("filtro-status")?.addEventListener("change", aplicarFiltros);

    document.getElementById("btn-novo-cliente")?.addEventListener("click", () => abrirModalCliente());

    document.getElementById("btn-fechar-cliente")?.addEventListener("click", fecharModalCliente);
    document.getElementById("btn-cancelar-cliente")?.addEventListener("click", fecharModalCliente);

    modalCliente()?.addEventListener("click", (e) => {
        if (e.target === modalCliente()) fecharModalCliente();
    });

    formCliente()?.addEventListener("submit", salvarCliente);

    document.addEventListener("click", (e) => {
        const btn = e.target.closest('[data-action="row-menu"]');
        if (!btn) {
            fecharRowMenu();
            return;
        }
        e.preventDefault();
        e.stopPropagation();
        abrirRowMenu(btn, btn.dataset.id);
    });

    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape") {
            fecharRowMenu();
            fecharModalCliente();
        }
    });
}

function debounce(fn, ms) {
    let t = null;
    return (...args) => {
        clearTimeout(t);
        t = setTimeout(() => fn(...args), ms);
    };
}