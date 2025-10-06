-- create_dias_semana_config.sql
-- Script SQL direto para criar a tabela dias_semana_config no PostgreSQL do Render

-- Criar a tabela
CREATE TABLE IF NOT EXISTS dias_semana_config (
    dia_id INTEGER PRIMARY KEY,
    nome_dia TEXT NOT NULL,
    ativo BOOLEAN DEFAULT TRUE
);

-- Inserir configuração dos dias da semana
INSERT INTO dias_semana_config (dia_id, nome_dia, ativo) VALUES 
(0, 'SEGUNDA-FEIRA', TRUE),
(1, 'TERÇA-FEIRA', TRUE),
(2, 'QUARTA-FEIRA', TRUE),
(4, 'SEXTA-FEIRA', TRUE),
(5, 'SÁBADO', TRUE)
ON CONFLICT (dia_id) DO NOTHING;

-- Verificar se foi criada
SELECT 'Tabela dias_semana_config criada com sucesso!' as status;

-- Mostrar dados inseridos
SELECT dia_id, nome_dia, ativo FROM dias_semana_config ORDER BY dia_id;
