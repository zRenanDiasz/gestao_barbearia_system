let agendamentosBase = [];
let listaAtualNaTela = [];

/* =========================
   Inicialização da Agenda
   Sistema profissional para operação real de barbearia
========================= */
document.addEventListener("DOMContentLoaded", () => {
    inicializarFiltros();
    inicializarModal();
    inicializarModalPagamento();
    inicializarModalPlano();
    inicializarMenusLinha();
    inicializarMenuStatus();

    carregarAgenda().catch((err) => notify(err?.message || "Erro ao carregar a agenda.", "error"));
});

/* =========================
   Utilitários gerais
========================= */
function formatBRL(n) {
    return `R$ ${Number(n || 0).toFixed(2).replace(".", ",")}`;
}

function isoParaBR(iso) {
    if (!iso || typeof iso !== "string" || !iso.includes("-")) return iso || "";
    const [yyyy, mm, dd] = iso.split("-");
    return `${dd}/${mm}/${yyyy}`;
}

function todayISO() {
    const d = new Date();
    const yyyy = d.getFullYear();
    const mm = String(d.getMonth() + 1).padStart(2, "0");
    const dd = String(d.getDate()).padStart(2, "0");
    return `${yyyy}-${mm}-${dd}`;
}

function isConcluido(status) {
    return String(status || "").toLowerCase() === "concluido";
}

