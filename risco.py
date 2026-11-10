"""
risco.py
Regra de negócio: calcula o nível de risco de alagamento de uma cidade.

Combina duas fontes:
1. Chuva prevista (Open-Meteo), usando os limiares de aviso do INMET:
   * amarelo (perigo potencial): 20 a 30 mm/h, ou até 50 mm/dia
   * laranja (perigo): 30 a 60 mm/h, ou 50 a 100 mm/dia
   * vermelho (grande perigo): acima de 60 mm/h, ou acima de 100 mm/dia
   Adaptação nossa: o INMET não fixa piso diário para o amarelo, usamos 30 mm em 24 h.
2. Relatos dos cidadãos: 3 ou mais ocorrências ativas na cidade indicam que a
   drenagem já está saturada, então o nível sobe um degrau.

Função pura (não acessa banco nem rede), por isso é fácil de testar.
"""

NIVEIS_RISCO = [
    {"nivel": 0, "nome": "NORMAL", "cor": "verde",
     "orientacao": "Sem previsão de chuva forte."},
    {"nivel": 1, "nome": "ATENCAO", "cor": "amarelo",
     "orientacao": "Chuva moderada a forte. Evite áreas que costumam alagar."},
    {"nivel": 2, "nome": "ALERTA", "cor": "laranja",
     "orientacao": "Risco de alagamentos. Não atravesse ruas alagadas e proteja documentos."},
    {"nivel": 3, "nome": "EMERGENCIA", "cor": "vermelho",
     "orientacao": "Risco alto. Procure local elevado e ligue 199 (Defesa Civil) ou 193."},
]

OCORRENCIAS_PARA_AGRAVAR = 3


def nivel_pela_chuva(total_24h, maximo_hora):
    if maximo_hora > 60 or total_24h > 100:
        return 3
    if maximo_hora >= 30 or total_24h >= 50:
        return 2
    if maximo_hora >= 20 or total_24h >= 30:
        return 1
    return 0


def calcular_risco(chuvas_mm, ocorrencias_ativas):
    """chuvas_mm: lista com a chuva prevista de cada hora (mm)."""
    total_24h = round(sum(chuvas_mm), 1)
    maximo_hora = round(max(chuvas_mm, default=0.0), 1)

    nivel = nivel_pela_chuva(total_24h, maximo_hora)
    agravado = ocorrencias_ativas >= OCORRENCIAS_PARA_AGRAVAR
    if agravado:
        nivel = min(nivel + 1, 3)

    resultado = dict(NIVEIS_RISCO[nivel])
    resultado.update({
        "chuva_24h_mm": total_24h,
        "chuva_max_hora_mm": maximo_hora,
        "ocorrencias_ativas": ocorrencias_ativas,
        "agravado_por_relatos": agravado,
    })
    return resultado
