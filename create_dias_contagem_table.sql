-- create_dias_contagem_table.sql
-- Script SQL direto para criar a tabela dias_contagem no PostgreSQL do Render

CREATE TABLE IF NOT EXISTS dias_contagem (
    id SERIAL PRIMARY KEY,
    data_contagem DATE NOT NULL UNIQUE,
    ativo BOOLEAN DEFAULT TRUE,
    observacoes TEXT
);

-- Verificar se a tabela foi criada
SELECT 'Tabela dias_contagem criada com sucesso!' as status;

-- Mostrar estrutura da tabela
\d dias_contagem;
