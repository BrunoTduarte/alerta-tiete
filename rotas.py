"""
rotas.py
Endpoints da API REST (Flask Blueprint com prefixo /api).

| Método | Rota                     | Quem pode        | Sucesso |
|--------|--------------------------|------------------|---------|
| GET    | /api/cidades             | todos            | 200     |
| GET    | /api/ocorrencias         | todos            | 200     |
| GET    | /api/ocorrencias/<id>    | todos            | 200     |
| POST   | /api/ocorrencias         | todos (limitado) | 201     |
| PUT    | /api/ocorrencias/<id>    | agente (token)   | 200     |
| DELETE | /api/ocorrencias/<id>    | agente (token)   | 204     |
| GET    | /api/risco/<cidade>      | todos            | 200     |
| GET    | /api/alertas             | todos            | 200     |

Erros (tratados em app.py): 400 dados inválidos, 401 sem token, 404 não existe,
413 corpo grande, 415 não é JSON, 429 limite, 503 banco ou API externa fora.
"""
from datetime import timedelta

from flask import Blueprint, current_app, jsonify, request
from werkzeug.exceptions import NotFound, UnsupportedMediaType

import clima
import database
from alertas_socket import notificar
from cidades import listar_cidades
from logs_app import registrar
from risco import calcular_risco
from seguranca import exigir_token_agente, limitar
from validacao import (NIVEIS, ErroValidacao, validar_atualizacao, validar_criacao,
                       validar_filtros, validar_id)

api = Blueprint("api", __name__, url_prefix="/api")

INTERVALO_ENTRE_ALERTAS = timedelta(hours=1)


# ---------------- funções auxiliares ----------------

def _ler_json():
    """Exige Content-Type JSON e um corpo JSON válido."""
    if not request.is_json:
        raise UnsupportedMediaType()
    dados = request.get_json(silent=True)
    if dados is None:
        raise ErroValidacao({"corpo": "JSON inválido."})
    return dados


def _formatar(ocorrencia):
    """Linha do banco -> JSON de resposta (com textos prontos para a tela)."""
    saida = database.serializar(ocorrencia)
    saida["nivel_texto"] = NIVEIS.get(saida["nivel"], "")
    return saida


def _buscar_ou_404(id_texto):
    ocorrencia = database.buscar_ocorrencia(validar_id(id_texto))
    if ocorrencia is None:
        raise NotFound()
    return ocorrencia


def _emitir_alerta_se_preciso(cidade, risco):
    """Grava e transmite alerta quando o risco é ALERTA ou EMERGENCIA (sem repetir a cada consulta)."""
    if risco["nivel"] < 2:
        return False
    ultimo = database.ultimo_alerta(cidade)
    if ultimo and ultimo.get("nivel") == risco["nivel"]:
        if database.agora() - ultimo["criado_em"] < INTERVALO_ENTRE_ALERTAS:
            return False  # mesmo nível há menos de 1 h: não repete

    alerta = {
        "cidade": cidade,
        "nivel": risco["nivel"],
        "nivel_nome": risco["nome"],
        "chuva_24h_mm": risco["chuva_24h_mm"],
        "chuva_max_hora_mm": risco["chuva_max_hora_mm"],
        "ocorrencias_ativas": risco["ocorrencias_ativas"],
        "orientacao": risco["orientacao"],
    }
    salvo = database.registrar_alerta(alerta)
    notificar({"tipo": "alerta_risco", **database.serializar(salvo)})
    registrar("EMITIR_ALERTA", "SUCESSO", cidade=cidade, nivel=risco["nome"])
    return True


# ---------------- rotas ----------------

@api.get("/cidades")
def listar_cidades_atendidas():
    return jsonify(listar_cidades()), 200


@api.get("/ocorrencias")
def listar_ocorrencias():
    filtros = validar_filtros(request.args)
    ocorrencias = [_formatar(o) for o in database.listar_ocorrencias(filtros)]
    registrar("LISTAR_OCORRENCIAS", "SUCESSO", total=len(ocorrencias))
    return jsonify(ocorrencias), 200


@api.get("/ocorrencias/<id_ocorrencia>")
def detalhar_ocorrencia(id_ocorrencia):
    ocorrencia = _buscar_ou_404(id_ocorrencia)
    registrar("DETALHAR_OCORRENCIA", "SUCESSO", id=id_ocorrencia)
    return jsonify(_formatar(ocorrencia)), 200


@api.post("/ocorrencias")
@limitar
def criar_ocorrencia():
    dados = validar_criacao(_ler_json())
    ocorrencia = _formatar(database.criar_ocorrencia(dados))
    registrar("CRIAR_OCORRENCIA", "SUCESSO", id=ocorrencia["id"], cidade=ocorrencia["cidade"],
              nivel=ocorrencia["nivel"])
    notificar({
        "tipo": "nova_ocorrencia",
        "id": ocorrencia["id"],
        "cidade_nome": ocorrencia["cidade_nome"],
        "bairro": ocorrencia["bairro"],
        "nivel": ocorrencia["nivel"],
        "nivel_texto": ocorrencia["nivel_texto"],
    })
    resposta = jsonify(ocorrencia)
    resposta.headers["Location"] = f"/api/ocorrencias/{ocorrencia['id']}"
    return resposta, 201


@api.put("/ocorrencias/<id_ocorrencia>")
@exigir_token_agente
def atualizar_ocorrencia(id_ocorrencia):
    numero = validar_id(id_ocorrencia)
    campos = validar_atualizacao(_ler_json())
    atualizada = database.atualizar_ocorrencia(numero, campos)
    if atualizada is None:
        raise NotFound()
    registrar("ATUALIZAR_OCORRENCIA", "SUCESSO", id=id_ocorrencia, campos=",".join(campos))
    return jsonify(_formatar(atualizada)), 200


@api.delete("/ocorrencias/<id_ocorrencia>")
@exigir_token_agente
def excluir_ocorrencia(id_ocorrencia):
    if not database.excluir_ocorrencia(validar_id(id_ocorrencia)):
        raise NotFound()
    registrar("EXCLUIR_OCORRENCIA", "SUCESSO", id=id_ocorrencia)
    return "", 204


@api.get("/risco/<cidade>")
def consultar_risco(cidade):
    filtros = validar_filtros({"cidade": cidade})  # garante que a cidade está na lista
    if not filtros:
        raise ErroValidacao({"cidade": "Cidade não atendida."})

    previsao = clima.buscar_previsao(cidade, timeout=current_app.config["OPEN_METEO_TIMEOUT"])
    ativas = database.contar_ativas(cidade)
    risco = calcular_risco([h["chuva_mm"] for h in previsao["horas"]], ativas)
    emitido = _emitir_alerta_se_preciso(cidade, risco)

    registrar("CONSULTAR_RISCO", "SUCESSO", cidade=cidade, nivel=risco["nome"])
    return jsonify({
        "cidade": cidade,
        "nome": previsao["nome"],
        "risco": risco,
        "horas": previsao["horas"],
        "fonte": previsao["fonte"],
        "alerta_emitido": emitido,
    }), 200


@api.get("/alertas")
def listar_alertas():
    alertas = [database.serializar(a) for a in database.listar_alertas()]
    return jsonify(alertas), 200
