from flask import jsonify


def ok(data=None, mensagem=None, status=200):
    payload = {"ok": True}
    if mensagem is not None:
        payload["mensagem"] = mensagem
    if data is not None:
        payload["data"] = data
    return jsonify(payload), status


def fail(erro, status=400, details=None):
    payload = {"ok": False, "erro": str(erro)}
    if details is not None:
        payload["details"] = details
    return jsonify(payload), status