function isCancelado(status) {
    return String(status || "").toLowerCase() === "cancelado";
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

function escapeHtml(str) {
    return String(str || "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

/* =========================
   Helpers de configuração
========================= */
function diaSemanaKey(dataISO) {
    const dt = new Date(dataISO + "T00:00:00");
    const map = ["dom", "seg", "ter", "qua", "qui", "sex", "sab"];
    return map[dt.getDay()];
}

function parseDiasTrabalho(raw) {
    return String(raw || "")
        .split(",")
        .map((s) => s.trim().toLowerCase())
        .filter(Boolean);
}

async function getBloqueiosDoDia(dataISO) {
    try {
        const rows = await API.get(`/bloqueios?data=${dataISO}`);
        return Array.isArray(rows) ? rows : [];
    } catch (_) {
        return [];
    }
}

/* =========================
   Carregamento de dados
========================= */
async function carregarAgenda() {
    const data = await API.get("/agendamentos");

    agendamentosBase = (data || []).map((a) => (
        a ? {
            id: a.id,
            cliente_id: a.cliente_id,
            cliente: a.cliente_nome,
            profissional_id: a.profissional_id,
            profissional: a.profissional_nome,
            servico_id: a.servico_id,
            servico: a.servico_nome,
            data: a.data,
            horario: a.horario,
            status: a.status,
            valor: Number(a.preco || 0),
        } : null
    )).filter(Boolean);

    const filtroData = document.getElementById("filtro-data");
    if (filtroData && !filtroData.value) filtroData.value = todayISO();

    popularFiltroProfissionais(agendamentosBase);
    aplicarFiltros();
}

/* =========================
   Filtros + KPIs
========================= */
let _searchTimer = null;

function inicializarFiltros() {
    const dataEl = document.getElementById("filtro-data");
    if (dataEl && !dataEl.value) dataEl.value = todayISO();
    dataEl?.addEventListener("change", aplicarFiltros);

    document.getElementById("filtro-status")?.addEventListener("change", aplicarFiltros);
    document.getElementById("filtro-profissional")?.addEventListener("change", aplicarFiltros);

    const searchEl = document.querySelector(".search-input");
    searchEl?.addEventListener("input", () => {
        if (_searchTimer) clearTimeout(_searchTimer);
        _searchTimer = setTimeout(aplicarFiltros, 180);
    });
}

function aplicarFiltros() {
    let lista = [...agendamentosBase];

    const dataSel = document.getElementById("filtro-data")?.value || "";
    const dataRef = dataSel || todayISO();
    lista = lista.filter((a) => String(a.data) === String(dataRef));

    const status = (document.getElementById("filtro-status")?.value || "").toLowerCase();
    if (status) {
        lista = lista.filter((a) => {
            const st = String(a.status || "").toLowerCase();
            if (status === "confirmado") return st === "confirmado" || st === "concluido";
            return st === status;
        });
    }

    const profissional = document.getElementById("filtro-profissional")?.value || "";
    if (profissional) {
        lista = lista.filter((a) => String(a.profissional || "") === profissional);
    }

    const q = (document.querySelector(".search-input")?.value || "").trim().toLowerCase();
    if (q) {
        lista = lista.filter((a) => {
            const hay = `${a.cliente || ""} ${a.profissional || ""} ${a.servico || ""}`.toLowerCase();
            return hay.includes(q);
        });
    }

    listaAtualNaTela = lista;
    renderizarKPIs(lista);
    renderizarTabela(lista);
}

function popularFiltroProfissionais(lista) {
    const select = document.getElementById("filtro-profissional");
    if (!select) return;

    const current = select.value || "";
    select.innerHTML = `<option value="">Todos os Profissionais</option>`;

    const nomes = [...new Set((lista || []).map((a) => a.profissional).filter(Boolean))]
        .sort((a, b) => String(a).localeCompare(String(b)));

    nomes.forEach((nome) => {
        const option = document.createElement("option");
        option.value = nome;
        option.textContent = nome;
        select.appendChild(option);
    });

    if (current && [...select.options].some((o) => o.value === current)) {
        select.value = current;
    } else {
        select.value = "";
    }
}

function renderizarKPIs(lista) {
    const total = lista.length;

    const confirmados = lista.filter((a) => {
        const st = String(a.status || "").toLowerCase();
        return st === "confirmado" || st === "concluido";
    }).length;

    const aguardando = lista.filter((a) => String(a.status || "").toLowerCase() === "aguardando").length;

    const faturamentoPrevisto = lista
        .filter((a) => {
            const st = String(a.status || "").toLowerCase();
            return st === "confirmado" || st === "aguardando";
        })
        .reduce((soma, a) => soma + Number(a.valor || 0), 0);

    const elTotal = document.getElementById("kpi-total");
    if (elTotal) elTotal.textContent = String(total);

    const elConfirmados = document.getElementById("kpi-confirmados");
    if (elConfirmados) elConfirmados.textContent = String(confirmados);

    const elAguardando = document.getElementById("kpi-aguardando");
    if (elAguardando) elAguardando.textContent = String(aguardando);

    const elFat = document.getElementById("kpi-faturamento");
    if (elFat) elFat.textContent = formatBRL(faturamentoPrevisto);
}

/* =========================
   Renderização da tabela
========================= */
function renderizarTabela(lista) {
    const tbody = document.querySelector(".agenda-table tbody");
    if (!tbody) return;

    tbody.innerHTML = "";

    if (!lista || lista.length === 0) {
        const tr = document.createElement("tr");
        tr.innerHTML = `<td colspan="8" style="padding:14px; opacity:0.75;">Nenhum agendamento encontrado para os filtros selecionados.</td>`;
        tbody.appendChild(tr);
        return;
    }

    lista.forEach((ag) => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td>${ag.cliente || ""}</td>
            <td>${ag.profissional || ""}</td>
            <td>${ag.servico || ""}</td>
            <td>${isoParaBR(ag.data)}</td>
            <td>${ag.horario || ""}</td>
            <td>${badgeStatus(ag.status, ag.id)}</td>
            <td>${formatBRL(ag.valor)}</td>
            <td class="td-actions">
                <button type="button" class="row-menu-btn" data-action="row-menu" data-id="${ag.id}">⋮</button>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

function badgeStatus(status, id) {
    const st = String(status || "").toLowerCase();

    const map = {
        concluido: { label: "Concluído", cls: "success" },
        confirmado: { label: "Confirmado", cls: "info" },
        aguardando: { label: "Aguardando", cls: "warning" },
        cancelado: { label: "Cancelado", cls: "danger" },
    };

    const s = map[st] || map.aguardando;

    return `
        <button type="button"
                class="badge badge-btn ${s.cls}"
                data-action="status"
                data-id="${id}">
            ${s.label}
        </button>
    `;
}

/* =========================
   Modal de criar / editar agendamento
========================= */
function inicializarModal() {
    document.getElementById("btn-novo-agendamento")?.addEventListener("click", abrirModalCriar);

    document.getElementById("btn-fechar-modal")?.addEventListener("click", fecharModal);
    document.getElementById("btn-cancelar-modal")?.addEventListener("click", fecharModal);

    const overlay = document.getElementById("modal-novo-agendamento");
    overlay?.addEventListener("click", (e) => {
        if (e.target === overlay) fecharModal();
    });

    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape") fecharModal();
    });

    const form = document.getElementById("form-agendamento");
    if (!form) return;

    bindClientePhoneToggle(form);

    form.querySelector("#servico")?.addEventListener("change", () => {
        const sel = form.querySelector("#servico");
        const opt = sel?.selectedOptions?.[0];
        const preco = opt?.dataset?.preco ? Number(opt.dataset.preco) : 0;
        const valorEl = form.querySelector("#valor");
        if (valorEl) valorEl.value = formatBRL(preco);
    });

    const dataEl = form.querySelector("#data");
    dataEl?.addEventListener("change", async () => {
        const profSelect = form.querySelector("#profissional");
        await popularSelectProfissionais(profSelect, dataEl.value, null);
    });

    form.addEventListener("submit", async (e) => {
        e.preventDefault();

        try {
            const clienteNomeEl = form.querySelector("#cliente_nome");
            const clienteIdEl = form.querySelector("#cliente_id");
            const clienteTelEl = form.querySelector("#cliente_telefone");

            const profEl = form.querySelector("#profissional");
            const servEl = form.querySelector("#servico");
            const dataEl2 = form.querySelector("#data");
            const horaEl = form.querySelector("#horario");

            if (!clienteNomeEl || !clienteIdEl || !clienteTelEl || !profEl || !servEl || !dataEl2 || !horaEl) {
                throw new Error("IDs do formulário não encontrados. Verifique o modal de agendamento.");
            }

            const cliente_nome = clienteNomeEl.value.trim();
            let cliente_id = Number(clienteIdEl.value || 0);

            const profissional_id = Number(profEl.value || 0);
            const servico_id = Number(servEl.value || 0);
            const data = dataEl2.value;
            const horario = horaEl.value;

            if (!cliente_nome) {
                return notify("Informe o nome do cliente.", "warning");
            }

            if (!cliente_id) {
                const telefone = clienteTelEl.value.trim();
                if (!telefone) {
                    return notify("Informe o telefone para cadastrar o cliente.", "warning");
                }

                const respCliente = await API.post("/clientes", {
                    nome: cliente_nome,
                    telefone: telefone,
                    observacoes: ""
                });

                cliente_id = Number(respCliente?.id || respCliente?.data?.id || 0);
                if (!cliente_id) {
                    throw new Error("Não foi possível ler o ID do cliente criado.");
                }

                clienteIdEl.value = String(cliente_id);
            }

            if (!profissional_id || !servico_id || !data || !horario) {
                return notify("Preencha Profissional, Serviço, Data e Horário.", "warning");
            }

            const editId = form.dataset.editId || null;

            if (editId) {
                await API.put(`/agendamentos/${editId}`, { cliente_id, profissional_id, servico_id, data, horario });
            } else {
                await API.post("/agendamentos", { cliente_id, profissional_id, servico_id, data, horario });
            }

            await carregarAgenda();
            fecharModal();
        } catch (err) {
            notify(err?.message || "Erro ao salvar agendamento.", "error");
        }
    });
}

function bindClientePhoneToggle(form) {
    const nomeEl = form.querySelector("#cliente_nome");
    const idEl = form.querySelector("#cliente_id");
    const telEl = form.querySelector("#cliente_telefone");
    const boxTel = document.getElementById("box-telefone");

    if (!nomeEl || !idEl || !telEl || !boxTel) return;

    if (form._clientePhoneBinded) return;
    form._clientePhoneBinded = true;

    let phoneTimer = null;
    let preenchendoAutomaticamente = false;

    const aplicarClienteEncontrado = (cliente, telefoneDigitado = "") => {
        preenchendoAutomaticamente = true;

        idEl.value = String(cliente.id || "");
        nomeEl.value = cliente.nome || "";
        nomeEl.readOnly = true;
        nomeEl.dataset.lockedByPhone = "1";

        if (telefoneDigitado) {
            telEl.value = telefoneDigitado;
        } else {
            telEl.value = cliente.telefone || "";
        }

        preenchendoAutomaticamente = false;
        toggle();
    };

    const limparClienteEncontrado = ({ manterNome = false } = {}) => {
        preenchendoAutomaticamente = true;

        idEl.value = "";
        nomeEl.readOnly = false;
        delete nomeEl.dataset.lockedByPhone;

        if (!manterNome) {
            nomeEl.value = "";
        }

        preenchendoAutomaticamente = false;
        toggle();
    };

    const toggle = () => {
        const hasId = Number(idEl.value || 0) > 0;

        boxTel.hidden = false;

        if (hasId) {
            telEl.setAttribute("data-match", "1");
        } else {
            telEl.removeAttribute("data-match");
        }
    };

    const buscarClientePeloTelefone = async () => {
        const telefone = telEl.value.trim();

        if (!telefone || telefone.length < 8) {
            if (nomeEl.dataset.lockedByPhone === "1") {
                limparClienteEncontrado({ manterNome: false });
            }
            return;
        }

        try {
            const resp = await API.get(`/clientes/por-telefone?telefone=${encodeURIComponent(telefone)}`);
            const cliente = resp?.data ?? resp ?? null;

            if (cliente && cliente.id) {
                aplicarClienteEncontrado(cliente, telefone);
            } else {
                if (nomeEl.dataset.lockedByPhone === "1") {
                    limparClienteEncontrado({ manterNome: false });
                } else {
                    idEl.value = "";
                    nomeEl.readOnly = false;
                }
            }
        } catch (err) {
            console.error("Erro ao buscar cliente por telefone:", err);
        }
    };

    nomeEl.addEventListener("input", (e) => {
        if (preenchendoAutomaticamente) return;

        if (nomeEl.dataset.lockedByPhone === "1" && e.isTrusted) {
            nomeEl.value = nomeEl.defaultValue || nomeEl.value;
            return;
        }

        if (e.isTrusted) {
            idEl.value = "";
        }

        toggle();
    });

    nomeEl.addEventListener("focus", () => {
        if (nomeEl.dataset.lockedByPhone === "1") {
            nomeEl.blur();
        }
    });

    telEl.addEventListener("input", () => {
        clearTimeout(phoneTimer);

        if (nomeEl.dataset.lockedByPhone === "1") {
            const telefoneAtual = telEl.value.trim();
            const telefoneAnterior = String(telEl.getAttribute("data-last-match") || "").trim();

            if (telefoneAnterior && telefoneAtual !== telefoneAnterior) {
                limparClienteEncontrado({ manterNome: false });
            }
        }

        phoneTimer = setTimeout(() => {
            buscarClientePeloTelefone();
        }, 250);
    });

    telEl.addEventListener("blur", async () => {
        clearTimeout(phoneTimer);
        await buscarClientePeloTelefone();

        if (Number(idEl.value || 0) > 0) {
            telEl.setAttribute("data-last-match", telEl.value.trim());
            nomeEl.defaultValue = nomeEl.value;
        } else {
            telEl.removeAttribute("data-last-match");
        }
    });

    toggle();
}

async function abrirModalCriar() {
    const overlay = document.getElementById("modal-novo-agendamento");
    const form = document.getElementById("form-agendamento");
    if (!overlay || !form) return;

    delete form.dataset.editId;
    form.reset();

    function bindClientePhoneToggle(form) {
        const nomeEl = form.querySelector("#cliente_nome");
        const idEl = form.querySelector("#cliente_id");
        const telEl = form.querySelector("#cliente_telefone");
        const boxTel = document.getElementById("box-telefone");

        if (!nomeEl || !idEl || !telEl || !boxTel) return;

        if (form._clientePhoneBinded) return;
        form._clientePhoneBinded = true;

        let phoneTimer = null;
        let preenchendoAutomaticamente = false;

        const aplicarClienteEncontrado = (cliente, telefoneDigitado = "") => {
            preenchendoAutomaticamente = true;

            idEl.value = String(cliente.id || "");
            nomeEl.value = cliente.nome || "";
            nomeEl.readOnly = true;
            nomeEl.dataset.lockedByPhone = "1";

            if (telefoneDigitado) {
                telEl.value = telefoneDigitado;
            } else {
                telEl.value = cliente.telefone || "";
            }

            preenchendoAutomaticamente = false;
            toggle();
        };

        const limparClienteEncontrado = ({ manterNome = false } = {}) => {
            preenchendoAutomaticamente = true;

            idEl.value = "";
            nomeEl.readOnly = false;
            delete nomeEl.dataset.lockedByPhone;

            if (!manterNome) {
                nomeEl.value = "";
            }

            preenchendoAutomaticamente = false;
            toggle();
        };

        const toggle = () => {
            const hasId = Number(idEl.value || 0) > 0;

            boxTel.hidden = false;

            if (hasId) {
                telEl.setAttribute("data-match", "1");
            } else {
                telEl.removeAttribute("data-match");
            }
        };

        const buscarClientePeloTelefone = async () => {
            const telefone = telEl.value.trim();

            if (!telefone || telefone.length < 8) {
                if (nomeEl.dataset.lockedByPhone === "1") {
                    limparClienteEncontrado({ manterNome: false });
                }
                return;
            }

            try {
                const resp = await API.get(`/clientes/por-telefone?telefone=${encodeURIComponent(telefone)}`);
                const cliente = resp?.data ?? resp ?? null;

                if (cliente && cliente.id) {
                    aplicarClienteEncontrado(cliente, telefone);
                } else {
                    if (nomeEl.dataset.lockedByPhone === "1") {
                        limparClienteEncontrado({ manterNome: false });
                    } else {
                        idEl.value = "";
                        nomeEl.readOnly = false;
                    }
                }
            } catch (err) {
                console.error("Erro ao buscar cliente por telefone:", err);
            }
        };

        nomeEl.addEventListener("input", (e) => {
            if (preenchendoAutomaticamente) return;

            if (nomeEl.dataset.lockedByPhone === "1" && e.isTrusted) {
                nomeEl.value = nomeEl.defaultValue || nomeEl.value;
                return;
            }

            if (e.isTrusted) {
                idEl.value = "";
            }

            toggle();
        });

        nomeEl.addEventListener("focus", () => {
            if (nomeEl.dataset.lockedByPhone === "1") {
                nomeEl.blur();
            }
        });

        telEl.addEventListener("input", () => {
            clearTimeout(phoneTimer);

            if (nomeEl.dataset.lockedByPhone === "1") {
                const telefoneAtual = telEl.value.trim();
                const telefoneAnterior = String(telEl.getAttribute("data-last-match") || "").trim();

                if (telefoneAnterior && telefoneAtual !== telefoneAnterior) {
                    limparClienteEncontrado({ manterNome: false });
                }
            }

            phoneTimer = setTimeout(() => {
                buscarClientePeloTelefone();
            }, 250);
        });

        telEl.addEventListener("blur", async () => {
            clearTimeout(phoneTimer);
            await buscarClientePeloTelefone();

            if (Number(idEl.value || 0) > 0) {
                telEl.setAttribute("data-last-match", telEl.value.trim());
                nomeEl.defaultValue = nomeEl.value;
            } else {
                telEl.removeAttribute("data-last-match");
            }
        });

        toggle();
    }

    const dataEl = form.querySelector("#data");
    if (dataEl) dataEl.value = todayISO();

    await popularSelectServicos(form.querySelector("#servico"));
    await popularSelectProfissionais(form.querySelector("#profissional"), dataEl?.value || todayISO(), null);

    const valorEl = form.querySelector("#valor");
    if (valorEl) valorEl.value = formatBRL(0);

    bindClientePhoneToggle(form);

    overlay.classList.add("is-open");
    form.querySelector("#cliente_nome")?.focus();
}

async function abrirModalEditarPorId(id) {
    const item = agendamentosBase.find((a) => String(a.id) === String(id));
    if (!item) return;

    const overlay = document.getElementById("modal-novo-agendamento");
    const form = document.getElementById("form-agendamento");
    if (!overlay || !form) return;

    form.reset();

    if (form.querySelector("#cliente_nome")) {
        form.querySelector("#cliente_nome").value = item.cliente || "";
        form.querySelector("#cliente_nome").readOnly = true;
        form.querySelector("#cliente_nome").dataset.lockedByPhone = "1";
        form.querySelector("#cliente_nome").defaultValue = item.cliente || "";
    }
    if (form.querySelector("#cliente_id")) form.querySelector("#cliente_id").value = String(item.cliente_id || "");
    if (form.querySelector("#cliente_telefone")) {
        form.querySelector("#cliente_telefone").value = "";
        form.querySelector("#cliente_telefone").removeAttribute("data-last-match");
    }

    const dataEl = form.querySelector("#data");
    if (dataEl) dataEl.value = item.data;

    await popularSelectServicos(form.querySelector("#servico"));
    await popularSelectProfissionais(form.querySelector("#profissional"), item.data, item.profissional_id);

    if (form.querySelector("#profissional")) form.querySelector("#profissional").value = String(item.profissional_id);
    if (form.querySelector("#servico")) form.querySelector("#servico").value = String(item.servico_id);
    if (form.querySelector("#horario")) form.querySelector("#horario").value = item.horario;

    const opt = form.querySelector("#servico")?.selectedOptions?.[0];
    const preco = opt?.dataset?.preco ? Number(opt.dataset.preco) : Number(item.valor || 0);
    if (form.querySelector("#valor")) form.querySelector("#valor").value = formatBRL(preco);

    form.dataset.editId = String(item.id);

    bindClientePhoneToggle(form);

    overlay.classList.add("is-open");
    form.querySelector("#cliente_nome")?.focus();
}

function fecharModal() {
    const overlay = document.getElementById("modal-novo-agendamento");
    const form = document.getElementById("form-agendamento");
    if (!overlay || !form) return;

    overlay.classList.remove("is-open");
    form.reset();
    delete form.dataset.editId;

    const v = form.querySelector("#valor");
    if (v) v.value = formatBRL(0);
}

/* =========================
   Carregamento de selects
========================= */
async function popularSelectProfissionais(select, dataISO, includeProfId) {
    if (!select) return;

    select.innerHTML = `<option value="">Selecione...</option>`;

    const data = dataISO || todayISO();
    const diaKey = diaSemanaKey(data);

    const profs = await API.get("/profissionais");
    const lista = Array.isArray(profs) ? profs : [];

    const bloqueios = await getBloqueiosDoDia(data);
    const bloqueadoSet = new Set(
        bloqueios
            .filter((b) => String(b.data) === String(data) && (b.dia_inteiro === 1 || b.dia_inteiro === true))
            .map((b) => String(b.profissional_id))
    );

    const disponiveis = lista.filter((p) => {
        const ativo = Number(p.ativo ?? 1) === 1;
        if (!ativo) return false;
        if (bloqueadoSet.has(String(p.id))) return false;

        const dias = parseDiasTrabalho(p.dias_trabalho);
        if (dias.length && !dias.includes(diaKey)) return false;

        return true;
    });

    disponiveis.forEach((p) => {
        const opt = document.createElement("option");
        opt.value = p.id;
        opt.textContent = p.nome;
        select.appendChild(opt);
    });

    if (includeProfId && !disponiveis.some((p) => String(p.id) === String(includeProfId))) {
        const atual = lista.find((p) => String(p.id) === String(includeProfId));
        if (atual) {
            const opt = document.createElement("option");
            opt.value = atual.id;
            opt.textContent = `${atual.nome} (indisponível na data)`;
            select.appendChild(opt);
        }
    }

    if (select.options.length === 1) {
        const opt = document.createElement("option");
        opt.value = "";
        opt.textContent = "Nenhum profissional disponível nessa data";
        opt.disabled = true;
        select.appendChild(opt);
    }
}

async function popularSelectServicos(select) {
    if (!select) return;

    select.innerHTML = `<option value="">Selecione...</option>`;

    const servs = await API.get("/servicos?status=ativo");
    const lista = Array.isArray(servs) ? servs : [];

    lista.forEach((s) => {
        const opt = document.createElement("option");
        opt.value = s.id;
        opt.textContent = s.nome;
        opt.dataset.preco = s.preco;
        opt.dataset.duracao = s.duracao;
        select.appendChild(opt);
    });

    if (lista.length > 0) {
        select.value = String(lista[0].id);
        const opt = select.selectedOptions?.[0];
        const preco = opt?.dataset?.preco ? Number(opt.dataset.preco) : 0;
        const valorEl = document.querySelector("#form-agendamento #valor");
        if (valorEl) valorEl.value = formatBRL(preco);
    }
}

/* =========================
   Menu de ações por linha
========================= */
let rowMenuEl = null;

function inicializarMenusLinha() {
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
}

function abrirRowMenu(anchorBtn, id) {
    fecharRowMenu();

    const item = agendamentosBase.find((a) => String(a.id) === String(id));
    const podeReceber = item && !isConcluido(item.status) && !isCancelado(item.status);

    const rect = anchorBtn.getBoundingClientRect();

    rowMenuEl = document.createElement("div");
    rowMenuEl.className = "row-menu";
    rowMenuEl.innerHTML = `
        <button type="button" class="row-opt" data-act="editar" data-id="${id}">
            ✎ <span>Editar</span>
        </button>

        ${podeReceber ? `
            <button type="button" class="row-opt" data-act="receber" data-id="${id}">
                💳 <span style="font-weight:600;">Receber</span>
            </button>
        ` : ""}

        <button type="button" class="row-opt danger" data-act="cancelar" data-id="${id}">
            ✖ <span>Cancelar</span>
        </button>
    `;

    document.body.appendChild(rowMenuEl);

    const top = rect.bottom + window.scrollY + 8;
    const left = rect.right + window.scrollX - rowMenuEl.offsetWidth;

    rowMenuEl.style.top = `${top}px`;
    rowMenuEl.style.left = `${left}px`;

    rowMenuEl.addEventListener("click", async (e) => {
        const opt = e.target.closest(".row-opt");
        if (!opt) return;

        const acao = opt.dataset.act;
        const agId = opt.dataset.id;

        try {
            if (acao === "editar") await abrirModalEditarPorId(agId);

            if (acao === "receber") {
                const ag = agendamentosBase.find((a) => String(a.id) === String(agId));
                if (ag) await decidirFluxoRecebimento(ag);
            }

            if (acao === "cancelar") await atualizarStatusPorId(agId, "cancelado");
        } catch (err) {
            console.error(err);
            notify(err?.message || "Erro ao executar ação.", "error");
        } finally {
            fecharRowMenu();
        }
    });
}

function fecharRowMenu() {
    if (rowMenuEl) {
        rowMenuEl.remove();
        rowMenuEl = null;
    }
}

/* =========================
   Menu de status
========================= */
let statusMenuEl = null;

function inicializarMenuStatus() {
    document.addEventListener("click", (e) => {
        const btn = e.target.closest('[data-action="status"]');
        if (!btn) {
            fecharStatusMenu();
            return;
        }

        e.preventDefault();
        e.stopPropagation();

        abrirStatusMenu(btn, btn.dataset.id);
    });

    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape") fecharStatusMenu();
    });
}

function abrirStatusMenu(anchorBtn, id) {
    fecharStatusMenu();

    const item = agendamentosBase.find((a) => String(a.id) === String(id));
    if (!item) return;
    if (isConcluido(item.status)) return;

    const rect = anchorBtn.getBoundingClientRect();

    statusMenuEl = document.createElement("div");
    statusMenuEl.className = "status-menu";
    statusMenuEl.innerHTML = `
        <button type="button" class="status-opt" data-status="aguardando" data-id="${id}">
            <span class="dot warning"></span> Aguardando
        </button>
        <button type="button" class="status-opt" data-status="cancelado" data-id="${id}">
            <span class="dot danger"></span> Cancelado
        </button>
    `;

    document.body.appendChild(statusMenuEl);

    const top = rect.bottom + window.scrollY + 8;
    const left = rect.left + window.scrollX;

    statusMenuEl.style.top = `${top}px`;
    statusMenuEl.style.left = `${left}px`;

    statusMenuEl.addEventListener("click", async (e) => {
        const opt = e.target.closest(".status-opt");
        if (!opt) return;

        try {
            await atualizarStatusPorId(opt.dataset.id, opt.dataset.status);
        } catch (err) {
            console.error(err);
            notify(err?.message || "Erro ao atualizar status.", "error");
        } finally {
            fecharStatusMenu();
        }
    });
}

function fecharStatusMenu() {
    if (statusMenuEl) {
        statusMenuEl.remove();
        statusMenuEl = null;
    }
}

async function atualizarStatusPorId(id, novoStatus) {
    await API.put(`/agendamentos/${id}/status`, { status: novoStatus });
    await carregarAgenda();
}

/* =========================
   Estado global do pagamento
========================= */
let pagamentoModalEl = null;
let planoModalEl = null;

let _pg = {
    ag: null,
    produtosCatalogo: [],
    itens: [],
    comissao: { ok: false, tipo: null, valor: 0, total: 0, pct: null, label: "não definida" },
    plano: null,
    podeUsarPlano: false,
    modoEscolhido: null,
    carregando: false,
};

/* =========================
   Modal de pagamento
   Fluxo profissional para recebimento no caixa
========================= */
function inicializarModalPagamento() {
    pagamentoModalEl = document.createElement("div");
    pagamentoModalEl.id = "modal-pagamento";
    pagamentoModalEl.style.display = "none";
    pagamentoModalEl.style.position = "fixed";
    pagamentoModalEl.style.inset = "0";
    pagamentoModalEl.style.background = "rgba(0,0,0,0.45)";
    pagamentoModalEl.style.zIndex = "9999";

    pagamentoModalEl.innerHTML = `
        <div class="pg-card" style="
            width: min(640px, 94vw);
            max-height: 84vh;
            overflow: auto;
            background:#fff;
            border-radius: 14px;
            padding: 18px;
            margin: 7vh auto;
            box-shadow: 0 18px 50px rgba(0,0,0,.25);
            position: relative;
        ">
            <button type="button" id="pg-close" aria-label="Fechar" style="
                position:absolute; right:14px; top:10px;
                width:36px; height:36px; border-radius:10px;
                border:0; background:transparent; cursor:pointer;
                font-size:20px; line-height:1; opacity:.75;
            ">×</button>

            <div style="margin-bottom:10px;">
                <div style="font-weight:800; font-size:18px;">Receber / Pagamento</div>
                <div style="font-size:13px; opacity:.75; margin-top:3px;">
                    Registre o pagamento do agendamento e produtos adicionais.
                </div>
            </div>

            <div id="pg-info" style="
                font-size:14px; line-height:1.55;
                padding: 10px 0 14px;
                border-bottom: 1px solid #eee;
            "></div>

            <div id="pg-forma-grid" style="display:grid; grid-template-columns: 1fr 1fr; gap:14px; padding: 14px 0;">
                <div>
                    <label style="display:block; font-size:13px; margin:0 0 6px; font-weight:600;">Forma de pagamento</label>
                    <select id="pg-forma" style="width:100%; padding:10px 12px; border:1px solid #e3e3e3; border-radius:10px;">
                        <option value="dinheiro">Dinheiro</option>
                        <option value="pix">Pix</option>
                        <option value="debito">Débito</option>
                        <option value="credito">Crédito</option>
                    </select>
                </div>

                <div>
                    <label style="display:block; font-size:13px; margin:0 0 6px; font-weight:600;">Valor</label>
                    <input id="pg-valor-servico" type="number" step="0.01" min="0" style="width:100%; padding:10px 12px; border:1px solid #e3e3e3; border-radius:10px;" />
                    <div id="pg-comissao-label" style="font-size:12px; opacity:.75; margin-top:6px;">Comissão (somente serviço): não definida</div>
                </div>
            </div>

            <div id="pg-produtos-head" style="border-top: 1px solid #eee; padding-top:14px; display:flex; align-items:center; justify-content:space-between; gap:10px;">
                <div style="font-weight:800; font-size:16px;">Produtos</div>
                <button type="button" id="pg-add-btn" style="
                    padding: 8px 12px;
                    border:0;
                    border-radius: 10px;
                    cursor:pointer;
                    background:#16a34a;
                    color:#fff;
                    font-weight:700;
                ">+ Adicionar</button>
            </div>

            <div id="pg-produtos-row" style="display:grid; grid-template-columns: 1fr 140px; gap:12px; padding: 12px 0 6px;">
                <div>
                    <label style="display:block; font-size:13px; margin:0 0 6px;">Produto</label>
                    <select id="pg-produto" style="width:100%; padding:10px 12px; border:1px solid #e3e3e3; border-radius:10px;">
                        <option value="">Carregando...</option>
                    </select>
                </div>
                <div>
                    <label style="display:block; font-size:13px; margin:0 0 6px;">Qtd:</label>
                    <input id="pg-qtd" type="number" min="1" step="1" value="1" style="width:100%; padding:10px 12px; border:1px solid #e3e3e3; border-radius:10px;" />
                </div>
            </div>

            <div id="pg-itens" style="padding: 6px 0 10px;"></div>

            <div id="pg-box-comissao" style="
                border: 1px solid #f5d37a;
                background: #fff7e6;
                border-radius: 12px;
                padding: 12px 12px;
                display:flex;
                justify-content:space-between;
                gap:10px;
                align-items:flex-start;
                margin: 8px 0 10px;
            ">
                <div>
                    <div id="pg-box-comissao-title" style="font-weight:800;">Comissão</div>
                    <div id="pg-box-comissao-sub" style="font-size:12px; opacity:.75; margin-top:2px;">
                        Calculado sobre o valor do serviço: ${formatBRL(0)}
                    </div>
                </div>
                <div id="pg-box-comissao-val" style="font-weight:900; color:#d97706;">${formatBRL(0)}</div>
            </div>

            <div id="pg-total-box" style="border-top: 1px solid #eee; padding-top: 10px;">
                <div style="display:flex; justify-content:space-between; margin-top:6px;">
                    <div style="opacity:.85;">Subtotal Produtos</div>
                    <div id="pg-subtotal-prod" style="font-weight:800;">${formatBRL(0)}</div>
                </div>

                <div style="display:flex; justify-content:space-between; margin-top:6px;">
                    <div style="font-weight:900;">Total a Receber</div>
                    <div id="pg-total" style="font-weight:900; color:#16a34a; font-size:18px;">${formatBRL(0)}</div>
                </div>
            </div>

            <div style="display:flex; gap:10px; justify-content:flex-end; margin-top:14px;">
                <button type="button" id="pg-cancelar" style="
                    padding:10px 14px; border:1px solid #e3e3e3; border-radius:10px; background:#fff; cursor:pointer;
                ">Cancelar</button>
                <button type="button" id="pg-confirmar" style="
                    padding:10px 14px; border:0; border-radius:10px;
                    background:#d97706; color:#fff; font-weight:800; cursor:pointer;
                ">Confirmar pagamento</button>
            </div>
        </div>
    `;

    document.body.appendChild(pagamentoModalEl);

    pagamentoModalEl.addEventListener("click", (e) => {
        if (e.target === pagamentoModalEl) fecharModalPagamento();
    });

    pagamentoModalEl.querySelector("#pg-close")?.addEventListener("click", fecharModalPagamento);
    pagamentoModalEl.querySelector("#pg-cancelar")?.addEventListener("click", fecharModalPagamento);

    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape") fecharModalPagamento();
    });

    pagamentoModalEl.querySelector("#pg-add-btn")?.addEventListener("click", () => {
        try {
            adicionarProdutoSelecionado();
        } catch (err) {
            console.error(err);
            notify(err?.message || "Erro ao adicionar produto.", "error");
        }
    });

    pagamentoModalEl.querySelector("#pg-valor-servico")?.addEventListener("input", () => {
        recalcularComissaoETotais();
    });

    pagamentoModalEl.querySelector("#pg-confirmar")?.addEventListener("click", async () => {
        try {
            await confirmarPagamento();
        } catch (err) {
            console.error(err);
            notify(err?.message || "Erro ao confirmar pagamento.", "error");
        }
    });
}

