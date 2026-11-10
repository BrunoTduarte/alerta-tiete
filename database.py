"""
database.py
Acesso ao MySQL com mysql-connector-python: SQL puro, sem ORM.

Consultas parametrizadas: TODO valor vindo de fora entra como parâmetro (%s).
O driver manda o valor separado do comando SQL, então ele nunca vira código
(é isso que impede SQL injection). Exemplo:
    cursor.execute("SELECT ... WHERE id = %s", (id_ocorrencia,))

Nomes de coluna nunca vêm do usuário: no UPDATE, os nomes saem da lista fixa
COLUNAS_ATUALIZAVEIS; só os VALORES são parâmetros.

Tabelas (criadas pelo schema.sql): cidades, ocorrencias, alertas.
"""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from functools import wraps

import mysql.connector
from mysql.connector import pooling

from cidades import CIDADES

DIAS_RETENCAO_RESOLVIDAS = 30
DIAS_RETENCAO_ALERTAS = 90
COLUNAS_ATUALIZAVEIS = ("nivel", "descricao", "status")

SELECT_OCORRENCIA = (
    "SELECT o.id, o.cidade, c.nome AS cidade_nome, o.bairro, o.nivel, o.descricao, "
    "o.status, o.criado_em, o.atualizado_em "
    "FROM ocorrencias o JOIN cidades c ON c.chave = o.cidade"
)
SELECT_ALERTA = (
    "SELECT a.id, a.cidade, c.nome AS cidade_nome, a.nivel, a.nivel_nome, a.chuva_24h_mm, "
    "a.chuva_max_hora_mm, a.ocorrencias_ativas, a.orientacao, a.criado_em "
    "FROM alertas a JOIN cidades c ON c.chave = a.cidade"
)

_fabrica_conexao = None  # função que devolve uma conexão (do pool, ou falsa nos testes)


class ErroBanco(Exception):
    """Falha de banco. A mensagem para o cliente é sempre genérica."""


def _protegido(funcao):
    """Decorator: transforma qualquer erro do MySQL em ErroBanco."""

    @wraps(funcao)
    def envoltorio(*args, **kwargs):
        try:
            return funcao(*args, **kwargs)
        except mysql.connector.Error as exc:
            raise ErroBanco("Falha ao acessar o banco") from exc

    return envoltorio


def agora():
    """Hora atual em UTC, sem fuso (é assim que o DATETIME do MySQL guarda)."""
    return datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)


def como_utc(data):
    if data is not None and data.tzinfo is None:
        return data.replace(tzinfo=timezone.utc)
    return data


@_protegido
def conectar(config, fabrica=None):
    """Cria o pool de conexões. Nos testes recebemos uma fábrica falsa (SQLite)."""
    global _fabrica_conexao
    if fabrica is None:
        pool = pooling.MySQLConnectionPool(
            pool_name="alerta_tiete",
            pool_size=10,
            host=config.MYSQL_HOST,
            port=config.MYSQL_PORT,
            user=config.MYSQL_USER,
            password=config.MYSQL_PASSWORD,
            database=config.MYSQL_DATABASE,
            charset="utf8mb4",
            autocommit=True,  # cada uso abre a própria transação em _transacao()
            connection_timeout=5,
        )
        fabrica = pool.get_connection
    _fabrica_conexao = fabrica
    preparar_banco()


@contextmanager
def _transacao():
    """Abre conexão + transação, faz commit no fim ou rollback se der erro, e devolve ao pool.
    A transação explícita garante que cada operação enxerga os dados mais recentes."""
    conexao = _fabrica_conexao()
    conexao.start_transaction()
    cursor = conexao.cursor(dictionary=True)  # linhas como dicionário {coluna: valor}
    try:
        yield cursor
        conexao.commit()
    except Exception:
        conexao.rollback()
        raise
    finally:
        cursor.close()
        conexao.close()  # com pool, close() devolve a conexão em vez de fechar


@_protegido
def preparar_banco():
    """Confere se as tabelas existem e sincroniza a tabela cidades com cidades.py."""
    with _transacao() as cursor:
        for chave, dados in CIDADES.items():
            cursor.execute("SELECT chave FROM cidades WHERE chave = %s", (chave,))
            if cursor.fetchone():
                cursor.execute(
                    "UPDATE cidades SET nome = %s, lat = %s, lon = %s WHERE chave = %s",
                    (dados["nome"], dados["lat"], dados["lon"], chave),
                )
            else:
                cursor.execute(
                    "INSERT INTO cidades (chave, nome, lat, lon) VALUES (%s, %s, %s, %s)",
                    (chave, dados["nome"], dados["lat"], dados["lon"]),
                )


def serializar(linha):
    """Converte datas e decimais para tipos que viram JSON."""
    if linha is None:
        return None
    saida = {}
    for coluna, valor in linha.items():
        if isinstance(valor, datetime):
            saida[coluna] = como_utc(valor).isoformat()
        elif isinstance(valor, Decimal):
            saida[coluna] = float(valor)
        else:
            saida[coluna] = valor
    return saida


# ---------------- Ocorrências (CRUD) ----------------

