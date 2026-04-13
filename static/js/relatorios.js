document.addEventListener("DOMContentLoaded", () => {
    initRelatorios().catch((err) => {
        console.error(err);
        alert(err.message || "Erro ao iniciar relatórios.");
    });
});

function brl(n) {
    return `R$ ${Number(n || 0).toFixed(2).replace(".", ",")}`;
}

function ymToLabel(ym) {
    if (!ym || !ym.includes("-")) return ym || "";
    const [y, m] = ym.split("-");
    const meses = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"];
    return `${meses[Number(m) - 1] || m}/${y}`;
}

function pick(obj, key, fallback) {
    if (!obj || typeof obj !== "object") return fallback;
    return key in obj ? obj[key] : fallback;
}

function notifyErro(message) {
    try {
        if (window.UI?.toast) {
            window.UI.toast(message, "error");
            return;
        }
        if (window.UI?.notify) {
            window.UI.notify(message, "error");
            return;
        }
    } catch (_) { }
    alert(message);
}

async function initRelatorios() {
    const selPeriodo = document.getElementById("rel-periodo");
    const selProf = document.getElementById("rel-profissional");
    const btnAtualizar = document.getElementById("rel-atualizar");
    const btnExport = document.getElementById("rel-export-csv");

    if (!selPeriodo || !selProf || !btnAtualizar || !btnExport) {
        throw new Error("IDs da tela de relatórios não encontrados.");
    }

    await carregarProfissionaisRelatorio();

    const recarregar = () => carregarResumo().catch((e) => {
        console.error(e);
        notifyErro(e.message || "Erro ao carregar relatório.");
    });

    btnAtualizar.addEventListener("click", recarregar);
    selPeriodo.addEventListener("change", recarregar);
    selProf.addEventListener("change", recarregar);

    btnExport.addEventListener("click", () => {
        const periodo = selPeriodo.value || "este_mes";
        const prof = selProf.value || "todos";

        const url =
            `/relatorios/export/pdf` +
            `?periodo=${encodeURIComponent(periodo)}` +
            `&profissional_id=${encodeURIComponent(prof)}`;

        window.open(url, "_blank");
    });

    await carregarResumo();
}

async function carregarProfissionaisRelatorio() {
    const selProf = document.getElementById("rel-profissional");
    if (!selProf) return;

    const profs = await API.get("/relatorios/profissionais");

    selProf.innerHTML = `<option value="todos">Todos</option>`;

    (Array.isArray(profs) ? profs : []).forEach((p) => {
        const opt = document.createElement("option");
        opt.value = String(p.id);
        opt.textContent = p.nome + (Number(p.ativo) === 1 ? "" : " (inativo)");
        selProf.appendChild(opt);
    });
}

async function carregarResumo() {
    const periodo = document.getElementById("rel-periodo")?.value || "este_mes";
    const prof = document.getElementById("rel-profissional")?.value || "todos";

    const data = await API.get(
        `/relatorios/resumo?periodo=${encodeURIComponent(periodo)}&profissional_id=${encodeURIComponent(prof)}`
    );

    const kpis = pick(data, "kpis", {});

    const elFat = document.getElementById("kpi-fat");
    const elClientes = document.getElementById("kpi-clientes");
    const elAtend = document.getElementById("kpi-atend");
    const elSaldo = document.getElementById("kpi-saldo");
    const elSaidas = document.getElementById("kpi-saidas");

    if (elFat) elFat.textContent = brl(pick(kpis, "entradas", 0));
    if (elClientes) elClientes.textContent = String(pick(kpis, "clientes_no_periodo", 0));
    if (elAtend) elAtend.textContent = String(pick(kpis, "atendimentos", 0));
    if (elSaldo) elSaldo.textContent = brl(pick(kpis, "saldo", 0));
    if (elSaidas) elSaidas.textContent = `Saídas: ${brl(pick(kpis, "saidas", 0))}`;

    const periodoLabel = pick(pick(data, "periodo", {}), "label", "—");
    const elPeriodoLabel = document.getElementById("kpi-periodo-label");
    const elTopPeriodo = document.getElementById("top-serv-periodo");

    if (elPeriodoLabel) elPeriodoLabel.textContent = periodoLabel;
    if (elTopPeriodo) elTopPeriodo.textContent = periodoLabel;

    renderMensal(pick(data, "faturamento_mensal_6m", []));
    renderTopServicos(pick(data, "top_servicos", []));
    renderTopProfissionais(pick(data, "top_profissionais", []));
}

function renderMensal(lista) {
    const box = document.getElementById("box-mensal");
    if (!box) return;

    box.innerHTML = "";

    if (!Array.isArray(lista) || !lista.length) {
        box.innerHTML = `<div style="color:#777; padding:10px;">Sem dados no período.</div>`;
        return;
    }

    const max = Math.max(...lista.map((x) => Number(x.total || 0)), 1);

    lista.forEach((item) => {
        const pct = Math.max(0, Math.round((Number(item.total || 0) / max) * 100));
        const el = document.createElement("div");
        el.className = "rel-bar";
        el.innerHTML = `
            <div class="label">${ymToLabel(item.ym)}</div>
            <div class="track"><div class="fill" style="width:${pct}%;"></div></div>
            <div class="val">${brl(item.total)}</div>
        `;
        box.appendChild(el);
    });
}

function renderTopServicos(lista) {
    const box = document.getElementById("box-top-servicos");
    if (!box) return;

    box.innerHTML = "";

    if (!Array.isArray(lista) || !lista.length) {
        box.innerHTML = `<div style="color:#777; padding:10px;">Sem serviços pagos no período.</div>`;
        return;
    }

    lista.forEach((s) => {
        const el = document.createElement("div");
        el.className = "rel-item";
        el.innerHTML = `
            <div>
                <div class="name">${s.servico_nome || "Serviço"}</div>
                <div class="meta">${Number(s.qtd || 0)} atendimentos</div>
            </div>
            <div style="font-weight:800;">${brl(s.total)}</div>
        `;
        box.appendChild(el);
    });
}

function renderTopProfissionais(lista) {
    const box = document.getElementById("box-top-profissionais");
    if (!box) return;

    box.innerHTML = "";

    if (!Array.isArray(lista) || !lista.length) {
        box.innerHTML = `<div style="color:#777; padding:10px;">Sem dados de profissionais no período.</div>`;
        return;
    }

    lista.forEach((p) => {
        const el = document.createElement("div");
        el.className = "prof-card";
        el.innerHTML = `
            <div class="nome">${p.profissional_nome || "Profissional"}</div>
            <div class="line"><span>Atendimentos</span><b>${Number(p.atendimentos || 0)}</b></div>
            <div class="line"><span>Faturamento</span><span class="total">${brl(p.total)}</span></div>
        `;
        box.appendChild(el);
    });
}