function fecharModalPagamento() {
    if (!pagamentoModalEl) return;

    pagamentoModalEl.style.display = "none";
    delete pagamentoModalEl.dataset.id;

    _pg = {
        ag: null,
        produtosCatalogo: [],
        itens: [],
        comissao: { ok: false, tipo: null, valor: 0, total: 0, pct: null, label: "não definida" },
        plano: null,
        podeUsarPlano: false,
        modoEscolhido: null,
        carregando: false,
    };

    const info = pagamentoModalEl.querySelector("#pg-info");
    if (info) info.innerHTML = "";

    const valorServicoEl = pagamentoModalEl.querySelector("#pg-valor-servico");
    if (valorServicoEl) valorServicoEl.value = "0.00";

    const formaEl = pagamentoModalEl.querySelector("#pg-forma");
    if (formaEl) formaEl.value = "dinheiro";

    const qtdEl = pagamentoModalEl.querySelector("#pg-qtd");
    if (qtdEl) qtdEl.value = "1";

    const produtoEl = pagamentoModalEl.querySelector("#pg-produto");
    if (produtoEl) produtoEl.innerHTML = `<option value="">Carregando...</option>`;

    renderItensProdutos();
    atualizarUIComissao();
    togglePagamentoNormal(true);
}

function togglePagamentoNormal(show) {
    if (!pagamentoModalEl) return;

    const formaGrid = pagamentoModalEl.querySelector("#pg-forma-grid");
    const produtosHead = pagamentoModalEl.querySelector("#pg-produtos-head");
    const produtosRow = pagamentoModalEl.querySelector("#pg-produtos-row");
    const itensBox = pagamentoModalEl.querySelector("#pg-itens");
    const comissaoBox = pagamentoModalEl.querySelector("#pg-box-comissao");
    const totalBox = pagamentoModalEl.querySelector("#pg-total-box");
    const btnConfirmar = pagamentoModalEl.querySelector("#pg-confirmar");

    if (formaGrid) formaGrid.style.display = show ? "grid" : "none";
    if (produtosHead) produtosHead.style.display = show ? "flex" : "none";
    if (produtosRow) produtosRow.style.display = show ? "grid" : "none";
    if (itensBox) itensBox.style.display = show ? "block" : "none";
    if (comissaoBox) comissaoBox.style.display = show ? "flex" : "none";
    if (totalBox) totalBox.style.display = show ? "block" : "none";
    if (btnConfirmar) btnConfirmar.style.display = show ? "inline-block" : "none";
}

