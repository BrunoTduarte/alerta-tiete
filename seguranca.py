"""
seguranca.py
Controles de segurança da API.

1. exigir_token_agente: só a Defesa Civil (quem tem o token) altera ou exclui ocorrências.
2. LimitadorRequisicoes: limita quantos reportes um mesmo IP envia por minuto (anti spam / flood).
   O IP fica só na memória, por 60 s, e nunca é gravado no banco (LGPD).
3. aplicar_cabecalhos: cabeçalhos HTTP de proteção do navegador (CSP, anti clickjacking etc).
"""
import hmac
import threading
import time
from collections import defaultdict, deque
from functools import wraps

from flask import current_app, jsonify, request

from logs_app import registrar

CABECALHO_TOKEN = "X-Token-Agente"


def exigir_token_agente(funcao):
    """Decorator para rotas restritas. Sem token correto: 401."""

    @wraps(funcao)
    def envoltorio(*args, **kwargs):
        enviado = request.headers.get(CABECALHO_TOKEN, "")
        esperado = current_app.config["AGENTE_TOKEN"]
        # compare_digest compara em tempo constante: não vaza quantos caracteres acertou
        if not hmac.compare_digest(enviado.encode("utf-8"), esperado.encode("utf-8")):
            registrar(funcao.__name__.upper(), "NEGADO", motivo="token de agente invalido")
            return jsonify({"erro": "Não autorizado."}), 401
        return funcao(*args, **kwargs)

    return envoltorio


class LimitadorRequisicoes:
    """Janela deslizante: no máximo `limite` requisições por `janela` segundos por IP."""

    def __init__(self, limite, janela=60):
        self.limite = limite
        self.janela = janela
        self._historico = defaultdict(deque)
        self._trava = threading.Lock()

    def permitir(self, chave):
        agora = time.monotonic()
        with self._trava:
            fila = self._historico[chave]
            while fila and agora - fila[0] > self.janela:
                fila.popleft()  # descarta registros antigos
            if len(fila) >= self.limite:
                return False
            fila.append(agora)
            return True


def limitar(funcao):
    """Decorator que aplica o limitador configurado no app."""

    @wraps(funcao)
    def envoltorio(*args, **kwargs):
        limitador = current_app.config["LIMITADOR"]
        if not limitador.permitir(request.remote_addr or "desconhecido"):
            registrar(funcao.__name__.upper(), "NEGADO", motivo="limite de requisicoes")
            return jsonify({"erro": "Muitas requisições. Tente de novo em 1 minuto."}), 429
        return funcao(*args, **kwargs)

    return envoltorio


POLITICA_CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
    "connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
)


def aplicar_cabecalhos(resposta):
    resposta.headers["Content-Security-Policy"] = POLITICA_CSP
    resposta.headers["X-Content-Type-Options"] = "nosniff"
    resposta.headers["X-Frame-Options"] = "DENY"
    resposta.headers["Referrer-Policy"] = "no-referrer"
    if request.path.startswith("/api/"):
        resposta.headers["Cache-Control"] = "no-store"
    return resposta
