"""
logs_app.py
Log em arquivo com data/hora, ação e resultado.

Formato de cada linha:
2026-11-10 08:15:02 | INFO | acao=CRIAR_OCORRENCIA | resultado=SUCESSO | id=6730...

Cuidados de segurança e LGPD:
* nunca registrar a descrição digitada pelo cidadão nem tokens;
* remover quebras de linha dos valores (evita "log injection", CWE 117);
* arquivo rotativo (1 MB x 3 arquivos) para não lotar o disco.
"""
import logging
import os
from logging.handlers import RotatingFileHandler

_logger = logging.getLogger("alerta_tiete")


def configurar_log(caminho_arquivo):
    """Cria a pasta de logs (se precisar) e liga o handler de arquivo."""
    pasta = os.path.dirname(caminho_arquivo)
    if pasta:
        os.makedirs(pasta, exist_ok=True)

    # Evita handlers duplicados se a função for chamada mais de uma vez
    for handler in list(_logger.handlers):
        _logger.removeHandler(handler)
        handler.close()

    handler = RotatingFileHandler(
        caminho_arquivo, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    handler.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)s | %(message)s", "%Y-%m-%d %H:%M:%S")
    )
    _logger.addHandler(handler)
    _logger.setLevel(logging.INFO)
    _logger.propagate = False
    return _logger


def _limpar(valor):
    """Remove quebras de linha e limita o tamanho para o log não ser forjado."""
    texto = str(valor).replace("\r", " ").replace("\n", " ")
    return texto[:120]


def registrar(acao, resultado, **detalhes):
    """Registra uma ação. Ex.: registrar("EXCLUIR_OCORRENCIA", "NEGADO", motivo="token invalido")."""
    partes = [f"acao={_limpar(acao)}", f"resultado={_limpar(resultado)}"]
    partes += [f"{_limpar(chave)}={_limpar(valor)}" for chave, valor in detalhes.items()]
    nivel = logging.WARNING if resultado in ("NEGADO", "FALHA", "INVALIDO") else logging.INFO
    _logger.log(nivel, " | ".join(partes))


def registrar_erro_interno(acao, excecao):
    """Erros inesperados: o traceback vai só para o arquivo, nunca para o cliente."""
    _logger.error(
        "acao=%s | resultado=FALHA | tipo=%s", _limpar(acao), type(excecao).__name__,
        exc_info=excecao,
    )