function preencherResumoPagamento(ag) {
    const info = pagamentoModalEl?.querySelector("#pg-info");
    if (!info) return;

    info.innerHTML = `
        <div><strong>Cliente:</strong> ${escapeHtml(ag?.cliente || "")}</div>
        <div><strong>Serviço:</strong> ${escapeHtml(ag?.servico || "")} (${formatBRL(ag?.valor || 0)})</div>
        <div><strong>Profissional:</strong> ${escapeHtml(ag?.profissional || "")}</div>
        <div><strong>Data/Hora:</strong> ${isoParaBR(ag?.data || "")} ${escapeHtml(ag?.horario || "")}</div>
    `;
}

async function abrirModalPagamento(ag, options = {}) {
    if (!pagamentoModalEl || !ag) return;
    if (isConcluido(ag.status)) return;

    const { skipPlano = false } = options;

    _pg = {
        ag,
        produtosCatalogo: [],
        itens: [],
        comissao: { ok: false, tipo: null, valor: 0, total: 0, pct: null, label: "não definida" },
        plano: null,
        podeUsarPlano: false,
        modoEscolhido: skipPlano ? "normal" : null,
        carregando: false,
    };

    pagamentoModalEl.dataset.id = String(ag.id);
    pagamentoModalEl.style.display = "block";

    const info = pagamentoModalEl.querySelector("#pg-info");
    if (info) info.innerHTML = "";

    togglePagamentoNormal(false);

    let plano = null;
    let podeUsarPlano = false;

    if (!skipPlano) {
        try {
            plano = await buscarPlanoAtivoCliente(ag.cliente_id);
            podeUsarPlano = Boolean(plano && Number(plano.usos_restantes || 0) > 0);
        } catch (err) {
            console.error("Erro ao consultar plano ativo:", err);
        }
    }

    _pg.plano = plano;
    _pg.podeUsarPlano = podeUsarPlano;

    if (plano && podeUsarPlano && !skipPlano) {
        if (info) {
            info.innerHTML = renderBoxPlanoInfo(plano, ag);
        }

        info?.querySelector("#pg-escolher-cancelar")?.addEventListener("click", fecharModalPagamento);

        info?.querySelector("#pg-escolher-plano")?.addEventListener("click", async () => {
            try {
                await API.post(`/clientes_planos/${plano.id}/usar_agendamento`, {
                    agendamento_id: Number(ag.id),
                });

                fecharModalPagamento();
                await carregarAgenda();
            } catch (err) {
                console.error(err);
                notify(err?.message || "Erro ao usar plano.", "error");
            }
        });

        info?.querySelector("#pg-escolher-normal")?.addEventListener("click", async () => {
            await abrirPagamentoNormalDireto(ag);
        });

        return;
    }

    await abrirPagamentoNormalDireto(ag);
}

