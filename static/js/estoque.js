// estoque.js — full file
//
// Main responsibilities:
// 1) Load products from backend
// 2) Local filtering (search/category/status)
// 3) KPIs + table rendering
// 4) Row menu ⋮ actions (edit / stock in / stock out)
// 5) Modals: product create/edit + movement in/out
//
// Backend endpoints used here:
// - GET  /produtos?ativos=1
// - POST /produtos
// - PUT  /produtos/<id>
// - POST /produtos/<id>/entrada
// - POST /produtos/<id>/saida

let produtosBase = [];
let listaAtual = [];

document.addEventListener("DOMContentLoaded", () => {
    initUI();
    carregarProdutos().catch(e => alert(e.message));
});

/* =========================
   UTILITIES
========================= */
function brl(n) {
    return `R$ ${Number(n || 0).toFixed(2).replace(".", ",")}`;
}

function norm(s) {
    return String(s || "").trim().toLowerCase();
}

function calcStatus(p) {
    const atual = Number(p.estoque_atual || 0);
    const min = Number(p.estoque_minimo || 0);

    if (atual <= 0) return "critico";

    const half = Math.max(1, Math.floor(min / 2));
    if (min > 0 && atual <= half) return "critico";

    if (min > 0 && atual <= min) return "baixo";

    return "normal";
}

function valorEstoque(p) {
    return Number(p.preco_custo || 0) * Number(p.estoque_atual || 0);
}

function setText(id, val) {
    const el = document.getElementById(id);
    if (el) el.textContent = String(val);
}

