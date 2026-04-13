// static/js/servicos.js

document.addEventListener("DOMContentLoaded", () => {
    initServicos().catch(err => showInfo(err.message || "Erro ao iniciar.", "Erro"));
});

let SERVICOS = [];
let EDIT_ID = null;

// confirm modal action
let confirmAction = null;

/* =========================
   Helpers
========================= */
function brl(n) {
    return `R$ ${Number(n || 0).toFixed(2).replace(".", ",")}`;
}

function escapeHtml(str) {
    return String(str).replace(/[&<>"']/g, s => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#039;"
    }[s]));
}

function debounce(fn, ms) {
    let t = null;
    return (...args) => {
        clearTimeout(t);
        t = setTimeout(() => fn(...args), ms);
    };
}

function openModal(id) {
    const el = document.getElementById(id);
    if (el) el.classList.add("is-open");
}

function closeModal(id) {
    const el = document.getElementById(id);
    if (el) el.classList.remove("is-open");
}

function showInfo(msg, title = "Aviso") {
    const overlay = document.getElementById("modal-info");
    if (!overlay) return;

    document.getElementById("info-title").textContent = title;
    document.getElementById("info-msg").textContent = msg;

    openModal("modal-info");
}

function closeInfo() {
    closeModal("modal-info");
}

function openConfirm(title, msg, actionFn) {
    document.getElementById("confirm-title").textContent = title;
    document.getElementById("confirm-msg").textContent = msg;
    confirmAction = actionFn;
    openModal("modal-confirm");
}

/* =========================
   Init
========================= */
async function initServicos() {
    bindUI();
    await reloadAll();
}

function bindUI() {
    const busca = document.getElementById("busca-servicos");
    const filtroCat = document.getElementById("filtro-categoria");
    const filtroStatus = document.getElementById("filtro-status");

    if (busca) busca.addEventListener("input", debounce(render, 200));
    if (filtroCat) filtroCat.addEventListener("change", render);

    // status altera o fetch (ativos/inativos/todos)
    if (filtroStatus) filtroStatus.addEventListener("change", () => reloadAll().catch(e => showInfo(e.message, "Erro")));

    // novo serviço
    document.getElementById("btn-novo-servico")?.addEventListener("click", () => {
        EDIT_ID = null;
        setModalTitle("Novo Serviço", "Preencha os dados para cadastrar.");
        fillForm({ nome: "", descricao: "", categoria: "", duracao: 30, preco: 0, ativo: 1 });
        openModal("modal-servico");
    });

    // fechar modal serviço
    document.getElementById("btn-fechar-servico")?.addEventListener("click", () => closeModal("modal-servico"));
    document.getElementById("btn-cancelar-servico")?.addEventListener("click", () => closeModal("modal-servico"));
    document.getElementById("modal-servico")?.addEventListener("click", (e) => {
        if (e.target.id === "modal-servico") closeModal("modal-servico");
    });

    // submit form
    document.getElementById("form-servico")?.addEventListener("submit", async (e) => {
        e.preventDefault();
        await salvarServico().catch(err => showInfo(err.message || "Erro ao salvar.", "Erro"));
    });

    // confirm modal
    document.getElementById("btn-fechar-confirm")?.addEventListener("click", () => closeModal("modal-confirm"));
    document.getElementById("btn-confirm-nao")?.addEventListener("click", () => closeModal("modal-confirm"));
    document.getElementById("btn-confirm-sim")?.addEventListener("click", async () => {
        try {
            if (confirmAction) await confirmAction();
        } catch (e) {
            showInfo(e.message || "Erro ao executar ação.", "Erro");
        } finally {
            confirmAction = null;
            closeModal("modal-confirm");
        }
    });

    // info modal
    document.getElementById("btn-fechar-info")?.addEventListener("click", closeInfo);
    document.getElementById("btn-info-ok")?.addEventListener("click", closeInfo);
    document.getElementById("modal-info")?.addEventListener("click", (e) => {
        if (e.target.id === "modal-info") closeInfo();
    });

    // clique fora fecha dropdowns
    document.addEventListener("click", (e) => {
        document.querySelectorAll(".menu.open").forEach(m => {
            const kebab = m.previousElementSibling;
            if (!m.contains(e.target) && kebab && !kebab.contains(e.target)) {
                m.classList.remove("open");
            }
        });
    });

    // ESC fecha modais/menus
    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape") {
            closeModal("modal-servico");
            closeModal("modal-confirm");
            closeInfo();
            document.querySelectorAll(".menu.open").forEach(m => m.classList.remove("open"));
        }
    });
}

