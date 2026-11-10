"""
cidades.py
Lista fechada (whitelist) das cidades atendidas no protótipo: região do Alto Tietê.

Por que lista fechada?
* validação: o usuário só escolhe cidades conhecidas;
* segurança: as coordenadas enviadas à API externa nunca vêm do usuário,
  então ninguém consegue usar o sistema para fazer consultas arbitrárias.

Coordenadas aproximadas do centro de cada município (dado geográfico público).
"""

CIDADES = {
    "suzano": {"nome": "Suzano", "lat": -23.5425, "lon": -46.3111},
    "mogi-das-cruzes": {"nome": "Mogi das Cruzes", "lat": -23.5228, "lon": -46.1883},
    "poa": {"nome": "Poá", "lat": -23.5286, "lon": -46.3439},
    "ferraz-de-vasconcelos": {"nome": "Ferraz de Vasconcelos", "lat": -23.5411, "lon": -46.3689},
    "itaquaquecetuba": {"nome": "Itaquaquecetuba", "lat": -23.4864, "lon": -46.3483},
}


def cidade_existe(chave):
    return chave in CIDADES


def nome_da_cidade(chave):
    return CIDADES[chave]["nome"]


def listar_cidades():
    """Formato usado pelo front end para montar o <select>."""
    return [{"chave": chave, "nome": dados["nome"]} for chave, dados in CIDADES.items()]
