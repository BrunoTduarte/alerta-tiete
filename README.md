# Alerta Tietê

Protótipo CitizenTech para **alagamentos no Alto Tietê** (Suzano, Mogi das Cruzes, Poá, Ferraz de Vasconcelos e Itaquaquecetuba).

O morador reporta o ponto alagado do seu bairro, sem informar dados pessoais. O sistema cruza esses relatos com a **previsão de chuva hora a hora** (API pública Open-Meteo) e com os **limiares de aviso do INMET**, calcula o nível de risco da cidade e **empurra alertas em tempo real por socket TCP** para quem precisa agir (Defesa Civil, líder comunitário, rádio de bairro).

Global Solution 2026 · Coding for Security · FIAP
Aluno: Bruno Tomé Duarte · RM 571712

![Tela do Alerta Tietê](docs/tela.jpg)

---

## Checklist da GS e onde está cada item

| Requisito | Onde está |
|---|---|
| API REST Flask com GET, POST, PUT, DELETE e status corretos | `rotas.py` (200, 201, 204, 400, 401, 404, 405, 413, 415, 429, 500, 503) |
| MySQL com CRUD por código Python, sem ORM | `database.py` (mysql-connector-python, SQL puro) + `schema.sql` |
| Fonte externa com requests e JSON | `clima.py` (Open-Meteo) |
| Interface web HTML/CSS que consome a API | `templates/index.html`, `static/style.css`, `static/app.js` |
| Log em arquivo com data/hora, ação e resultado | `logs_app.py` → `logs/app.log` |
| Módulo à escolha: sockets TCP | `alertas_socket.py` (servidor) e `cliente_alertas.py` (cliente) |
| Funções, módulos e tratamento de exceções | todos os arquivos; erros centralizados em `app.py` |
| Credenciais em .env | `config.py` + `.env.example` |
| Consultas parametrizadas | todo valor entra como parâmetro `%s` (`database.py`) |
| Validação de toda entrada | `validacao.py` |
| Erros sem detalhes internos | tratadores em `app.py` |
| Coleta mínima (LGPD) | sem nome, telefone ou endereço; descrição com CPF/telefone/e-mail é recusada; dados antigos são apagados automaticamente a cada 1 hora |
| Menor privilégio no banco (extra) | usuário `alerta_app` só com SELECT, INSERT, UPDATE, DELETE (`schema.sql`) |
| Testes automatizados (extra) | `tests/` (59 testes; rodam sem MySQL instalado ou contra o MySQL real) |

## Estrutura

```
alerta-tiete/
├── app.py               # ponto de entrada: sobe Flask + socket
├── rotas.py             # endpoints da API
├── database.py          # CRUD no MySQL (SQL parametrizado)
├── schema.sql           # criação do banco, tabelas e usuário da aplicação
├── validacao.py         # validação de entrada
├── clima.py             # integração Open-Meteo (requests + JSON)
├── risco.py             # regra de risco (limiares INMET)
├── alertas_socket.py    # servidor TCP de alertas
├── cliente_alertas.py   # cliente TCP (painel da Defesa Civil)
├── seguranca.py         # token de agente, limite de requisições, cabeçalhos
├── logs_app.py          # log em arquivo
├── config.py            # leitura do .env
├── cidades.py           # cidades atendidas (lista fechada)
├── seed.py              # dados fictícios de exemplo
├── templates/index.html
├── static/style.css, static/app.js
├── tests/               # testes com pytest
├── requirements.txt     # dependências do sistema
├── requirements-dev.txt # dependências dos testes
└── .env.example         # modelo de configuração (sem segredos)
```

---

## Como rodar do zero

### 1. Pré requisitos

* **Python 3.10 ou superior** (`python --version`)
* **MySQL 8** instalado pelo **MySQL Installer** (Windows), com **MySQL Server** e **MySQL Workbench**. Ele fica rodando como serviço na porta 3306.

### 2. Baixar o projeto

```bash
git clone https://github.com/SEU_USUARIO/alerta-tiete.git
cd alerta-tiete
```

| Parte | O que faz |
|---|---|
| `git clone <url>` | copia o repositório do GitHub para a sua máquina |
| `cd alerta-tiete` | entra na pasta do projeto (todos os próximos comandos rodam daqui) |

Se recebeu o .zip, é só extrair e abrir um terminal dentro da pasta.

### 3. Criar o ambiente virtual

Windows (PowerShell):
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

Linux / WSL:
```bash
python3 -m venv .venv
source .venv/bin/activate
```