/* =========================
   Data loading
========================= */
async function reloadAll() {
    const status = document.getElementById("filtro-status")?.value || "todos";

    const qs = new URLSearchParams();
    if (status) qs.set("status", status);

    // 1) lista de serviços
    const data = await API.get(`/servicos?${qs.toString()}`);
    SERVICOS = Array.isArray(data) ? data : [];

    // 2) kpis
    const kpis = await API.get("/servicos/kpis");
    applyKPIs(kpis);

    fillCategoriasFromData(kpis, SERVICOS);
    render();
}

function applyKPIs(k) {
    const total = Number(k?.total || 0);
    const ativos = Number(k?.ativos || 0);
    const inativos = Number(k?.inativos || 0);
    const categorias = Array.isArray(k?.categorias) ? k.categorias : [];

    document.getElementById("kpi-total-servicos").textContent = String(total);
    document.getElementById("kpi-ativos").textContent = String(ativos);
    document.getElementById("kpi-inativos").textContent = String(inativos);

    const pct = total > 0 ? ((ativos / total) * 100).toFixed(1).replace(".", ",") + "% do total" : "—";
    document.getElementById("kpi-ativos-pct").textContent = pct;

    document.getElementById("kpi-total-categorias").textContent = `${categorias.length} categorias`;

    const mv = k?.mais_vendido || null;
    if (mv && mv.nome) {
        document.getElementById("kpi-mais-vendido-nome").textContent = mv.nome;
        document.getElementById("kpi-mais-vendido-qtde").textContent = `${mv.qtd} vezes este mês`;
    } else {
        document.getElementById("kpi-mais-vendido-nome").textContent = "—";
        document.getElementById("kpi-mais-vendido-qtde").textContent = "—";
    }
}

function fillCategoriasFromData(kpis, servicos) {
    const set = new Set();

    if (kpis && Array.isArray(kpis.categorias)) {
        kpis.categorias.forEach(c => {
            const v = (c.categoria || "").trim();
            if (v) set.add(v);
        });
    } else {
        (servicos || []).forEach(s => {
            const v = (s.categoria || "").trim();
            if (v) set.add(v);
        });
    }

    const filtro = document.getElementById("filtro-categoria");
    if (!filtro) return;

    const atual = filtro.value;
    filtro.innerHTML = `<option value="">Todas as Categorias</option>`;

    [...set].sort().forEach(cat => {
        const opt = document.createElement("option");
        opt.value = cat;
        opt.textContent = cat;
        filtro.appendChild(opt);
    });

    if ([...filtro.options].some(o => o.value === atual)) {
        filtro.value = atual;
    }
}