async function abrirPagamentoNormalDireto(ag) {
    if (!pagamentoModalEl || !ag) return;
    if (_pg.carregando) return;

    _pg.carregando = true;
    _pg.modoEscolhido = "normal";

    preencherResumoPagamento(ag);

    const valorServicoEl = pagamentoModalEl.querySelector("#pg-valor-servico");
    if (valorServicoEl) {
        valorServicoEl.value = String(Number(ag.valor || 0).toFixed(2));
    }

    try {
        try {
            await carregarProdutosParaPagamento();
        } catch (err) {
            console.error("Erro ao carregar produtos do pagamento:", err);
            notify("Não foi possível carregar os produtos agora. O pagamento do serviço continuará disponível.", "warning");
            _pg.produtosCatalogo = [];
            const sel = pagamentoModalEl.querySelector("#pg-produto");
            if (sel) sel.innerHTML = `<option value="">Nenhum produto disponível</option>`;
        }

        try {
            await carregarComissaoParaPagamento();
        } catch (err) {
            console.error("Erro ao carregar comissão:", err);
            _pg.comissao = { ok: false, tipo: null, valor: 0, total: 0, pct: null, label: "não definida" };
            atualizarUIComissao();
        }

        renderItensProdutos();
        recalcularComissaoETotais();
    } catch (err) {
        console.error("Erro ao preparar modal de pagamento:", err);
        notify("Erro ao abrir o recebimento.", "error");
    } finally {
        togglePagamentoNormal(true);
        _pg.carregando = false;
    }
}