| Parte | O que faz |
|---|---|
| `python -m venv` | roda o módulo `venv`, que cria um Python isolado só para este projeto |
| `.venv` | nome da pasta onde esse ambiente fica |
| `Activate.ps1` / `source .../activate` | ativa o ambiente; o terminal passa a mostrar `(.venv)` |

Se o PowerShell bloquear o script de ativação: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` (libera scripts locais só para o seu usuário).

### 4. Instalar as dependências

```bash
pip install -r requirements.txt
```

| Parte | O que faz |
|---|---|
| `pip install` | instala pacotes Python |
| `-r requirements.txt` | lê a lista de pacotes (com versões fixas) desse arquivo |

### 5. Criar o banco no MySQL

1. Abra o `schema.sql` e troque as **duas** ocorrências de `TROQUE_ESTA_SENHA` por uma senha forte (é a senha do usuário da aplicação).
2. Rode o arquivo como **root**, de um destes jeitos:

**MySQL Workbench:** conecte como root, File > Open SQL Script > `schema.sql` e clique no raio (Execute).

**Terminal:**
```bash
mysql -u root -p -e "source schema.sql"
```

| Parte | O que faz |
|---|---|
| `mysql` | cliente de linha de comando do MySQL |
| `-u root` | entra como o usuário administrador |
| `-p` | pede a senha do root |
| `-e "source schema.sql"` | executa os comandos do arquivo |

O script cria o banco `alerta_tiete`, as tabelas `cidades`, `ocorrencias` e `alertas` e o usuário `alerta_app`, que só pode ler e gravar dados (não pode apagar tabela nem mudar estrutura).

### 6. Criar o arquivo .env

Windows: `Copy-Item .env.example .env`
Linux / WSL: `cp .env.example .env`

Depois gere dois tokens fortes e cole em `AGENTE_TOKEN` e `SOCKET_TOKEN`:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

| Parte | O que faz |
|---|---|
| `python -c "..."` | executa o código entre aspas sem precisar criar arquivo |
| `secrets.token_urlsafe(32)` | gera 32 bytes aleatórios seguros, em texto que pode ir em URL/header |

Em `MYSQL_PASSWORD`, coloque a mesma senha que você colocou no `schema.sql`.

O sistema **se recusa a iniciar** se algum token estiver vazio, com o valor de exemplo ou com menos de 16 caracteres, ou se a senha do banco for a de exemplo.

### 7. (Opcional) Popular com dados fictícios

```bash
python seed.py
```
Insere 5 ocorrências inventadas em bairros do Alto Tietê, passando pela mesma validação da API.

### 8. Subir o sistema

```bash
python app.py
```

Saída esperada:
```
Alerta Tietê rodando em http://127.0.0.1:5000
Servidor de alertas TCP em 127.0.0.1:5050
```

Abra **http://127.0.0.1:5000** no navegador.

### 9. Ver os alertas em tempo real (segundo terminal)

Com o ambiente virtual ativado em outro terminal:
```bash
python cliente_alertas.py
```
Ele conecta no socket TCP com o `SOCKET_TOKEN` do .env. Agora, ao enviar um reporte pela página ou consultar uma cidade com risco ALERTA ou EMERGENCIA, a mensagem aparece nesse terminal na hora.

### 10. Rodar os testes (não precisa de MySQL)

```bash
pip install -r requirements-dev.txt
python -m pytest -v
```

| Parte | O que faz |
|---|---|
| `requirements-dev.txt` | instala o pytest |
| `python -m pytest` | roda todos os testes da pasta `tests/` |
| `-v` | mostra o nome de cada teste e se passou |

Por padrão os testes usam um SQLite em memória que imita a conexão do MySQL (os comandos SQL são os mesmos). Para rodar contra o MySQL de verdade, crie um banco **só para testes** com o `schema.sql` (as tabelas são esvaziadas a cada teste) e defina `TESTE_MYSQL_REAL=1` junto com as variáveis `MYSQL_*` dele.

---

## Endpoints

| Método | Rota | Acesso | Sucesso | Erros possíveis |
|---|---|---|---|---|
| GET | `/api/cidades` | público | 200 | |
| GET | `/api/ocorrencias?cidade=&status=` | público | 200 | 400 filtro inválido |
| GET | `/api/ocorrencias/<id>` | público | 200 | 400 id inválido, 404 |
| POST | `/api/ocorrencias` | público, 5 por minuto por IP | 201 + header Location | 400, 413, 415, 429 |
| PUT | `/api/ocorrencias/<id>` | agente (header `X-Token-Agente`) | 200 | 400, 401, 404 |
| DELETE | `/api/ocorrencias/<id>` | agente (header `X-Token-Agente`) | 204 | 401, 404 |
| GET | `/api/risco/<cidade>` | público | 200 | 400 cidade fora da lista, 503 API externa fora |
| GET | `/api/alertas` | público | 200 | |

Banco ou API externa fora do ar respondem **503** com mensagem genérica. Qualquer erro inesperado responde **500** sem traceback; o detalhe vai só para `logs/app.log`.

### Testando com curl (Linux / WSL / Git Bash)

```bash
curl -i -X POST http://127.0.0.1:5000/api/ocorrencias \
  -H "Content-Type: application/json" \
  -d '{"cidade":"suzano","bairro":"Centro","nivel":2,"descricao":"Rua alagada"}'
