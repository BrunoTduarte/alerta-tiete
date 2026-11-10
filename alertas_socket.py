"""
alertas_socket.py
Módulo de sockets TCP: servidor que empurra alertas em tempo real.

Quem se conecta: um painel da Defesa Civil, um líder comunitário ou uma rádio
de bairro (simulados pelo cliente_alertas.py).

Protocolo simples, uma mensagem JSON por linha:
1. cliente conecta e envia o token:   TOKEN <valor>\\n
2. servidor responde:                 OK\\n   ou   NEGADO\\n (e fecha)
3. a partir daí o servidor envia:     {"tipo": "nova_ocorrencia", ...}\\n

Segurança:
* escuta em 127.0.0.1 por padrão (não fica exposto na rede);
* exige token, comparado com hmac.compare_digest (tempo constante, evita timing attack);
* 5 s para autenticar, senão a conexão cai (evita conexões "penduradas");
* limite de clientes simultâneos (evita esgotar recursos).
"""
import hmac
import json
import socket
import threading

from logs_app import registrar

TEMPO_AUTENTICACAO = 5
MAX_CLIENTES = 20


class ServidorAlertas:
    def __init__(self, host, porta, token, max_clientes=MAX_CLIENTES):
        self.host = host
        self.porta = porta
        self._token = token.encode("utf-8")
        self.max_clientes = max_clientes
        self._clientes = []             # sockets autenticados
        self._trava = threading.Lock()  # protege a lista entre threads
        self._socket = None
        self._rodando = False

    def iniciar(self):
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # TCP / IPv4
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket.bind((self.host, self.porta))
        self._socket.listen()
        self.porta = self._socket.getsockname()[1]  # útil quando a porta é 0 (testes)
        self._rodando = True
        threading.Thread(target=self._aceitar, daemon=True).start()
        registrar("SOCKET_INICIAR", "SUCESSO", porta=self.porta)

    def _aceitar(self):
        while self._rodando:
            try:
                conexao, endereco = self._socket.accept()
            except OSError:
                break  # socket fechado em parar()
            threading.Thread(
                target=self._autenticar, args=(conexao, endereco), daemon=True
            ).start()

    def _autenticar(self, conexao, endereco):
        try:
            conexao.settimeout(TEMPO_AUTENTICACAO)
            linha = conexao.recv(256).decode("utf-8", errors="ignore").strip()
            token_recebido = linha[len("TOKEN "):] if linha.startswith("TOKEN ") else ""

            with self._trava:
                lotado = len(self._clientes) >= self.max_clientes
            valido = hmac.compare_digest(token_recebido.encode("utf-8"), self._token)

            if not valido or lotado:
                conexao.sendall(b"NEGADO\n")
                conexao.close()
                registrar("SOCKET_CONECTAR", "NEGADO",
                          motivo="lotado" if lotado else "token invalido")
                return

            conexao.settimeout(None)
            conexao.sendall(b"OK\n")
            with self._trava:
                self._clientes.append(conexao)
            registrar("SOCKET_CONECTAR", "SUCESSO", clientes=len(self._clientes))
        except OSError:
            conexao.close()
            registrar("SOCKET_CONECTAR", "FALHA", motivo="timeout ou desconexao")

    def transmitir(self, evento):
        """Envia o evento para todos os clientes conectados; remove os que caíram."""
        mensagem = (json.dumps(evento, ensure_ascii=False) + "\n").encode("utf-8")
        with self._trava:
            clientes = list(self._clientes)
        caidos = []
        for cliente in clientes:
            try:
                cliente.sendall(mensagem)
            except OSError:
                caidos.append(cliente)
        if caidos:
            with self._trava:
                for cliente in caidos:
                    if cliente in self._clientes:
                        self._clientes.remove(cliente)
                    cliente.close()
        registrar("SOCKET_TRANSMITIR", "SUCESSO", tipo=evento.get("tipo"),
                  destinatarios=len(clientes) - len(caidos))

    def total_clientes(self):
        with self._trava:
            return len(self._clientes)

    def parar(self):
        self._rodando = False
        if self._socket:
            self._socket.close()
        with self._trava:
            for cliente in self._clientes:
                cliente.close()
            self._clientes.clear()


# Instância usada pela API. Fica None até o app.py iniciar o servidor.
_servidor = None


def definir_servidor(servidor):
    global _servidor
    _servidor = servidor


def notificar(evento):
    """Chamado pelas rotas. Se o servidor não estiver ligado, simplesmente não faz nada."""
    if _servidor is not None:
        _servidor.transmitir(evento)
