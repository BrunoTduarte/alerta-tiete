-- =====================================================================
-- schema.sql : banco do Alerta Tietê (MySQL 8)
-- Rode UMA vez como root (MySQL Workbench ou terminal):
--     mysql -u root -p < schema.sql
-- ANTES de rodar, troque as DUAS ocorrências de 'TROQUE_ESTA_SENHA' no fim do arquivo
-- e coloque a mesma senha em MYSQL_PASSWORD no .env.
-- =====================================================================

CREATE DATABASE IF NOT EXISTS alerta_tiete
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE alerta_tiete;

-- Cidades atendidas (a aplicação sincroniza esta tabela com cidades.py ao iniciar)
CREATE TABLE IF NOT EXISTS cidades (
  chave VARCHAR(40)  NOT NULL,
  nome  VARCHAR(60)  NOT NULL,
  lat   DECIMAL(8,5) NOT NULL,
  lon   DECIMAL(8,5) NOT NULL,
  PRIMARY KEY (chave)
);

-- Pontos de alagamento reportados pelos moradores (sem nenhum dado pessoal)
CREATE TABLE IF NOT EXISTS ocorrencias (
  id            INT UNSIGNED     NOT NULL AUTO_INCREMENT,
  cidade        VARCHAR(40)      NOT NULL,
  bairro        VARCHAR(60)      NOT NULL,
  nivel         TINYINT UNSIGNED NOT NULL,
  descricao     VARCHAR(280)     NOT NULL DEFAULT '',
  status        ENUM('aberta', 'em_atendimento', 'resolvida') NOT NULL DEFAULT 'aberta',
  criado_em     DATETIME         NOT NULL,
  atualizado_em DATETIME         NOT NULL,
  expira_em     DATETIME         NULL,          -- preenchido ao resolver (retenção LGPD)
  PRIMARY KEY (id),
  CONSTRAINT fk_ocorrencia_cidade FOREIGN KEY (cidade) REFERENCES cidades (chave),
  CONSTRAINT ck_ocorrencia_nivel CHECK (nivel BETWEEN 1 AND 3),
  INDEX idx_ocorrencia_cidade_status (cidade, status),
  INDEX idx_ocorrencia_criado (criado_em),
  INDEX idx_ocorrencia_expira (expira_em)
);

-- Histórico de alertas emitidos (apagado depois de 90 dias)
CREATE TABLE IF NOT EXISTS alertas (
  id                 INT UNSIGNED     NOT NULL AUTO_INCREMENT,
  cidade             VARCHAR(40)      NOT NULL,
  nivel              TINYINT UNSIGNED NOT NULL,
  nivel_nome         VARCHAR(20)      NOT NULL,
  chuva_24h_mm       DECIMAL(6,1)     NOT NULL,
  chuva_max_hora_mm  DECIMAL(6,1)     NOT NULL,
  ocorrencias_ativas INT UNSIGNED     NOT NULL,
  orientacao         VARCHAR(200)     NOT NULL,
  criado_em          DATETIME         NOT NULL,
  PRIMARY KEY (id),
  CONSTRAINT fk_alerta_cidade FOREIGN KEY (cidade) REFERENCES cidades (chave),
  CONSTRAINT ck_alerta_nivel CHECK (nivel BETWEEN 0 AND 3),
  INDEX idx_alerta_cidade_data (cidade, criado_em)
);

-- Usuário da aplicação com MENOR PRIVILÉGIO:
-- só lê e grava dados; não pode apagar tabela, alterar estrutura nem dar permissão.
-- Criado para 'localhost' e '127.0.0.1' porque o MySQL trata os dois como origens diferentes.
CREATE USER IF NOT EXISTS 'alerta_app'@'localhost' IDENTIFIED BY 'TROQUE_ESTA_SENHA';
CREATE USER IF NOT EXISTS 'alerta_app'@'127.0.0.1' IDENTIFIED BY 'TROQUE_ESTA_SENHA';
GRANT SELECT, INSERT, UPDATE, DELETE ON alerta_tiete.* TO 'alerta_app'@'localhost';
GRANT SELECT, INSERT, UPDATE, DELETE ON alerta_tiete.* TO 'alerta_app'@'127.0.0.1';
FLUSH PRIVILEGES;
