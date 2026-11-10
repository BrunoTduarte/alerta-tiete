"""
validacao.py
Valida TODA entrada vinda do usuário antes de chegar ao banco.

Defesas implementadas:
1. Só aceita os campos esperados (bloqueia "mass assignment", ex.: mandar status ou criado_em no POST).
2. Confere o tipo de cada campo: texto tem que ser str, nível tem que ser int.
3. Tamanho máximo e caracteres permitidos (regex). Junto com as consultas
   parametrizadas do database.py, isso fecha a porta para SQL injection.
4. LGPD: recusa descrição com CPF, telefone ou e-mail (coleta mínima de dados pessoais).
"""
import re

from cidades import cidade_existe

NIVEIS = {
    1: "Água na calçada",
    2: "Rua alagada",
    3: "Intransitável / risco à vida",
}
STATUS_VALIDOS = ("aberta", "em_atendimento", "resolvida")

CAMPOS_CRIACAO = {"cidade", "bairro", "nivel", "descricao"}
CAMPOS_ATUALIZACAO = {"nivel", "descricao", "status"}

TAMANHO_MAX_DESCRICAO = 280

# Letras (com acento), números, espaço, ponto, apóstrofo e hífen, 2 a 60 caracteres
REGEX_BAIRRO = re.compile(r"^[A-Za-zÀ-ÖØ-öø-ÿ0-9 .'\-]{2,60}$")

# Padrões de dados pessoais que NÃO queremos guardar
REGEX_CPF = re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")
REGEX_TELEFONE = re.compile(r"(\(?\d{2}\)?\s?)?9?\d{4}[-\s]?\d{4}\b")
REGEX_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
REGEX_CONTROLE = re.compile(r"[\x00-\x1f\x7f]")


class ErroValidacao(Exception):
    """Guarda um dicionário {campo: mensagem} que pode ser mostrado ao usuário."""

    def __init__(self, erros):
        super().__init__("Dados inválidos")
        self.erros = erros


def _exigir_dicionario(dados):
    if not isinstance(dados, dict):
        raise ErroValidacao({"corpo": "Envie um objeto JSON."})


def _checar_campos(dados, permitidos):
    desconhecidos = set(dados) - permitidos
    if desconhecidos:
        raise ErroValidacao({"campos": f"Campos não permitidos: {', '.join(sorted(desconhecidos))}"})


def _validar_nivel(valor, erros):
    # bool é subclasse de int em Python, por isso o teste extra
    if isinstance(valor, bool) or not isinstance(valor, int) or valor not in NIVEIS:
        erros["nivel"] = "Use 1, 2 ou 3."
        return None
    return valor


def _validar_descricao(valor, erros):
    if valor is None:
        return ""
    if not isinstance(valor, str):
        erros["descricao"] = "Precisa ser texto."
        return None
    texto = REGEX_CONTROLE.sub(" ", valor).strip()
    if len(texto) > TAMANHO_MAX_DESCRICAO:
        erros["descricao"] = f"Máximo de {TAMANHO_MAX_DESCRICAO} caracteres."
        return None
    if REGEX_CPF.search(texto) or REGEX_TELEFONE.search(texto) or REGEX_EMAIL.search(texto):
        erros["descricao"] = "Não inclua CPF, telefone ou e-mail (LGPD)."
        return None
    return texto


def validar_criacao(dados):
    """Valida o corpo do POST /api/ocorrencias e devolve só os campos limpos."""
    _exigir_dicionario(dados)
    _checar_campos(dados, CAMPOS_CRIACAO)
    erros = {}

    cidade = dados.get("cidade")
    if not isinstance(cidade, str) or not cidade_existe(cidade.strip().lower()):
        erros["cidade"] = "Cidade não atendida."
    else:
        cidade = cidade.strip().lower()

    bairro = dados.get("bairro")
    if not isinstance(bairro, str) or not REGEX_BAIRRO.match(bairro.strip()):
        erros["bairro"] = "Use de 2 a 60 letras, números ou espaços."
    else:
        bairro = " ".join(bairro.split())  # tira espaços repetidos

    nivel = _validar_nivel(dados.get("nivel"), erros)
    descricao = _validar_descricao(dados.get("descricao"), erros)

    if erros:
        raise ErroValidacao(erros)
    return {"cidade": cidade, "bairro": bairro, "nivel": nivel, "descricao": descricao}


def validar_atualizacao(dados):
    """Valida o corpo do PUT. Aceita um ou mais campos entre nivel, descricao e status."""
    _exigir_dicionario(dados)
    _checar_campos(dados, CAMPOS_ATUALIZACAO)
    if not dados:
        raise ErroValidacao({"corpo": "Informe ao menos um campo: nivel, descricao ou status."})

    erros, limpo = {}, {}
    if "nivel" in dados:
        limpo["nivel"] = _validar_nivel(dados["nivel"], erros)
    if "descricao" in dados:
        limpo["descricao"] = _validar_descricao(dados["descricao"], erros)
    if "status" in dados:
        if not isinstance(dados["status"], str) or dados["status"] not in STATUS_VALIDOS:
            erros["status"] = f"Use: {', '.join(STATUS_VALIDOS)}."
        else:
            limpo["status"] = dados["status"]

    if erros:
        raise ErroValidacao(erros)
    return limpo


REGEX_ID = re.compile(r"^[0-9]{1,10}$")
ID_MAXIMO = 4_294_967_295  # limite do INT UNSIGNED no MySQL


def validar_id(texto):
    """Converte o id da URL em inteiro positivo. Id malformado vira erro 400, não 500."""
    if not isinstance(texto, str) or not REGEX_ID.match(texto):
        raise ErroValidacao({"id": "Identificador inválido."})
    numero = int(texto)
    if not 1 <= numero <= ID_MAXIMO:
        raise ErroValidacao({"id": "Identificador inválido."})
    return numero


def validar_filtros(args):
    """Valida os filtros opcionais do GET (?cidade=...&status=...)."""
    filtros, erros = {}, {}
    cidade = args.get("cidade")
    if cidade:
        if cidade_existe(cidade):
            filtros["cidade"] = cidade
        else:
            erros["cidade"] = "Cidade não atendida."
    status = args.get("status")
    if status:
        if status in STATUS_VALIDOS:
            filtros["status"] = status
        else:
            erros["status"] = f"Use: {', '.join(STATUS_VALIDOS)}."
    if erros:
        raise ErroValidacao(erros)
    return filtros