/* =========================
   Modal de escolha de plano
   Mantido para experiência comercial da barbearia
========================= */
function inicializarModalPlano() {
    planoModalEl = document.createElement("div");
    planoModalEl.id = "modal-plano";
    planoModalEl.style.display = "none";
    planoModalEl.style.position = "fixed";
    planoModalEl.style.inset = "0";
    planoModalEl.style.background = "rgba(0,0,0,0.45)";
    planoModalEl.style.zIndex = "9999";

    planoModalEl.innerHTML = `
        <div class="pg-card" style="
            width: min(640px, 94vw);
            max-height: 84vh;
            overflow: auto;
            background:#fff;
            border-radius: 14px;
            padding: 18px;
            margin: 7vh auto;
            box-shadow: 0 18px 50px rgba(0,0,0,.25);
            position: relative;
        ">
            <button type="button" id="pl-close" aria-label="Fechar" style="
                position:absolute; right:14px; top:10px;
                width:36px; height:36px; border-radius:10px;
                border:0; background:transparent; cursor:pointer;
                font-size:20px; line-height:1; opacity:.75;
            ">×</button>

            <div id="pl-content"></div>
        </div>
    `;

    document.body.appendChild(planoModalEl);

    planoModalEl.addEventListener("click", (e) => {
        if (e.target === planoModalEl) fecharModalPlano();
    });

    planoModalEl.querySelector("#pl-close")?.addEventListener("click", fecharModalPlano);
}

