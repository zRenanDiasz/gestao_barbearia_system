// static/js/api.js
const API = (() => {
    // IMPORTANTE: a API está no Flask, não no Live Server
    const BASE = "http://127.0.0.1:5000";

    async function request(path, { method = "GET", body = null } = {}) {
        const headers = {};
        const hasBody = body !== null && body !== undefined;

        if (hasBody) {
            headers["Content-Type"] = "application/json";
        }

        const res = await fetch(BASE + path, {
            method,
            headers,
            body: hasBody ? JSON.stringify(body) : null,
        });

        // DELETE muitas vezes pode retornar 204 No Content
        if (res.status === 204) return null;

        // se vier HTML (ex: 404), isso evita quebrar o app sem diagnóstico
        const contentType = res.headers.get("content-type") || "";
        if (!contentType.includes("application/json")) {
            throw new Error(`Resposta inválida do servidor (${res.status}).`);
        }

        const payload = await res.json();

        // seu padrão ok/fail
        if (payload && typeof payload === "object" && "ok" in payload) {
            if (!payload.ok) throw new Error(payload.erro || payload.mensagem || "Erro.");
            return payload.data;
        }

        // fallback (se algum endpoint ainda não estiver padronizado)
        return payload;
    }

    return {
        get: (p) => request(p, { method: "GET" }),
        post: (p, b) => request(p, { method: "POST", body: b }),
        put: (p, b) => request(p, { method: "PUT", body: b }),
        delete: (p) => request(p, { method: "DELETE" }),
    };
})();
