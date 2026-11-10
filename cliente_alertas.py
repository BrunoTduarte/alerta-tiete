"""
cliente_alertas.py
Cliente TCP que simula o painel da Defesa Civil / líder comunitário.

Uso (com a API rodando em outro terminal):
    python cliente_alertas.py

Ele conecta no servidor de alertas, envia o token do .env e imprime cada
alerta que chegar, em tempo real.
"""
import json
import os
import socket
import sys

from dotenv import load_dotenv

ICONES = {"nova_ocorrencia": "[NOVA OCORRENCIA]", "alerta_risco": "[ALERTA DE RISCO]"}


def formatar(evento):
    tipo = ICONES.get(evento.get("tipo"), "[EVENTO]")
    if evento.get("tipo") == "nova_ocorrencia":
        return (f"{tipo} {evento.get('cidade_nome')} / {evento.get('bairro')}: "
                f"nível {evento.get('nivel')} ({evento.get('nivel_texto')})")
    if evento.get("tipo") == "alerta_risco":
        return (f"{tipo} {evento.get('cidade_nome')}: {evento.get('nivel_nome')} | "
                f"chuva 24h {evento.get('chuva_24h_mm')} mm | {evento.get('orientacao')}")
    return f"{tipo} {evento}"


def main():
    load_dotenv()
    host = os.getenv("SOCKET_HOST", "127.0.0.1")
    porta = int(os.getenv("SOCKET_PORT", "5050"))
    token = os.getenv("SOCKET_TOKEN", "")

    try:
        with socket.create_connection((host, porta), timeout=5) as conexao:
            conexao.sendall(f"TOKEN {token}\n".encode("utf-8"))
            arquivo = conexao.makefile("r", encoding="utf-8")  # lê linha a linha
            resposta = arquivo.readline().strip()
            if resposta != "OK":
                print("Conexão recusada pelo servidor (token inválido ou servidor lotado).")
                sys.exit(1)

            conexao.settimeout(None)  # depois de autenticado, espera sem limite
            print(f"Conectado em {host}:{porta}. Aguardando alertas... (Ctrl+C para sair)")
            for linha in arquivo:
                try:
                    print(formatar(json.loads(linha)))
                except json.JSONDecodeError:
                    print("Mensagem inválida recebida e ignorada.")
            print("Servidor encerrou a conexão.")
    except ConnectionRefusedError:
        print("Servidor de alertas não está rodando. Inicie a API com: python app.py")
    except (socket.timeout, TimeoutError):
        print("Tempo esgotado ao conectar.")
    except KeyboardInterrupt:
        print("\nEncerrado.")


if __name__ == "__main__":
    main()