function fecharModalPlano() {
    if (!planoModalEl) return;
    planoModalEl.style.display = "none";

    const content = planoModalEl.querySelector("#pl-content");
    if (content) content.innerHTML = "";
}

async function decidirFluxoRecebimento(ag) {
    if (!ag) return;

    const plano = await buscarPlanoAtivoCliente(ag.cliente_id);

    if (plano && Number(plano.usos_restantes || 0) > 0) {
        abrirModalPlano(ag, plano);
        return;
    }

    await abrirModalPagamento(ag, { skipPlano: true });
}

function abrirModalPlano(ag, plano) {
    if (!planoModalEl) return;

    const content = planoModalEl.querySelector("#pl-content");
    if (!content) return;

    content.innerHTML = renderBoxPlanoInfo(plano, ag);

    content.querySelector("#pg-escolher-cancelar")?.addEventListener("click", fecharModalPlano);

    content.querySelector("#pg-escolher-plano")?.addEventListener("click", async () => {
        try {
            await API.post(`/clientes_planos/${plano.id}/usar_agendamento`, {
                agendamento_id: Number(ag.id),
            });

            fecharModalPlano();
            await carregarAgenda();
        } catch (err) {
            console.error(err);
            notify(err?.message || "Erro ao usar plano.", "error");
        }
    });

    content.querySelector("#pg-escolher-normal")?.addEventListener("click", async () => {
        try {
            fecharModalPlano();
            await abrirModalPagamento(ag, { skipPlano: true });
        } catch (err) {
            console.error(err);
            notify(err?.message || "Erro ao abrir pagamento.", "error");
        }
    });

    planoModalEl.style.display = "block";
}

/* =========================
   Helpers de plano
========================= */
async function buscarPlanoAtivoCliente(clienteId) {
    if (!clienteId) return null;
    try {
        const resp = await API.get(`/clientes/${clienteId}/plano_ativo`);
        return resp || null;
    } catch (_) {
        return null;
    }
}

function renderBoxPlanoInfo(plano, ag) {
    if (!plano) return "";

    const usosRestantes = Number(plano.usos_restantes || 0);
    const usosTotais = Number(plano.usos_totais || plano.usos_por_mes || 4);
    const nomePlano = plano.plano_nome || "Plano ativo";
    const nomeServico = ag?.servico || "Serviço";

    const maxDots = Math.max(4, Math.min(6, usosTotais || 4));
    const filled = usosTotais > 0
        ? Math.max(0, Math.round((usosRestantes / usosTotais) * maxDots))
        : 0;

    const dots = Array.from({ length: maxDots })
        .map((_, i) => `<span class="pg-plan-dot ${i < filled ? "on" : ""}"></span>`)
        .join("");

    return `
        <div class="pg-plan-choice">
            <div class="pg-plan-head">
                <div>
                    <h3>Cliente com Plano Ativo</h3>
                    <p>${escapeHtml(ag?.cliente || "Cliente")} possui um plano ativo. Como deseja registrar este atendimento?</p>
                </div>
            </div>

            <div class="pg-plan-summary">
                <div class="pg-plan-summary-top">
                    <div class="pg-plan-icon">🛡️</div>
                    <div>
                        <div class="pg-plan-title">${escapeHtml(nomePlano)}</div>
                        <div class="pg-plan-service">${escapeHtml(nomeServico)}</div>
                    </div>
                </div>

                <div class="pg-plan-usage">
                    <div class="pg-plan-dots">${dots}</div>
                    <div class="pg-plan-usage-text">${usosRestantes} uso(s) restante(s)</div>
                </div>
            </div>

            <div class="pg-plan-actions">
                <button type="button" class="pg-plan-card pg-plan-card--use" id="pg-escolher-plano">
                    <div class="pg-plan-card-icon">🛡️</div>
                    <div class="pg-plan-card-title">Usar Plano</div>
                </button>

                <button type="button" class="pg-plan-card pg-plan-card--normal" id="pg-escolher-normal">
                    <div class="pg-plan-card-icon">💳</div>
                    <div class="pg-plan-card-title">Cobrar Normalmente</div>
                </button>
            </div>

            <div class="pg-plan-footer">
                <button type="button" class="btn-secondary" id="pg-escolher-cancelar">Cancelar</button>
            </div>
        </div>
    `;
}

/* =========================
   Pagamento: produtos e comissão
========================= */
async function carregarProdutosParaPagamento() {
    const rows = await API.get("/produtos?ativos=1");
    const lista = Array.isArray(rows) ? rows : [];

    _pg.produtosCatalogo = lista.map((p) => (
        p ? {
            id: Number(p.id),
            nome: String(p.nome || ""),
            preco_venda: Number(p.preco_venda || 0),
            estoque_atual: Number(p.estoque_atual || 0),
            ativo: Number(p.ativo ?? 1),
        } : null
    )).filter(Boolean);

    const sel = pagamentoModalEl?.querySelector("#pg-produto");
    if (!sel) return;

    sel.innerHTML = `<option value="">Selecione um produto...</option>`;

    _pg.produtosCatalogo.forEach((p) => {
        const opt = document.createElement("option");
        opt.value = String(p.id);
        opt.textContent = `${p.nome} - ${formatBRL(p.preco_venda)} (estoque ${p.estoque_atual})`;
        opt.dataset.preco = String(p.preco_venda || 0);
        opt.dataset.estoque = String(p.estoque_atual || 0);
        sel.appendChild(opt);
    });
}

async function resolverComissaoVigente(profissional_id, dataISO) {
    try {
        const resp = await API.get(`/comissoes/fechamento?profissional_id=${profissional_id}&data=${dataISO}`);
        const payload = resp?.data ? resp.data : resp;
        const tipo = (payload?.tipo_comissao || "").toLowerCase();
        const valor = Number(payload?.valor_comissao || 0);
        if (tipo && Number.isFinite(valor)) return { tipo, valor };
    } catch (_) { }

    try {
        const rows = await API.get(`/profissionais/${profissional_id}/comissoes`);
        const lista = Array.isArray(rows) ? rows : (rows?.data ? rows.data : []);
        const clean = Array.isArray(lista) ? lista : [];

        const alvo = String(dataISO || "").slice(0, 10);

        const candidatos = clean
            .map((c) => ({
                tipo: String(c?.tipo_comissao || "").toLowerCase(),
                valor: Number(c?.valor_comissao || 0),
                desde: String(c?.vigente_desde || "").slice(0, 10),
            }))
            .filter((c) => c.tipo && c.desde && c.desde <= alvo);

        candidatos.sort((a, b) => (a.desde < b.desde ? 1 : a.desde > b.desde ? -1 : 0));

        if (candidatos.length) {
            return { tipo: candidatos[0].tipo, valor: candidatos[0].valor };
        }
    } catch (_) { }

    try {
        const profs = await API.get("/profissionais");
        const lista = Array.isArray(profs) ? profs : [];
        const p = lista.find((x) => String(x?.id) === String(profissional_id));

        const tipo = String(p?.tipo_comissao || "").toLowerCase();
        const valor = Number(p?.valor_comissao || 0);

        if (tipo && Number.isFinite(valor)) return { tipo, valor };
    } catch (_) { }

    return null;
}

