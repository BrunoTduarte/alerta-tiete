"""
clima.py
Fonte externa de dados: API pública Open-Meteo (previsão de chuva hora a hora).

* Consumida com requests e JSON, sem chave de API.
* Licença dos dados: CC BY 4.0. Por isso a interface mostra
  "Dados meteorológicos: Open-Meteo.com" com link (atribuição obrigatória).
* Uso gratuito não comercial: até 10.000 chamadas por dia. O cache de 10 minutos
  abaixo evita chamar a API toda vez que alguém abre a página.

Segurança: a resposta de um serviço externo também é entrada não confiável,
então conferimos a estrutura e os tipos antes de usar.
"""
import time
from datetime import datetime, timedelta, timezone

import requests

from cidades import CIDADES

URL_PREVISAO = "https://api.open-meteo.com/v1/forecast"
CACHE_SEGUNDOS = 600
HORAS_ANALISADAS = 24

_cache = {}  # chave da cidade -> (momento da consulta, resultado)


class ErroServicoExterno(Exception):
    """A API externa falhou ou respondeu algo inesperado."""


def limpar_cache():
    _cache.clear()


def _numero(valor):
    """Valores nulos viram 0; qualquer coisa que não seja número é rejeitada."""
    if valor is None:
        return 0.0
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        raise ErroServicoExterno("Valor não numérico na resposta")
    return float(valor)


def _hora_local_atual(offset_segundos):
    """Hora atual no fuso da cidade, no mesmo formato da API (AAAA-MM-DDTHH:00)."""
    local = datetime.now(timezone.utc) + timedelta(seconds=offset_segundos)
    return local.strftime("%Y-%m-%dT%H:00")


def _interpretar(dados):
    """Extrai as próximas 24 horas de chuva da resposta JSON."""
    if not isinstance(dados, dict) or not isinstance(dados.get("hourly"), dict):
        raise ErroServicoExterno("Resposta sem o bloco 'hourly'")

    horario = dados["hourly"]
    tempos = horario.get("time")
    chuvas = horario.get("precipitation")
    probabilidades = horario.get("precipitation_probability") or [None] * len(tempos or [])

    if not isinstance(tempos, list) or not isinstance(chuvas, list) or not tempos:
        raise ErroServicoExterno("Listas de horário ausentes")
    if not (len(tempos) == len(chuvas) == len(probabilidades)):
        raise ErroServicoExterno("Listas com tamanhos diferentes")

    offset = dados.get("utc_offset_seconds", 0)
    if isinstance(offset, bool) or not isinstance(offset, int):
        offset = 0
    hora_atual = _hora_local_atual(offset)

    horas = []
    for tempo, chuva, prob in zip(tempos, chuvas, probabilidades):
        if not isinstance(tempo, str):
            raise ErroServicoExterno("Horário inválido")
        if tempo < hora_atual:
            continue  # ignora horas que já passaram
        horas.append({
            "hora": tempo,
            "chuva_mm": round(_numero(chuva), 1),
            "probabilidade": None if prob is None else int(_numero(prob)),
        })
        if len(horas) == HORAS_ANALISADAS:
            break

    if not horas:
        raise ErroServicoExterno("Nenhuma hora futura na resposta")
    return horas


def buscar_previsao(chave_cidade, timeout=5):
    """Devolve as próximas 24 h de chuva prevista para a cidade (com cache)."""
    cidade = CIDADES[chave_cidade]  # chave já validada pela rota

    em_cache = _cache.get(chave_cidade)
    if em_cache and time.time() - em_cache[0] < CACHE_SEGUNDOS:
        return em_cache[1]

    parametros = {
        "latitude": cidade["lat"],
        "longitude": cidade["lon"],
        "hourly": "precipitation,precipitation_probability",
        "forecast_days": 2,
        "timezone": "America/Sao_Paulo",
    }
    try:
        resposta = requests.get(URL_PREVISAO, params=parametros, timeout=timeout)
        resposta.raise_for_status()  # 4xx/5xx vira exceção
        dados = resposta.json()       # JSON inválido vira ValueError
    except (requests.RequestException, ValueError) as exc:
        raise ErroServicoExterno("Falha ao consultar a Open-Meteo") from exc

    resultado = {
        "cidade": chave_cidade,
        "nome": cidade["nome"],
        "horas": _interpretar(dados),
        "fonte": "Open-Meteo.com (CC BY 4.0)",
    }
    _cache[chave_cidade] = (time.time(), resultado)
    return resultado
