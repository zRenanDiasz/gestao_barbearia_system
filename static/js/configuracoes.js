// static/js/configuracoes.js

document.addEventListener("DOMContentLoaded", () => {
    initConfiguracoes();
});

function initConfiguracoes() {
    initTabs();
    initGeral();
    initHorarios();
}

/* =========================
   TABS (Geral / Horários)
========================= */
function initTabs() {
    const tabs = Array.from(document.querySelectorAll(".cfg-tab"));
    const panelGeral = document.getElementById("tab-geral");
    const panelHorarios = document.getElementById("tab-horarios");

    if (!tabs.length || !panelGeral || !panelHorarios) return;

    function setActive(tabKey) {
        tabs.forEach((t) => t.classList.toggle("is-active", t.dataset.tab === tabKey));
        panelGeral.classList.toggle("is-active", tabKey === "geral");
        panelHorarios.classList.toggle("is-active", tabKey === "horarios");
    }

    tabs.forEach((btn) => {
        btn.addEventListener("click", () => {
            const key = btn.dataset.tab;
            setActive(key);
            if (key === "horarios") carregarHorarios().catch(() => { });
        });
    });
}

/* =========================
   GERAL
========================= */
function initGeral() {
    const form = document.getElementById("form-geral");
    if (!form) return;

    carregarGeral().catch(() => { });

    form.addEventListener("submit", async (e) => {
        e.preventDefault();

        const payload = {
            nome: document.getElementById("cfg-nome")?.value || "",
            telefone: document.getElementById("cfg-telefone")?.value || "",
            endereco: document.getElementById("cfg-endereco")?.value || "",
            email: document.getElementById("cfg-email")?.value || "",
            cnpj: document.getElementById("cfg-cnpj")?.value || "",
        };

        try {
            await API.put("/configuracoes/geral", payload);
            await carregarGeral();
        } catch (err) {
            console.warn("Falha ao salvar configurações gerais:", err?.message || err);
        }
    });
}

async function carregarGeral() {
    try {
        const resp = await API.get("/configuracoes/geral");
        if (!resp) return;

        const g = resp.geral || resp;

        const set = (id, val) => {
            const el = document.getElementById(id);
            if (el) el.value = val || "";
        };

        set("cfg-nome", g.nome);
        set("cfg-telefone", g.telefone);
        set("cfg-endereco", g.endereco);
        set("cfg-email", g.email);
        set("cfg-cnpj", g.cnpj);
    } catch (err) {
        console.warn("Falha ao carregar configurações gerais:", err?.message || err);
    }
}

/* =========================
   HORÁRIOS
========================= */
const DIAS = [
    { idx: 0, nome: "Domingo" },
    { idx: 1, nome: "Segunda-feira" },
    { idx: 2, nome: "Terça-feira" },
    { idx: 3, nome: "Quarta-feira" },
    { idx: 4, nome: "Quinta-feira" },
    { idx: 5, nome: "Sexta-feira" },
    { idx: 6, nome: "Sábado" },
];

function initHorarios() {
    const btnSalvar = document.getElementById("btn-salvar-horarios");
    const lista = document.getElementById("lista-horarios");
    if (!btnSalvar || !lista) return;

    lista.innerHTML = "";
    DIAS.forEach((d) => lista.appendChild(criarLinhaDia(d)));

    carregarHorarios().catch(() => { });

    btnSalvar.addEventListener("click", async () => {
        try {
            const payload = coletarHorariosDaTela();
            const res = await API.put("/configuracoes/horarios", { horarios: payload });

            await carregarHorarios();
            alert(res?.mensagem || "Horários salvos com sucesso.");
        } catch (err) {
            console.warn("Falha ao salvar horários:", err?.message || err);
            alert(err?.message || "Erro ao salvar horários.");
        }
    });
}

function criarLinhaDia(d) {
    const row = document.createElement("div");
    row.className = "cfg-row";
    row.dataset.dia = String(d.idx);

    row.innerHTML = `
    <div class="cfg-dia">${d.nome}</div>
    <input class="cfg-time" type="time" value="09:00" data-role="inicio" />
    <input class="cfg-time" type="time" value="19:00" data-role="fim" />
    <div class="cfg-toggle">
      <div class="cfg-switch is-on" role="switch" aria-checked="true" tabindex="0" data-role="aberto"></div>
    </div>
  `;

    const sw = row.querySelector('[data-role="aberto"]');
    sw.addEventListener("click", () => toggleSwitch(sw));
    sw.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            toggleSwitch(sw);
        }
    });

    aplicarEstadoLinha(row, true);
    return row;
}

function toggleSwitch(sw) {
    const on = sw.classList.toggle("is-on");
    sw.setAttribute("aria-checked", on ? "true" : "false");
    const row = sw.closest(".cfg-row");
    aplicarEstadoLinha(row, on);
}

function aplicarEstadoLinha(row, aberto) {
    if (!row) return;
    const ini = row.querySelector('[data-role="inicio"]');
    const fim = row.querySelector('[data-role="fim"]');
    if (ini) ini.disabled = !aberto;
    if (fim) fim.disabled = !aberto;
}

function coletarHorariosDaTela() {
    const rows = Array.from(document.querySelectorAll(".cfg-row"));
    return rows.map((r) => {
        const dia = Number(r.dataset.dia);
        const sw = r.querySelector('[data-role="aberto"]');
        const aberto = sw?.classList.contains("is-on") ? 1 : 0;
        const hora_inicio = r.querySelector('[data-role="inicio"]')?.value || "09:00";
        const hora_fim = r.querySelector('[data-role="fim"]')?.value || "19:00";
        return { dia_semana: dia, aberto, hora_inicio, hora_fim };
    });
}

async function carregarHorarios() {
    const lista = document.getElementById("lista-horarios");
    if (!lista) return;

    try {
        const resp = await API.get("/configuracoes/horarios");
        if (!resp) return;

        const horarios = resp.horarios || resp;
        if (!Array.isArray(horarios) || !horarios.length) return;

        horarios.forEach((h) => {
            const row = lista.querySelector(`.cfg-row[data-dia="${h.dia_semana}"]`);
            if (!row) return;

            const ini = row.querySelector('[data-role="inicio"]');
            const fim = row.querySelector('[data-role="fim"]');
            const sw = row.querySelector('[data-role="aberto"]');

            const isOn = Number(h.aberto) === 1;

            if (ini) ini.value = (h.hora_inicio || "09:00").slice(0, 5);
            if (fim) fim.value = (h.hora_fim || "19:00").slice(0, 5);

            if (sw) {
                sw.classList.toggle("is-on", isOn);
                sw.setAttribute("aria-checked", isOn ? "true" : "false");
            }

            aplicarEstadoLinha(row, isOn);
        });
    } catch (err) {
        console.warn("Falha ao carregar horários:", err?.message || err);
    }
}