async function carregarComissaoParaPagamento() {
    const ag = _pg.ag;

    if (!ag || !ag.profissional_id || !ag.data) {
        _pg.comissao = { ok: false, tipo: null, valor: 0, total: 0, pct: null, label: "não definida" };
        atualizarUIComissao();
        return;
    }

    const vigente = await resolverComissaoVigente(ag.profissional_id, ag.data);

    if (!vigente || !vigente.tipo) {
        _pg.comissao = { ok: false, tipo: null, valor: 0, total: 0, pct: null, label: "não definida" };
        atualizarUIComissao();
        return;
    }

    const tipo = String(vigente.tipo || "").toLowerCase();
    const valor = Number(vigente.valor || 0);

    if (tipo === "percentual") {
        _pg.comissao = { ok: true, tipo: "percentual", valor, total: 0, pct: valor, label: `${valor}%` };
    } else if (tipo === "fixo") {
        _pg.comissao = { ok: true, tipo: "fixo", valor, total: 0, pct: null, label: `${formatBRL(valor)} (fixo)` };
    } else {
        _pg.comissao = { ok: false, tipo: null, valor: 0, total: 0, pct: null, label: "não definida" };
    }

    atualizarUIComissao();
}

function adicionarProdutoSelecionado() {
    const sel = pagamentoModalEl?.querySelector("#pg-produto");
    const qtdEl = pagamentoModalEl?.querySelector("#pg-qtd");
    if (!sel || !qtdEl) return;

    const produtoId = Number(sel.value || 0);
    if (!produtoId) return notify("Selecione um produto.", "warning");

    const qtd = Number(qtdEl.value || 0);
    if (!Number.isFinite(qtd) || qtd <= 0) return notify("Quantidade inválida.", "warning");

    const p = _pg.produtosCatalogo.find((x) => Number(x.id) === produtoId);
    if (!p) return notify("Produto inválido.", "warning");

    const ja = _pg.itens.find((x) => Number(x.produto_id) === produtoId);
    const novaQtd = (ja ? Number(ja.quantidade) : 0) + qtd;

    if (novaQtd > Number(p.estoque_atual || 0)) {
        return notify("Quantidade maior que o estoque disponível.", "warning");
    }

    if (ja) {
        ja.quantidade = novaQtd;
    } else {
        _pg.itens.push({
            produto_id: Number(p.id),
            nome: p.nome,
            preco_unit: Number(p.preco_venda || 0),
            quantidade: qtd,
            estoque_atual: Number(p.estoque_atual || 0),
        });
    }

    qtdEl.value = "1";

    renderItensProdutos();
    recalcularComissaoETotais();
}

function removerItemProduto(produtoId) {
    _pg.itens = _pg.itens.filter((x) => Number(x.produto_id) !== Number(produtoId));
    renderItensProdutos();
    recalcularComissaoETotais();
}

function renderItensProdutos() {
    const box = pagamentoModalEl?.querySelector("#pg-itens");
    if (!box) return;

    if (!_pg.itens.length) {
        box.innerHTML = `
            <div style="
                border: 1px dashed #e3e3e3; border-radius: 12px;
                padding: 12px; opacity:.75; font-size:13px;
            ">Nenhum produto adicionado.</div>
        `;
        return;
    }

    box.innerHTML = _pg.itens.map((it) => {
        const subtotal = Number(it.preco_unit || 0) * Number(it.quantidade || 0);

        return `
            <div style="
                display:flex; align-items:center; justify-content:space-between; gap:12px;
                padding: 10px 12px; border: 1px solid #eee; border-radius: 12px; margin-bottom: 8px;
            ">
                <div style="min-width:0;">
                    <div style="font-weight:800;">${escapeHtml(it.nome)}</div>
                    <div style="font-size:12px; opacity:.75; margin-top:2px;">
                        ${it.quantidade} × ${formatBRL(it.preco_unit)} = <strong>${formatBRL(subtotal)}</strong>
                    </div>
                </div>

                <button type="button" data-rm="${it.produto_id}" aria-label="Remover" style="
                    width:38px; height:38px; border-radius:12px;
                    border:0; background:#f3f4f6; cursor:pointer; font-size:16px;
                ">🗑</button>
            </div>
        `;
    }).join("");

    box.querySelectorAll("button[data-rm]").forEach((btn) => {
        btn.addEventListener("click", () => removerItemProduto(btn.getAttribute("data-rm")));
    });
}

function recalcularComissaoETotais() {
    const valorServicoEl = pagamentoModalEl?.querySelector("#pg-valor-servico");
    const valorServico = valorServicoEl ? Number(valorServicoEl.value || 0) : 0;

    let comVal = 0;

    if (_pg.comissao?.ok) {
        if (_pg.comissao.tipo === "percentual") {
            comVal = valorServico * (Number(_pg.comissao.valor || 0) / 100);
        } else if (_pg.comissao.tipo === "fixo") {
            comVal = Number(_pg.comissao.valor || 0);
        }
    }

    _pg.comissao.total = Number.isFinite(comVal) ? comVal : 0;

    const subtotalProdutos = _pg.itens.reduce(
        (s, it) => s + Number(it.preco_unit || 0) * Number(it.quantidade || 0),
        0
    );

    const total = Number(valorServico || 0) + Number(subtotalProdutos || 0);

    const subEl = pagamentoModalEl?.querySelector("#pg-subtotal-prod");
    if (subEl) subEl.textContent = formatBRL(subtotalProdutos);

    const totalEl = pagamentoModalEl?.querySelector("#pg-total");
    if (totalEl) totalEl.textContent = formatBRL(total);

    const boxSub = pagamentoModalEl?.querySelector("#pg-box-comissao-sub");
    if (boxSub) boxSub.textContent = `Calculado sobre o valor do serviço: ${formatBRL(valorServico)}`;

    const boxVal = pagamentoModalEl?.querySelector("#pg-box-comissao-val");
    if (boxVal) boxVal.textContent = formatBRL(_pg.comissao.total || 0);

    const boxTitle = pagamentoModalEl?.querySelector("#pg-box-comissao-title");
    if (boxTitle) {
        const label = _pg.comissao?.ok ? `Comissão (${_pg.comissao.label})` : "Comissão";
        boxTitle.textContent = label;
    }

    const comLabel = pagamentoModalEl?.querySelector("#pg-comissao-label");
    if (comLabel) {
        comLabel.textContent = _pg.comissao?.ok
            ? `Comissão (somente serviço): ${formatBRL(_pg.comissao.total)}`
            : "Comissão (somente serviço): não definida";
    }
}

function atualizarUIComissao() {
    recalcularComissaoETotais();
}

async function confirmarPagamento() {
    const id = pagamentoModalEl?.dataset?.id;
    if (!id) throw new Error("Agendamento inválido.");

    const forma = pagamentoModalEl.querySelector("#pg-forma")?.value || "";
    if (!forma) return notify("Selecione a forma de pagamento.", "warning");

    const valorServicoEl = pagamentoModalEl.querySelector("#pg-valor-servico");
    const valor_servico = valorServicoEl ? Number(valorServicoEl.value || 0) : 0;

    if (!Number.isFinite(valor_servico) || valor_servico <= 0) {
        return notify("Valor do serviço inválido.", "warning");
    }

    const produtos = _pg.itens.map((it) => ({
        produto_id: Number(it.produto_id),
        quantidade: Number(it.quantidade),
    }));

    await API.post(`/agendamentos/${id}/pagar`, {
        forma_pagamento: forma,
        valor_servico,
        produtos,
        data_hora: null,
    });

    fecharModalPagamento();
    await carregarAgenda();
}