/* =========================
   Render table
========================= */
function render() {
    const termo = (document.getElementById("busca-servicos")?.value || "").trim().toLowerCase();
    const catFiltro = (document.getElementById("filtro-categoria")?.value || "").trim();

    const rows = (SERVICOS || []).filter(s => {
        const nome = (s.nome || "").toLowerCase();
        const desc = (s.descricao || "").toLowerCase();
        const okTermo = !termo || nome.includes(termo) || desc.includes(termo);
        const okCat = !catFiltro || (s.categoria || "") === catFiltro;
        return okTermo && okCat;
    });

    const tbody = document.getElementById("tbody-servicos");
    if (!tbody) return;

    tbody.innerHTML = "";

    rows.forEach(s => {
        const tr = document.createElement("tr");

        const cat = (s.categoria || "").trim();
        let catCls = "";
        const catLower = cat.toLowerCase();
        if (catLower.includes("combo")) catCls = "combo";
        else if (catLower.includes("barba")) catCls = "barba";

        const catBadge = cat
            ? `<span class="badge cat ${catCls}">${escapeHtml(cat)}</span>`
            : `<span class="badge neutral">—</span>`;

        const statusBadge = Number(s.ativo) === 1
            ? `<span class="badge success">Ativo</span>`
            : `<span class="badge danger">Inativo</span>`;

        tr.innerHTML = `
          <td><strong>${escapeHtml(s.nome)}</strong></td>
          <td class="muted">${escapeHtml(s.descricao || "—")}</td>
          <td>${catBadge}</td>
          <td>
            <div class="duracao-cell">
              <span class="clock">🕒</span>
              <span>${Number(s.duracao || 0)} min</span>
            </div>
          </td>
          <td><strong>${brl(s.preco)}</strong></td>
          <td>${statusBadge}</td>
          <td>
            <div class="actions">
              <button class="btn-kebab" type="button" title="Ações">⋮</button>
              <div class="menu">
                <button type="button" data-action="edit">Editar</button>
                <button type="button" data-action="toggle">${Number(s.ativo) === 1 ? "Desativar" : "Ativar"}</button>
                <button type="button" data-action="delete">Excluir</button>
              </div>
            </div>
          </td>
        `;

        const kebab = tr.querySelector(".btn-kebab");
        const menu = tr.querySelector(".menu");

        kebab.addEventListener("click", (e) => {
            e.stopPropagation();
            document.querySelectorAll(".menu.open").forEach(m => m.classList.remove("open"));
            menu.classList.toggle("open");
        });

        menu.addEventListener("click", (e) => {
            e.stopPropagation();
            const btn = e.target.closest("button[data-action]");
            if (!btn) return;

            const action = btn.dataset.action;
            menu.classList.remove("open");

            if (action === "edit") onEdit(s);
            if (action === "toggle") onToggle(s);
            if (action === "delete") onDelete(s);
        });

        tbody.appendChild(tr);
    });
}

/* =========================
   Actions
========================= */
function onEdit(s) {
    EDIT_ID = s.id;
    setModalTitle("Editar Serviço", "Atualize os dados do serviço.");
    fillForm(s);
    openModal("modal-servico");
}

function onToggle(s) {
    const novoAtivo = Number(s.ativo) === 1 ? 0 : 1;

    openConfirm(
        "Alterar status",
        `Deseja ${novoAtivo === 1 ? "ativar" : "desativar"} o serviço "${s.nome}"?`,
        async () => {
            await API.put(`/servicos/${s.id}/status`, { ativo: novoAtivo });
            await reloadAll();
        }
    );
}

function onDelete(s) {
    openConfirm(
        "Excluir serviço",
        `Deseja excluir o serviço "${s.nome}"? (Se já tiver histórico em agendamentos, o sistema vai bloquear.)`,
        async () => {
            await API.delete(`/servicos/${s.id}`);
            await reloadAll();
        }
    );
}

async function salvarServico() {
    const payload = readForm();

    if (!payload.nome) return showInfo("Nome é obrigatório.");
    if (!payload.duracao || payload.duracao <= 0) return showInfo("Duração inválida.");
    if (payload.preco < 0) return showInfo("Preço inválido.");

    if (EDIT_ID) {
        await API.put(`/servicos/${EDIT_ID}`, payload);
    } else {
        await API.post("/servicos", payload);
    }

    closeModal("modal-servico");
    await reloadAll();
}

/* =========================
   Form helpers
========================= */
function readForm() {
    return {
        nome: (document.getElementById("s-nome").value || "").trim(),
        descricao: (document.getElementById("s-descricao").value || "").trim() || null,
        categoria: (document.getElementById("s-categoria").value || "").trim() || null,
        duracao: Number(document.getElementById("s-duracao").value || 0),
        preco: Number(document.getElementById("s-preco").value || 0),
        ativo: Number(document.getElementById("s-ativo").value || 1),
    };
}

function fillForm(s) {
    document.getElementById("s-nome").value = s.nome || "";
    document.getElementById("s-descricao").value = s.descricao || "";
    document.getElementById("s-categoria").value = s.categoria || "";
    document.getElementById("s-duracao").value = (s.duracao ?? 30);
    document.getElementById("s-preco").value = (s.preco ?? 0);
    document.getElementById("s-ativo").value = String(s.ativo ?? 1);
}

function setModalTitle(t, st) {
    document.getElementById("titulo-modal-servico").textContent = t;
    document.getElementById("subtitulo-modal-servico").textContent = st;
}