"""
seed.py
Popula o banco com ocorrências FICTÍCIAS para demonstração.

    python seed.py

Os bairros existem, mas os relatos são inventados (nenhum dado pessoal).
Os dados passam pela mesma validação da API.
"""
import sys

import database
from config import Config, ErroConfiguracao
from validacao import ErroValidacao, validar_criacao

EXEMPLOS = [
    {"cidade": "suzano", "bairro": "Jardim São Luiz", "nivel": 3,
     "descricao": "Enxurrada forte, correnteza arrastando objetos na rua."},
    {"cidade": "suzano", "bairro": "Centro", "nivel": 2,
     "descricao": "Avenida alagada perto do viaduto, carros parados."},
    {"cidade": "suzano", "bairro": "Vila Amorim", "nivel": 1,
     "descricao": "Bueiro entupido, água chegando na calçada."},
    {"cidade": "mogi-das-cruzes", "bairro": "Brás Cubas", "nivel": 2,
     "descricao": "Rua alagada na altura da estação."},
    {"cidade": "itaquaquecetuba", "bairro": "Vila Virgínia", "nivel": 1,
     "descricao": ""},
]


def main():
    try:
        config = Config()
        database.conectar(config)
        for exemplo in EXEMPLOS:
            ocorrencia = database.criar_ocorrencia(validar_criacao(exemplo))
            print(f"Criada: {ocorrencia['bairro']} ({ocorrencia['cidade_nome']}) id={ocorrencia['id']}")
    except ErroConfiguracao as erro:
        print(f"[ERRO] Configuração: {erro}")
        sys.exit(1)
    except database.ErroBanco:
        print("[ERRO] MySQL inacessível. Confira se está rodando, se o schema.sql foi executado e o .env.")
        sys.exit(1)
    except ErroValidacao as erro:
        print(f"[ERRO] Exemplo inválido: {erro.erros}")
        sys.exit(1)


if __name__ == "__main__":
    main()