```

| Parte | O que faz |
|---|---|
| `-i` | mostra os cabeçalhos da resposta (dá para ver o `201 Created` e o `Location`) |
| `-X POST` | define o método HTTP |
| `-H "Content-Type: application/json"` | avisa que o corpo é JSON (sem isso a API responde 415) |
| `-d '{...}'` | corpo da requisição |

Atualizar status como agente:
```bash
curl -i -X PUT http://127.0.0.1:5000/api/ocorrencias/ID_AQUI \
  -H "Content-Type: application/json" \
  -H "X-Token-Agente: SEU_AGENTE_TOKEN" \
  -d '{"status":"resolvida"}'
```
`X-Token-Agente` é o cabeçalho que prova que é a Defesa Civil. Sem ele: 401.

No PowerShell, use `curl.exe` (o `curl` puro é um apelido de outro comando) ou teste pela própria página / Postman / Thunder Client.

---

## Modelo de dados (MySQL)

```
cidades (1) ────< (N) ocorrencias
cidades (1) ────< (N) alertas
```

**Tabela `cidades`**: `chave` (PK, ex.: `suzano`), `nome`, `lat`, `lon`. Sincronizada com `cidades.py` ao iniciar.

**Tabela `ocorrencias`**

| Coluna | Tipo | Observação |
|---|---|---|
| `id` | INT UNSIGNED, AUTO_INCREMENT | chave primária |
| `cidade` | VARCHAR(40) | FK para `cidades.chave` |
| `bairro` | VARCHAR(60) | 2 a 60 caracteres |
| `nivel` | TINYINT | CHECK 1 a 3 (1 calçada, 2 rua alagada, 3 intransitável) |
| `descricao` | VARCHAR(280) | opcional, sem dados pessoais |
| `status` | ENUM | `aberta`, `em_atendimento`, `resolvida` (definido pelo servidor) |
| `criado_em`, `atualizado_em` | DATETIME | UTC |
| `expira_em` | DATETIME NULL | preenchido ao resolver; a linha é apagada 30 dias depois |

**Tabela `alertas`**: `id`, `cidade` (FK), `nivel`, `nivel_nome`, `chuva_24h_mm`, `chuva_max_hora_mm`, `ocorrencias_ativas`, `orientacao`, `criado_em` (apagado após 90 dias).

Índices: `(cidade, status)`, `criado_em`, `expira_em` e `(cidade, criado_em)` em alertas. CHECK, ENUM e chaves estrangeiras são a segunda camada de validação, dentro do próprio banco.

## Segurança em resumo

| Ameaça | Mitigação |
|---|---|
| SQL injection | todo valor como parâmetro `%s`; regex e lista fechada na entrada; usuário do banco sem DROP/ALTER |
| Alteração ou exclusão indevida | PUT/DELETE exigem token (comparação em tempo constante com `hmac.compare_digest`) |
| Spam / flood de reportes | limite de 5 POST por minuto por IP (IP só em memória) |
| XSS na interface | `textContent` no JS + Content Security Policy sem script inline |
| Vazamento de detalhes em erro | mensagens genéricas; traceback só no log |
| Socket aberto para qualquer um | bind em 127.0.0.1, token, timeout de 5 s, limite de 20 clientes |
| Log injection | quebras de linha removidas antes de gravar |
| Dados pessoais (LGPD) | sem nome/telefone/endereço; descrição com CPF/telefone/e-mail recusada; retenção apaga dados antigos |

---

## Créditos, terceiros e uso de IA

* **Open-Meteo** (api.open-meteo.com): previsão de chuva. Dados sob licença **CC BY 4.0**, uso não comercial até 10.000 chamadas por dia. A atribuição aparece na interface.
* **INMET**: limiares dos avisos de chuvas intensas (amarelo, laranja, vermelho) usados em `risco.py`.
* Bibliotecas: Flask, mysql-connector-python, requests, python-dotenv; testes com pytest.
* Coordenadas: centro aproximado de cada município (dado geográfico público).
* **IA generativa**: o Claude (Anthropic) foi usado como assistente no desenvolvimento, conforme declarado no relatório.
