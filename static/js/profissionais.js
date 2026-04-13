let profissionaisBase = [];
let listaAtual = [];
let agHojeBase = [];
let bloqueiosHojeBase = [];

document.addEventListener("DOMContentLoaded", () => {
    initUI();
    carregarTudo().catch(e => showInfo(e.message, "Erro"));
});

/* =========================
   Utils
========================= */
function norm(s) { return String(s || "").trim().toLowerCase(); }

function escapeHtml(str) {
    return String(str)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

function todayISO() {
    const d = new Date();
    const yyyy = d.getFullYear();
    const mm = String(d.getMonth() + 1).padStart(2, "0");
    const dd = String(d.getDate()).padStart(2, "0");
    return `${yyyy}-${mm}-${dd}`;
}

function diaSemanaKeyHoje() {
    const dt = new Date();
    const map = ["dom", "seg", "ter", "qua", "qui", "sex", "sab"];
    return map[dt.getDay()];
}

function parseDiasTrabalho(raw) {
    return String(raw || "")
        .split(",")
        .map(s => s.trim().toLowerCase())
        .filter(Boolean);
}

function isDiaInteiro(b) {
    return b && (b.dia_inteiro === 1 || b.dia_inteiro === true || String(b.dia_inteiro) === "1");
}

/* =========================
   Load
========================= */
async function carregarTudo() {
    const profs = await API.get("/profissionais");
    profissionaisBase = Array.isArray(profs) ? profs : [];

    try {
        const ag = await API.get(`/agendamentos?data=${encodeURIComponent(todayISO())}`);
        agHojeBase = Array.isArray(ag) ? ag : [];
    } catch {
        agHojeBase = [];
    }

    try {
        const bl = await API.get(`/bloqueios?data=${encodeURIComponent(todayISO())}`);
        bloqueiosHojeBase = Array.isArray(bl) ? bl : [];
    } catch {
        bloqueiosHojeBase = [];
    }

    aplicarFiltros();
}

function countAgHojePorProf(profissional_id) {
    return agHojeBase.filter(a => String(a.profissional_id) === String(profissional_id)).length;
}

function getBloqueioDiaInteiroHoje(profissional_id) {
    return bloqueiosHojeBase.find(b =>
        String(b.profissional_id) === String(profissional_id) && isDiaInteiro(b)
    ) || null;
}

/* =========================
   Filters + KPIs
========================= */
function aplicarFiltros() {
    const busca = norm(document.getElementById("busca-profissionais")?.value);
    const st = document.getElementById("filtro-status")?.value || "";
    const hojeKey = diaSemanaKeyHoje();

    let lista = [...profissionaisBase].map(p => {
        const b = getBloqueioDiaInteiroHoje(p.id);
        const ativo = (Number(p.ativo ?? 1) === 1);
        const dias = parseDiasTrabalho(p.dias_trabalho);
        const trabalhaHoje = dias.length ? dias.includes(hojeKey) : true;

        return {
            ...p,
            __agHoje: countAgHojePorProf(p.id),
            __status: ativo ? "ativo" : "inativo",
            __trabalhaHoje: trabalhaHoje,
            __emFolgaHoje: !!b,
            __bloqueioHojeId: b ? b.id : null
        };
    });

    if (busca) {
        lista = lista.filter(p => {
            const n = norm(p.nome);
            const t = norm(p.telefone);
            return n.includes(busca) || t.includes(busca);
        });
    }

    if (st) {
        lista = lista.filter(p => p.__status === st);
    }

    listaAtual = lista;
    renderKPIs(listaAtual);
    renderTabela(listaAtual);
}

function renderKPIs(lista) {
    const total = lista.length;

    // "Ativos Hoje" = ativo + trabalha hoje + não está em folga hoje
    const ativosHoje = lista.filter(p => p.__status === "ativo" && p.__trabalhaHoje && !p.__emFolgaHoje).length;
    const inativos = lista.filter(p => p.__status === "inativo").length;

    const agHoje = lista.reduce((s, p) => s + Number(p.__agHoje || 0), 0);

    setText("kpi-total", total);
    setText("kpi-ativos-hoje", ativosHoje);
    setText("kpi-inativos", inativos);
    setText("kpi-ag-hoje", agHoje);

    const pct = total ? ((ativosHoje / total) * 100).toFixed(1).replace(".", ",") : "0,0";
    setText("kpi-ativos-pct", total ? `${pct}% do total` : "—");
}

function setText(id, val) {
    const el = document.getElementById(id);
    if (el) el.textContent = String(val);
}

/* =========================
   Table + Row menu
========================= */
let rowMenuEl = null;

function renderTabela(lista) {
    const tbody = document.getElementById("tbody-profissionais");
    if (!tbody) return;

    tbody.innerHTML = "";

    lista.forEach(p => {
        const tr = document.createElement("tr");

        const diasTxt = formatDias(p.dias_trabalho);
        const horarioTxt = `${(p.hora_inicio || "—")} - ${(p.hora_fim || "—")}`;

        tr.innerHTML = `
          <td><strong>${escapeHtml(p.nome || "")}</strong></td>
          <td><div class="contato">📞 ${escapeHtml(p.telefone || "—")}</div></td>
          <td>${escapeHtml(diasTxt)}</td>
          <td>${escapeHtml(horarioTxt)}</td>
          <td><span class="pill count">${Number(p.__agHoje || 0)}</span></td>
          <td>${badgeStatus(p.__status, p.__emFolgaHoje)}</td>
          <td class="td-actions">
            <button type="button" class="row-menu-btn" data-action="row-menu" data-id="${p.id}">⋮</button>
          </td>
        `;
        tbody.appendChild(tr);
    });
}

function badgeStatus(st, emFolga) {
    if (emFolga) return `<span class="pill folga">Folga (hoje)</span>`;
    const s = norm(st);
    if (s === "ativo") return `<span class="pill ativo">Ativo</span>`;
    return `<span class="pill inativo">Inativo</span>`;
}

function formatDias(raw) {
    const map = { seg: "Seg", ter: "Ter", qua: "Qua", qui: "Qui", sex: "Sex", sab: "Sáb", dom: "Dom" };
    const arr = String(raw || "").split(",").map(x => x.trim()).filter(Boolean);
    if (!arr.length) return "—";
    return arr.map(d => map[d] || d).join(" - ");
}

function abrirRowMenu(anchorBtn, id) {
    fecharRowMenu();
    const p = listaAtual.find(x => String(x.id) === String(id));
    if (!p) return;

    rowMenuEl = document.createElement("div");
    rowMenuEl.className = "row-menu";

    const folgaLabel = p.__emFolgaHoje
        ? "🗑 <span>Remover folga (hoje)</span>"
        : "📌 <span>Definir folga</span>";

    const folgaAct = p.__emFolgaHoje ? "remover_folga" : "folga";

    rowMenuEl.innerHTML = `
        <button type="button" class="row-opt" data-act="editar" data-id="${id}">✎ <span>Editar</span></button>
        <button type="button" class="row-opt" data-act="comissao" data-id="${id}">％ <span>Definir comissão</span></button>
        <button type="button" class="row-opt" data-act="${folgaAct}" data-id="${id}">${folgaLabel}</button>
        <button type="button" class="row-opt danger" data-act="toggle" data-id="${id}">
          ${p.__status === "ativo" ? "⛔" : "✅"} <span>${p.__status === "ativo" ? "Desativar" : "Ativar"}</span>
        </button>
    `;

    document.body.appendChild(rowMenuEl);

    const r = anchorBtn.getBoundingClientRect();
    const menuW = rowMenuEl.offsetWidth;
    const menuH = rowMenuEl.offsetHeight;

    let top = r.bottom + 8;
    let left = r.left;

    if (left + menuW > window.innerWidth - 12) left = window.innerWidth - menuW - 12;
    if (top + menuH > window.innerHeight - 12) top = r.top - menuH - 8;

    top = Math.max(12, top);
    left = Math.max(12, left);

    rowMenuEl.style.top = `${top}px`;
    rowMenuEl.style.left = `${left}px`;

    rowMenuEl.addEventListener("click", async (e) => {
        const opt = e.target.closest(".row-opt");
        if (!opt) return;

        const act = opt.dataset.act;
        const pid = opt.dataset.id;

        if (act === "editar") abrirModalProf(p);
        if (act === "comissao") abrirModalComissao(p);
        if (act === "folga") abrirModalFolga(p);
        if (act === "toggle") await toggleStatus(pid, p.__status);
        if (act === "remover_folga") await removerFolgaHoje(p);

        fecharRowMenu();
    });
}

function fecharRowMenu() {
    if (rowMenuEl) {
        rowMenuEl.remove();
        rowMenuEl = null;
    }
}

/* =========================
   Modal Profissional
========================= */
const modalProf = () => document.getElementById("modal-profissional");
const formProf = () => document.getElementById("form-prof");

function abrirModalProf(prof = null) {
    const m = modalProf();
    if (!m) return;

    const isEdit = !!prof;
    document.getElementById("titulo-modal-prof").textContent = isEdit ? "Editar Profissional" : "Novo Profissional";
    document.getElementById("btn-salvar-prof").textContent = isEdit ? "Salvar" : "Adicionar";

    if (isEdit) {
        m.dataset.editId = String(prof.id);
        document.getElementById("p-nome").value = prof.nome || "";
        document.getElementById("p-telefone").value = prof.telefone || "";
        document.getElementById("p-inicio").value = (prof.hora_inicio || "09:00");
        document.getElementById("p-fim").value = (prof.hora_fim || "19:00");
        marcarDias(prof.dias_trabalho);
    } else {
        delete m.dataset.editId;
        formProf()?.reset();
        document.getElementById("p-inicio").value = "09:00";
        document.getElementById("p-fim").value = "19:00";
        marcarDias("seg,ter,qua,qui,sex,sab");
    }

    m.classList.add("is-open");
}

function fecharModalProf() {
    modalProf()?.classList.remove("is-open");
}

function marcarDias(raw) {
    const set = new Set(String(raw || "").split(",").map(x => x.trim()).filter(Boolean));
    document.querySelectorAll('#dias-grid input[type="checkbox"]').forEach(chk => {
        chk.checked = set.has(chk.value);
    });
}

function coletarDias() {
    const dias = [];
    document.querySelectorAll('#dias-grid input[type="checkbox"]').forEach(chk => {
        if (chk.checked) dias.push(chk.value);
    });
    return dias.join(",");
}

async function salvarProf(e) {
    e.preventDefault();

    const m = modalProf();
    const editId = m?.dataset.editId || null;

    const nome = document.getElementById("p-nome").value.trim();
    const telefone = document.getElementById("p-telefone").value.trim();
    const dias_trabalho = coletarDias();
    const hora_inicio = document.getElementById("p-inicio").value;
    const hora_fim = document.getElementById("p-fim").value;

    if (!nome) return showInfo("Informe o nome.");
    if (!telefone) return showInfo("Informe o telefone.");
    if (!dias_trabalho) return showInfo("Selecione os dias de trabalho.");
    if (!hora_inicio || !hora_fim) return showInfo("Informe o horário.");

    const payload = { nome, telefone, dias_trabalho, hora_inicio, hora_fim };

    try {
        if (editId) await API.put(`/profissionais/${editId}`, payload);
        else await API.post("/profissionais", payload);

        fecharModalProf();
        await carregarTudo();
    } catch (err) {
        showInfo(err.message, "Erro");
    }
}

/* =========================
   Modal Folga
========================= */
const modalFolga = () => document.getElementById("modal-folga");
const formFolga = () => document.getElementById("form-folga");

function abrirModalFolga(prof) {
    const m = modalFolga();
    if (!m) return;

    m.dataset.profId = String(prof.id);
    document.getElementById("folga-sub").textContent = `${prof.nome} • bloqueio dia inteiro`;

    document.getElementById("f-data").value = todayISO();
    document.getElementById("f-motivo").value = "";

    m.classList.add("is-open");
}

function fecharModalFolga() {
    modalFolga()?.classList.remove("is-open");
}

async function salvarFolga(e) {
    e.preventDefault();

    const m = modalFolga();
    const profissional_id = m?.dataset.profId;
    const data = document.getElementById("f-data").value;
    const motivo = document.getElementById("f-motivo").value.trim();

    if (!profissional_id) return;
    if (!data) return showInfo("Informe a data.");

    const payload = {
        profissional_id: Number(profissional_id),
        data,
        dia_inteiro: 1,
        motivo
    };

    try {
        await API.post("/bloqueios", payload);
        fecharModalFolga();
        await carregarTudo();
        showInfo("Folga registrada. Nesse dia não cairá agenda para o profissional.", "Sucesso");
    } catch (err) {
        showInfo(err.message, "Erro");
    }
}

/* =========================
   Modal Comissão
========================= */
const modalComissao = () => document.getElementById("modal-comissao");
const formComissao = () => document.getElementById("form-comissao");

function abrirModalComissao(prof) {
    const m = modalComissao();
    if (!m) return;

    m.dataset.profId = String(prof.id);
    document.getElementById("comissao-sub").textContent = `${prof.nome} • comissão fixa percentual`;

    const tipo = (prof.tipo_comissao || "percentual").toString().toLowerCase();
    const valorAtual = Number(prof.valor_comissao || 0);

    document.getElementById("c-valor").value =
        (tipo === "percentual" && !Number.isNaN(valorAtual)) ? String(valorAtual) : "";

    m.classList.add("is-open");
    m.setAttribute("aria-hidden", "false");
}

function fecharModalComissao() {
    const m = modalComissao();
    if (!m) return;
    m.classList.remove("is-open");
    m.setAttribute("aria-hidden", "true");
}

async function salvarComissao(e) {
    e.preventDefault();

    const m = modalComissao();
    const profissional_id = m?.dataset.profId;
    if (!profissional_id) return;

    const raw = (document.getElementById("c-valor").value || "").trim();
    if (!raw) return showInfo("Informe a comissão (%).");

    const valor = Number(raw.replace(",", "."));
    if (Number.isNaN(valor)) return showInfo("Comissão inválida.");
    if (valor < 0) return showInfo("A comissão não pode ser negativa.");
    if (valor > 100) return showInfo("O percentual não pode ser maior que 100.");

    try {
        await API.put(`/profissionais/${profissional_id}/comissao`, {
            tipo_comissao: "percentual",
            valor_comissao: valor
        });

        fecharModalComissao();
        await carregarTudo();
        showInfo("Comissão atualizada com sucesso.", "Sucesso");
    } catch (err) {
        showInfo(err.message, "Erro");
    }
}

/* =========================
   Status (ativar/desativar)
========================= */
async function toggleStatus(id, statusAtual) {
    const novoAtivo = (statusAtual === "inativo") ? 1 : 0;

    try {
        await API.put(`/profissionais/${id}/status`, { ativo: novoAtivo });
        await carregarTudo();
    } catch (err) {
        showInfo(err.message, "Erro");
    }
}

/* =========================
   Modal Info + Confirm
========================= */
const modalInfo = () => document.getElementById("modal-info");
const modalConfirm = () => document.getElementById("modal-confirm");

function showInfo(msg, title = "Aviso") {
    const m = modalInfo();
    if (!m) return;

    document.getElementById("info-title").textContent = title;
    document.getElementById("info-msg").textContent = msg;

    m.classList.add("is-open");
}

function closeInfo() {
    modalInfo()?.classList.remove("is-open");
}

function confirmModal(message, title = "Confirmar ação") {
    return new Promise((resolve) => {
        const overlay = modalConfirm();
        const msg = document.getElementById("confirm-msg");
        const ttl = document.getElementById("confirm-title");
        const btnSim = document.getElementById("btn-confirm-sim");
        const btnNao = document.getElementById("btn-confirm-nao");
        const btnX = document.getElementById("btn-fechar-confirm");

        if (!overlay || !msg || !ttl || !btnSim || !btnNao || !btnX) {
            resolve(false);
            return;
        }

        ttl.textContent = title;
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

        overlay.onclick = (e) => { if (e.target === overlay) fechar(false); };
        document.onkeydown = (e) => { if (e.key === "Escape") fechar(false); };

        overlay.classList.add("is-open");
        overlay.setAttribute("aria-hidden", "false");
    });
}

/* =========================
   Remover folga
========================= */
async function removerFolgaHoje(prof) {
    if (!prof.__bloqueioHojeId) return;

    const ok = await confirmModal(`Remover a folga de hoje de ${prof.nome}?`);
    if (!ok) return;

    try {
        await API.delete(`/bloqueios/${prof.__bloqueioHojeId}`);
        await carregarTudo();
        showInfo("Folga removida com sucesso.", "Sucesso");
    } catch (err) {
        showInfo(err.message, "Erro");
    }
}

/* =========================
   UI init
========================= */
function initUI() {
    document.getElementById("busca-profissionais")?.addEventListener("input", debounce(aplicarFiltros, 150));
    document.getElementById("filtro-status")?.addEventListener("change", aplicarFiltros);

    document.getElementById("btn-novo-profissional")?.addEventListener("click", () => abrirModalProf());

    // modal prof
    document.getElementById("btn-fechar-prof")?.addEventListener("click", fecharModalProf);
    document.getElementById("btn-cancelar-prof")?.addEventListener("click", fecharModalProf);
    modalProf()?.addEventListener("click", (e) => { if (e.target === modalProf()) fecharModalProf(); });
    formProf()?.addEventListener("submit", salvarProf);

    // modal folga
    document.getElementById("btn-fechar-folga")?.addEventListener("click", fecharModalFolga);
    document.getElementById("btn-cancelar-folga")?.addEventListener("click", fecharModalFolga);
    modalFolga()?.addEventListener("click", (e) => { if (e.target === modalFolga()) fecharModalFolga(); });
    formFolga()?.addEventListener("submit", salvarFolga);

    // modal comissão
    document.getElementById("btn-fechar-comissao")?.addEventListener("click", fecharModalComissao);
    document.getElementById("btn-cancelar-comissao")?.addEventListener("click", fecharModalComissao);
    modalComissao()?.addEventListener("click", (e) => { if (e.target === modalComissao()) fecharModalComissao(); });
    formComissao()?.addEventListener("submit", salvarComissao);

    // modal info
    document.getElementById("btn-fechar-info")?.addEventListener("click", closeInfo);
    document.getElementById("btn-info-ok")?.addEventListener("click", closeInfo);
    modalInfo()?.addEventListener("click", (e) => { if (e.target === modalInfo()) closeInfo(); });

    // modal confirm
    modalConfirm()?.addEventListener("click", (e) => { if (e.target === modalConfirm()) modalConfirm().classList.remove("is-open"); });

    // menu ⋮
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
            fecharModalProf();
            fecharModalFolga();
            fecharModalComissao();
            closeInfo();
            modalConfirm()?.classList.remove("is-open");
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