@_protegido
def criar_ocorrencia(dados):
    momento = agora()
    with _transacao() as cursor:
        cursor.execute(
            "INSERT INTO ocorrencias (cidade, bairro, nivel, descricao, status, criado_em, atualizado_em) "
            "VALUES (%s, %s, %s, %s, 'aberta', %s, %s)",
            (dados["cidade"], dados["bairro"], dados["nivel"], dados["descricao"], momento, momento),
        )
        novo_id = cursor.lastrowid
        cursor.execute(SELECT_OCORRENCIA + " WHERE o.id = %s", (novo_id,))
        return cursor.fetchone()


@_protegido
def listar_ocorrencias(filtros, limite=100):
    # As condições são textos FIXOS; os valores filtrados entram como parâmetros
    condicoes, parametros = [], []
    if "cidade" in filtros:
        condicoes.append("o.cidade = %s")
        parametros.append(filtros["cidade"])
    if "status" in filtros:
        condicoes.append("o.status = %s")
        parametros.append(filtros["status"])

    sql = SELECT_OCORRENCIA
    if condicoes:
        sql += " WHERE " + " AND ".join(condicoes)
    sql += " ORDER BY o.criado_em DESC, o.id DESC LIMIT %s"
    parametros.append(limite)

    with _transacao() as cursor:
        cursor.execute(sql, tuple(parametros))
        return cursor.fetchall()


@_protegido
def buscar_ocorrencia(id_ocorrencia):
    with _transacao() as cursor:
        cursor.execute(SELECT_OCORRENCIA + " WHERE o.id = %s", (id_ocorrencia,))
        return cursor.fetchone()


@_protegido
def atualizar_ocorrencia(id_ocorrencia, campos):
    """Atualiza só as colunas permitidas. Devolve a linha nova ou None se não existe."""
    alteracoes = {coluna: campos[coluna] for coluna in COLUNAS_ATUALIZAVEIS if coluna in campos}
    alteracoes["atualizado_em"] = agora()
    if campos.get("status") == "resolvida":
        # LGPD: ocorrência resolvida não precisa ficar para sempre
        alteracoes["expira_em"] = agora() + timedelta(days=DIAS_RETENCAO_RESOLVIDAS)
    elif "status" in campos:
        alteracoes["expira_em"] = None

    # Nomes de coluna vêm da lista fixa acima; valores vão como parâmetros
    trecho_set = ", ".join(f"{coluna} = %s" for coluna in alteracoes)
    with _transacao() as cursor:
        cursor.execute(
            f"UPDATE ocorrencias SET {trecho_set} WHERE id = %s",
            (*alteracoes.values(), id_ocorrencia),
        )
        cursor.execute(SELECT_OCORRENCIA + " WHERE o.id = %s", (id_ocorrencia,))
        return cursor.fetchone()


@_protegido
def excluir_ocorrencia(id_ocorrencia):
    with _transacao() as cursor:
        cursor.execute("DELETE FROM ocorrencias WHERE id = %s", (id_ocorrencia,))
        return cursor.rowcount == 1


@_protegido
def contar_ativas(cidade):
    """Ocorrências ainda não resolvidas naquela cidade."""
    with _transacao() as cursor:
        cursor.execute(
            "SELECT COUNT(*) AS total FROM ocorrencias "
            "WHERE cidade = %s AND status IN ('aberta', 'em_atendimento')",
            (cidade,),
        )
        return int(cursor.fetchone()["total"])


# ---------------- Alertas ----------------

@_protegido
def registrar_alerta(alerta):
    with _transacao() as cursor:
        cursor.execute(
            "INSERT INTO alertas (cidade, nivel, nivel_nome, chuva_24h_mm, chuva_max_hora_mm, "
            "ocorrencias_ativas, orientacao, criado_em) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (alerta["cidade"], alerta["nivel"], alerta["nivel_nome"], alerta["chuva_24h_mm"],
             alerta["chuva_max_hora_mm"], alerta["ocorrencias_ativas"], alerta["orientacao"], agora()),
        )
        novo_id = cursor.lastrowid
        cursor.execute(SELECT_ALERTA + " WHERE a.id = %s", (novo_id,))
        return cursor.fetchone()


@_protegido
def ultimo_alerta(cidade):
    with _transacao() as cursor:
        cursor.execute(
            SELECT_ALERTA + " WHERE a.cidade = %s ORDER BY a.criado_em DESC, a.id DESC LIMIT 1",
            (cidade,),
        )
        return cursor.fetchone()


@_protegido
def listar_alertas(limite=20):
    with _transacao() as cursor:
        cursor.execute(SELECT_ALERTA + " ORDER BY a.criado_em DESC, a.id DESC LIMIT %s", (limite,))
        return cursor.fetchall()


# ---------------- Retenção (LGPD) ----------------

@_protegido
def aplicar_retencao():
    """Apaga ocorrências resolvidas há mais de 30 dias e alertas com mais de 90 dias."""
    momento = agora()
    with _transacao() as cursor:
        cursor.execute(
            "DELETE FROM ocorrencias WHERE expira_em IS NOT NULL AND expira_em < %s", (momento,)
        )
        ocorrencias = cursor.rowcount
        cursor.execute(
            "DELETE FROM alertas WHERE criado_em < %s",
            (momento - timedelta(days=DIAS_RETENCAO_ALERTAS),),
        )
        return {"ocorrencias": ocorrencias, "alertas": cursor.rowcount}
