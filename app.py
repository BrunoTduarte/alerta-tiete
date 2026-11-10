"""
app.py
Ponto de entrada do Alerta Tietê.

    python app.py

Sobe três coisas:
1. conexão com o MySQL (pool de conexões) + limpeza de dados antigos (LGPD);
2. servidor de alertas por socket TCP (thread em segundo plano);
3. API Flask + interface web em http://127.0.0.1:5000
"""
import sys
import threading
import time

from flask import Flask, jsonify, render_template, request
from werkzeug.exceptions import HTTPException

import database
from alertas_socket import ServidorAlertas, definir_servidor
from clima import ErroServicoExterno
from config import Config, ErroConfiguracao
from logs_app import configurar_log, registrar, registrar_erro_interno
from rotas import api
from seguranca import LimitadorRequisicoes, aplicar_cabecalhos
from validacao import ErroValidacao

TAMANHO_MAX_CORPO = 16 * 1024  # 16 KB: mais que suficiente para um reporte

MENSAGENS_HTTP = {
    400: "Requisição inválida.",
    401: "Não autorizado.",
    404: "Recurso não encontrado.",
    405: "Método não permitido.",
    413: "Corpo da requisição muito grande.",
    415: "Envie os dados em JSON (Content-Type: application/json).",
}


def registrar_tratadores_de_erro(app):
    """Respostas de erro SEMPRE genéricas: nada de traceback, nome de tabela ou versão."""

    @app.errorhandler(ErroValidacao)
    def erro_validacao(erro):
        registrar("VALIDAR_ENTRADA", "INVALIDO", rota=request.path, campos=",".join(erro.erros))
        return jsonify({"erro": "Dados inválidos.", "detalhes": erro.erros}), 400

    @app.errorhandler(database.ErroBanco)
    def erro_banco(erro):
        registrar_erro_interno("BANCO", erro)
        return jsonify({"erro": "Serviço temporariamente indisponível."}), 503

    @app.errorhandler(ErroServicoExterno)
    def erro_externo(erro):
        registrar("CONSULTAR_PREVISAO", "FALHA", motivo=type(erro.__cause__ or erro).__name__)
        return jsonify({"erro": "Previsão do tempo indisponível no momento."}), 503

    @app.errorhandler(HTTPException)
    def erro_http(erro):
        mensagem = MENSAGENS_HTTP.get(erro.code, "Erro na requisição.")
        return jsonify({"erro": mensagem}), erro.code

    @app.errorhandler(Exception)
    def erro_inesperado(erro):
        registrar_erro_interno(request.path, erro)  # detalhe só no arquivo de log
        return jsonify({"erro": "Erro interno. Tente novamente mais tarde."}), 500


def aplicar_retencao():
    """Apaga dados que já passaram do prazo (LGPD) e registra no log."""
    try:
        apagados = database.aplicar_retencao()
        registrar("APLICAR_RETENCAO", "SUCESSO", **apagados)
    except database.ErroBanco as erro:
        registrar_erro_interno("APLICAR_RETENCAO", erro)


def agendar_retencao(intervalo_segundos=3600):
    """Thread em segundo plano que roda a retenção a cada 1 hora."""
    def ciclo():
        while True:
            time.sleep(intervalo_segundos)
            aplicar_retencao()
    threading.Thread(target=ciclo, daemon=True).start()


def criar_app(config, fabrica_conexao=None):
    """Monta o app Flask. Os testes passam uma fábrica de conexões falsa (SQLite em memória)."""
    app = Flask(__name__)
    app.json.ensure_ascii = False  # acentos legíveis no JSON
    app.config["MAX_CONTENT_LENGTH"] = TAMANHO_MAX_CORPO
    app.config["AGENTE_TOKEN"] = config.AGENTE_TOKEN
    app.config["LIMITADOR"] = LimitadorRequisicoes(config.LIMITE_POSTS_POR_MINUTO)
    app.config["OPEN_METEO_TIMEOUT"] = config.OPEN_METEO_TIMEOUT

    configurar_log(config.LOG_ARQUIVO)
    database.conectar(config, fabrica=fabrica_conexao)
    aplicar_retencao()

    app.register_blueprint(api)
    registrar_tratadores_de_erro(app)
    app.after_request(aplicar_cabecalhos)

    @app.get("/")
    def pagina_inicial():
        return render_template("index.html")

    return app


def main():
    try:
        config = Config()
    except ErroConfiguracao as erro:
        print(f"[ERRO] Configuração: {erro}")
        sys.exit(1)

    try:
        app = criar_app(config)
    except database.ErroBanco:
        print("[ERRO] Não foi possível acessar o MySQL. Confira se ele está rodando, "
              "se o schema.sql foi executado e se usuário/senha do .env estão certos.")
        sys.exit(1)

    servidor = ServidorAlertas(config.SOCKET_HOST, config.SOCKET_PORT, config.SOCKET_TOKEN)
    try:
        servidor.iniciar()
    except OSError:
        print(f"[ERRO] Porta {config.SOCKET_PORT} do socket ocupada. Troque SOCKET_PORT no .env.")
        sys.exit(1)
    definir_servidor(servidor)
    agendar_retencao()

    print(f"Alerta Tietê rodando em http://{config.FLASK_HOST}:{config.FLASK_PORT}")
    print(f"Servidor de alertas TCP em {config.SOCKET_HOST}:{servidor.porta}")
    registrar("INICIAR_SISTEMA", "SUCESSO")
    try:
        # debug=False: nunca expor o debugger do Werkzeug (permite executar código)
        app.run(host=config.FLASK_HOST, port=config.FLASK_PORT, debug=False, use_reloader=False)
    finally:
        servidor.parar()
        registrar("ENCERRAR_SISTEMA", "SUCESSO")


if __name__ == "__main__":
    main()
