"""
config.py
Lê as configurações do arquivo .env.

Regra de segurança: nenhum segredo (URI do banco, tokens) fica escrito no código.
Se um segredo obrigatório faltar ou estiver com o valor de exemplo, o sistema
se recusa a iniciar (evita rodar com credencial padrão).
"""
import os

from dotenv import load_dotenv

load_dotenv()  # carrega o .env para as variáveis de ambiente

VALOR_EXEMPLO = "troque_este_valor"


class ErroConfiguracao(Exception):
    """Configuração ausente ou insegura."""


def _texto(nome, padrao=None, obrigatoria=False):
    valor = os.getenv(nome, padrao)
    if obrigatoria and not valor:
        raise ErroConfiguracao(f"Variável obrigatória ausente no .env: {nome}")
    return valor


def _segredo(nome):
    """Segredos precisam existir, não podem ser o valor de exemplo e precisam ter 16+ caracteres."""
    valor = _texto(nome, obrigatoria=True)
    if valor == VALOR_EXEMPLO or len(valor) < 16:
        raise ErroConfiguracao(
            f"{nome} inseguro: gere um valor forte com "
            "python -c \"import secrets; print(secrets.token_urlsafe(32))\""
        )
    return valor


def _senha_banco():
    """A senha do MySQL não pode ficar vazia nem com o valor de exemplo."""
    senha = _texto("MYSQL_PASSWORD", obrigatoria=True)
    if senha in (VALOR_EXEMPLO, "TROQUE_ESTA_SENHA"):
        raise ErroConfiguracao("MYSQL_PASSWORD ainda está com o valor de exemplo")
    return senha


def _inteiro(nome, padrao):
    try:
        return int(os.getenv(nome, padrao))
    except ValueError as exc:
        raise ErroConfiguracao(f"{nome} precisa ser um número inteiro") from exc


class Config:
    """Agrupa as configurações em um só lugar."""

    def __init__(self):
        # Banco de dados (MySQL)
        self.MYSQL_HOST = _texto("MYSQL_HOST", "127.0.0.1")
        self.MYSQL_PORT = _inteiro("MYSQL_PORT", 3306)
        self.MYSQL_USER = _texto("MYSQL_USER", obrigatoria=True)
        self.MYSQL_PASSWORD = _senha_banco()
        self.MYSQL_DATABASE = _texto("MYSQL_DATABASE", "alerta_tiete")

        # Servidor web
        self.FLASK_HOST = _texto("FLASK_HOST", "127.0.0.1")
        self.FLASK_PORT = _inteiro("FLASK_PORT", 5000)

        # Token de quem pode alterar e excluir ocorrências (Defesa Civil)
        self.AGENTE_TOKEN = _segredo("AGENTE_TOKEN")

        # Servidor de alertas por socket TCP
        self.SOCKET_HOST = _texto("SOCKET_HOST", "127.0.0.1")
        self.SOCKET_PORT = _inteiro("SOCKET_PORT", 5050)
        self.SOCKET_TOKEN = _segredo("SOCKET_TOKEN")

        # Limites e integrações
        self.LIMITE_POSTS_POR_MINUTO = _inteiro("LIMITE_POSTS_POR_MINUTO", 5)
        self.OPEN_METEO_TIMEOUT = _inteiro("OPEN_METEO_TIMEOUT", 5)
        self.LOG_ARQUIVO = _texto("LOG_ARQUIVO", "logs/app.log")