function escapeHtml(str) {
    return String(str)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

/* =========================
   DATA LOADING
========================= */
async function carregarProdutos() {
    const data = await API.get("/produtos?ativos=1");
    produtosBase = Array.isArray(data) ? data : [];

    popularCategorias(produtosBase);
    aplicarFiltros();
}

function popularCategorias(lista) {
    const sel = document.getElementById("filtro-categoria");
    if (!sel) return;

    const cats = [...new Set(lista.map(p => (p.categoria || "").trim()).filter(Boolean))].sort();
    sel.innerHTML = `<option value="">Todas as Categorias</option>`;

    cats.forEach(c => {
        const opt = document.createElement("option");
        opt.value = c;
        opt.textContent = c;
        sel.appendChild(opt);
    });
}

/* =========================
   FILTERS + KPIs
========================= */
function aplicarFiltros() {
    const busca = norm(document.getElementById("busca-produtos")?.value);
    const cat = document.getElementById("filtro-categoria")?.value || "";
    const st = document.getElementById("filtro-status")?.value || "";

    let lista = [...produtosBase];

    if (busca) {
        lista = lista.filter(p => {
            const a = norm(p.nome);
            const b = norm(p.marca);
            const c = norm(p.categoria);
            return a.includes(busca) || b.includes(busca) || c.includes(busca);
        });
    }

    if (cat) {
        lista = lista.filter(p => (p.categoria || "") === cat);
    }

    if (st) {
        lista = lista.filter(p => calcStatus(p) === st);
    }

    listaAtual = lista;

    renderKPIs(listaAtual);
    renderTabela(listaAtual);
}

function renderKPIs(lista) {
    const totalProdutos = lista.length;

    const categorias = new Set(lista.map(p => (p.categoria || "").trim()).filter(Boolean));
    const totalCategorias = categorias.size;

    const valorTotal = lista.reduce((s, p) => s + valorEstoque(p), 0);

    const baixos = lista.filter(p => calcStatus(p) === "baixo").length;
    const criticos = lista.filter(p => calcStatus(p) === "critico").length;

    setText("kpi-total-produtos", totalProdutos);
    setText("kpi-total-categorias", totalCategorias);
    setText("kpi-valor-total", brl(valorTotal));
    setText("kpi-estoque-baixo", baixos);
    setText("kpi-estoque-critico", criticos);

    const alert = document.getElementById("alert-critico");
    const msg = document.getElementById("alert-critico-msg");

    if (alert) {
        if (criticos > 0) {
            alert.hidden = false;
            if (msg) msg.textContent = `${criticos} produto(s) estão com estoque crítico e precisam ser repostos urgentemente.`;
        } else {
            alert.hidden = true;
        }
    }
}

/* =========================
   TABLE RENDER
========================= */
function renderTabela(lista) {
    const tbody = document.getElementById("tbody-produtos");
    if (!tbody) return;

    tbody.innerHTML = "";

    lista.forEach(p => {
        const st = calcStatus(p);

        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td>${escapeHtml(p.nome || "")}</td>
            <td>${escapeHtml(p.categoria || "—")}</td>
            <td>${escapeHtml(p.marca || "—")}</td>
            <td>${Number(p.estoque_atual || 0)} <span class="muted">un</span></td>
            <td>${Number(p.estoque_minimo || 0)} <span class="muted">un</span></td>
            <td>${brl(p.preco_custo || 0)}</td>
            <td><strong style="color:#1b7f3a">${brl(p.preco_venda || 0)}</strong></td>
            <td>${badge(st)}</td>
            <td class="td-actions">
                <button type="button" class="row-menu-btn" data-action="row-menu" data-id="${p.id}">⋮</button>
            </td>
        `;

        tbody.appendChild(tr);
    });
}

function badge(st) {
    const map = {
        normal: { label: "Normal", cls: "normal" },
        baixo: { label: "Baixo", cls: "baixo" },
        critico: { label: "Crítico", cls: "critico" },
    };
    const b = map[st] || map.normal;
    return `<span class="pill ${b.cls}">${b.label}</span>`;
}

/* =========================
   UI INIT
========================= */
let rowMenuEl = null;

function initUI() {
    document.getElementById("busca-produtos")?.addEventListener("input", debounce(aplicarFiltros, 150));
    document.getElementById("filtro-categoria")?.addEventListener("change", aplicarFiltros);
    document.getElementById("filtro-status")?.addEventListener("change", aplicarFiltros);

    document.getElementById("btn-ver-criticos")?.addEventListener("click", () => {
        const sel = document.getElementById("filtro-status");
        if (sel) sel.value = "critico";
        aplicarFiltros();
    });

    document.getElementById("btn-novo-produto")?.addEventListener("click", () => abrirModalProduto());
    document.getElementById("btn-novo-produto-2")?.addEventListener("click", () => abrirModalProduto());

    initModalProduto();
    initModalMov();

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
            fecharModalProduto();
            fecharModalMov();
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

/* =========================
   ROW MENU
========================= */
function abrirRowMenu(anchorBtn, id) {
    fecharRowMenu();

    const p = produtosBase.find(x => String(x.id) === String(id));
    if (!p) return;

    const rect = anchorBtn.getBoundingClientRect();

    rowMenuEl = document.createElement("div");
    rowMenuEl.className = "row-menu";
    rowMenuEl.innerHTML = `
        <button type="button" class="row-opt" data-act="editar" data-id="${id}">✎ <span>Editar</span></button>
        <button type="button" class="row-opt" data-act="entrada" data-id="${id}">＋ <span>Entrada de estoque</span></button>
        <button type="button" class="row-opt" data-act="saida" data-id="${id}">－ <span>Saída de estoque</span></button>
    `;

    document.body.appendChild(rowMenuEl);

    rowMenuEl.style.position = "fixed";
    rowMenuEl.style.zIndex = "9999";

    positionFloatingMenu(rect, rowMenuEl);

    rowMenuEl.addEventListener("click", async (e) => {
        const opt = e.target.closest(".row-opt");
        if (!opt) return;

        const act = opt.dataset.act;
        const pid = opt.dataset.id;

        if (act === "editar") abrirModalProduto(p);
        if (act === "entrada") abrirModalMov("entrada", p);
        if (act === "saida") abrirModalMov("saida", p);

        fecharRowMenu();
    });
}

function fecharRowMenu() {
    if (rowMenuEl) {
        rowMenuEl.remove();
        rowMenuEl = null;
    }
}

function positionFloatingMenu(anchorRect, menuEl) {
    const margin = 12;

    const menuW = menuEl.offsetWidth;
    const menuH = menuEl.offsetHeight;

    let left = anchorRect.left;
    left = Math.min(Math.max(margin, left), window.innerWidth - menuW - margin);

    let top = anchorRect.bottom + 8;
    if (top + menuH > window.innerHeight - margin) {
        top = anchorRect.top - menuH - 8;
    }

    top = Math.min(Math.max(margin, top), window.innerHeight - menuH - margin);

    menuEl.style.left = `${left}px`;
    menuEl.style.top = `${top}px`;
}

/* =========================
   MODAL: PRODUCT
========================= */
const modalProduto = () => document.getElementById("modal-produto");
const formProduto = () => document.getElementById("form-produto");

function initModalProduto() {
    document.getElementById("btn-fechar-produto")?.addEventListener("click", fecharModalProduto);
    document.getElementById("btn-cancelar-produto")?.addEventListener("click", fecharModalProduto);

    modalProduto()?.addEventListener("click", (e) => {
        if (e.target === modalProduto()) fecharModalProduto();
    });

    formProduto()?.addEventListener("submit", async (e) => {
        e.preventDefault();

        const mp = modalProduto();
        const editId = mp?.dataset.editId || null;

        const payload = {
            nome: document.getElementById("p-nome").value.trim(),
            categoria: document.getElementById("p-categoria").value.trim(),
            marca: document.getElementById("p-marca").value.trim(),
            estoque_inicial: Number(document.getElementById("p-estoque-inicial").value || 0),
            estoque_minimo: Number(document.getElementById("p-estoque-minimo").value || 0),
            preco_custo: Number(document.getElementById("p-preco-custo").value || 0),
            preco_venda: Number(document.getElementById("p-preco-venda").value || 0),
        };

        if (!payload.nome) {
            alert("Informe o nome do produto.");
            return;
        }

        if (editId) {
            delete payload.estoque_inicial;
            await API.put(`/produtos/${editId}`, payload);
        } else {
            await API.post("/produtos", payload);
        }

        fecharModalProduto();
        await carregarProdutos();
    });
}

function abrirModalProduto(produto = null) {
    const mp = modalProduto();
    const fp = formProduto();
    if (!mp || !fp) return;

    const isEdit = !!produto;

    document.getElementById("titulo-modal-produto").textContent = isEdit ? "Editar Produto" : "Novo Produto";
    document.getElementById("btn-salvar-produto").textContent = isEdit ? "Salvar Alterações" : "Adicionar Produto";

    const elEstoqueInicial = document.getElementById("p-estoque-inicial");

    if (isEdit) {
        mp.dataset.editId = String(produto.id);

        document.getElementById("p-nome").value = produto.nome || "";
        document.getElementById("p-categoria").value = produto.categoria || "";
        document.getElementById("p-marca").value = produto.marca || "";
        document.getElementById("p-estoque-inicial").value = Number(produto.estoque_atual || 0);
        document.getElementById("p-estoque-minimo").value = Number(produto.estoque_minimo || 0);
        document.getElementById("p-preco-custo").value = Number(produto.preco_custo || 0);
        document.getElementById("p-preco-venda").value = Number(produto.preco_venda || 0);

        if (elEstoqueInicial) elEstoqueInicial.disabled = true;
    } else {
        delete mp.dataset.editId;
        fp.reset();

        if (elEstoqueInicial) elEstoqueInicial.disabled = false;

        document.getElementById("p-estoque-inicial").value = 0;
        document.getElementById("p-estoque-minimo").value = 0;
        document.getElementById("p-preco-custo").value = 0;
        document.getElementById("p-preco-venda").value = 0;
    }

    mp.classList.add("is-open");
}

function fecharModalProduto() {
    const mp = modalProduto();
    if (!mp) return;
    mp.classList.remove("is-open");
}

/* =========================
   MODAL: MOVEMENT
========================= */
const modalMov = () => document.getElementById("modal-mov");
const formMov = () => document.getElementById("form-mov");

function initModalMov() {
    document.getElementById("btn-fechar-mov")?.addEventListener("click", fecharModalMov);
    document.getElementById("btn-cancelar-mov")?.addEventListener("click", fecharModalMov);

    modalMov()?.addEventListener("click", (e) => {
        if (e.target === modalMov()) fecharModalMov();
    });

    document.getElementById("m-quantidade")?.addEventListener("input", atualizarResumoMov);
    document.getElementById("m-forma-pagamento")?.addEventListener("change", atualizarResumoMov);

    formMov()?.addEventListener("submit", async (e) => {
        e.preventDefault();

        const mm = modalMov();
        const tipo = mm?.dataset.tipo;
        const pid = mm?.dataset.produtoId;

        const quantidade = Number(document.getElementById("m-quantidade").value || 0);
        const descricao = document.getElementById("m-descricao").value.trim();
        const forma_pagamento = document.getElementById("m-forma-pagamento").value;

        if (!pid || !tipo) return;

        if (quantidade <= 0) {
            alert("Informe uma quantidade válida.");
            return;
        }

        if (!forma_pagamento) {
            alert("Selecione a forma de pagamento.");
            return;
        }

        const payload = { quantidade, descricao, forma_pagamento };

        if (tipo === "entrada") {
            await API.post(`/produtos/${pid}/entrada`, payload);
        } else {
            await API.post(`/produtos/${pid}/saida`, payload);
        }

        fecharModalMov();
        await carregarProdutos();
    });
}

function abrirModalMov(tipo, produto) {
    const mm = modalMov();
    const fm = formMov();
    if (!mm || !fm) return;

    mm.dataset.tipo = tipo;
    mm.dataset.produtoId = String(produto.id);
    mm.dataset.precoBase = String(
        tipo === "entrada"
            ? Number(produto.preco_custo || 0)
            : Number(produto.preco_venda || 0)
    );

    const titulo = document.getElementById("titulo-modal-mov");
    const subt = document.getElementById("subtitulo-modal-mov");
    const btn = document.getElementById("btn-confirmar-mov");
    const lblValor = document.getElementById("m-label-valor");
    const lblForma = document.getElementById("m-label-forma");

    if (titulo) titulo.textContent = (tipo === "entrada") ? "Entrada de Estoque" : "Saída de Estoque";
    if (subt) subt.textContent = `${produto.nome} • Estoque atual: ${Number(produto.estoque_atual || 0)} un`;
    if (btn) btn.textContent = (tipo === "entrada") ? "Confirmar entrada" : "Confirmar saída";
    if (lblValor) lblValor.textContent = (tipo === "entrada") ? "Despesa prevista" : "Entrada prevista";
    if (lblForma) lblForma.textContent = (tipo === "entrada") ? "Forma de pagamento" : "Forma de recebimento";

    fm.reset();
    document.getElementById("m-quantidade").value = "";
    document.getElementById("m-descricao").value = "";
    document.getElementById("m-forma-pagamento").value = "dinheiro";
    document.getElementById("m-valor-previsto").value = brl(0);

    atualizarResumoMov();
    mm.classList.add("is-open");
}

function atualizarResumoMov() {
    const mm = modalMov();
    if (!mm) return;

    const quantidade = Number(document.getElementById("m-quantidade")?.value || 0);
    const precoBase = Number(mm.dataset.precoBase || 0);
    const valorPrevisto = quantidade > 0 ? quantidade * precoBase : 0;

    const campo = document.getElementById("m-valor-previsto");
    if (campo) {
        campo.value = brl(valorPrevisto);
    }
}

function fecharModalMov() {
    const mm = modalMov();
    if (!mm) return;
    mm.classList.remove("is-open");
}