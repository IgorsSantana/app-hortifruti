# init_db.py
import os
import sqlite3
import psycopg2
from produtos_config import PRODUTOS

# --- DEFINIÇÃO DOS USUÁRIOS ---
USUARIOS = [
    ('bcs', 'bcs123', 'loja', 'BCS'),
    ('sjn', 'sjn123', 'loja', 'SJN'),
    ('mep', 'mep123', 'loja', 'MEP'),
    ('fcl1', 'fcl123', 'loja', 'FCL1'),
    ('fcl2', 'fcl223', 'loja', 'FCL2'),
    ('fcl3', 'fcl323', 'loja', 'FCL3'),
    ('Igor', 'S4nt4n4', 'admin', None),
    ('Gabriel', 'G1a2l', 'admin', None)
]

# --- LÓGICA DE CONEXÃO E CRIAÇÃO ---
db_url = os.environ.get('DATABASE_URL')
is_postgres = bool(db_url)

conn = psycopg2.connect(db_url) if is_postgres else sqlite3.connect('hortifruti.db')
cur = conn.cursor()

# --- COMANDOS SQL PARA CRIAR AS TABELAS ---
SQL_TYPE = {
    "SERIAL_PK": "SERIAL PRIMARY KEY" if is_postgres else "INTEGER PRIMARY KEY AUTOINCREMENT",
    "TEXT_UNIQUE": "TEXT UNIQUE NOT NULL" if is_postgres else "TEXT UNIQUE NOT NULL",
    "INSERT_USER": 'INSERT INTO users (username, password, role, store_name) VALUES (%s, %s, %s, %s) ON CONFLICT (username) DO NOTHING;' if is_postgres else 'INSERT OR IGNORE INTO users (username, password, role, store_name) VALUES (?, ?, ?, ?);'
}

# Tabela de Pedidos
cur.execute(f'''
    CREATE TABLE IF NOT EXISTS pedidos (
        id {SQL_TYPE["SERIAL_PK"]},
        data_pedido TEXT NOT NULL,
        loja TEXT NOT NULL,
        produto TEXT NOT NULL,
        tipo TEXT NOT NULL,
        quantidade INTEGER NOT NULL
    );''')

# Tabela de Usuários
cur.execute(f'''
    CREATE TABLE IF NOT EXISTS users (
        id {SQL_TYPE["SERIAL_PK"]},
        username {SQL_TYPE["TEXT_UNIQUE"]},
        password TEXT NOT NULL,
        role TEXT NOT NULL,
        store_name TEXT
    );''')

# Tabela de Produtos (ATUALIZADA)
cur.execute(f'''
    CREATE TABLE IF NOT EXISTS products (
        id {SQL_TYPE["SERIAL_PK"]},
        name {SQL_TYPE["TEXT_UNIQUE"]},
        unidade_fracionada TEXT NOT NULL,
        codigo_interno TEXT UNIQUE
    );''')

# Tabela de Disponibilidade dos Produtos
cur.execute(f'''
    CREATE TABLE IF NOT EXISTS product_availability (
        product_id INTEGER NOT NULL,
        day_id INTEGER NOT NULL,
        PRIMARY KEY (product_id, day_id)
    );''')


# --- LÓGICA PARA POPULAR AS TABELAS ---

# Insere os usuários padrão
cur.executemany(SQL_TYPE["INSERT_USER"], USUARIOS)

# Migra os produtos do arquivo produtos_config.py para o banco de dados
print("Iniciando migração de produtos do arquivo de configuração...")
DIAS_MAP = {"SEGUNDA-FEIRA": 0, "TERÇA-FEIRA": 1, "QUARTA-FEIRA": 2, "SEXTA-FEIRA": 4, "SÁBADO": 5}

for dia_nome, produtos_lista in PRODUTOS.items():
    if dia_nome not in DIAS_MAP: continue
    day_id = DIAS_MAP[dia_nome]

    for produto_dict in produtos_lista:
        nome = produto_dict['nome']
        unidade = produto_dict['unidade_fracionada']
        
        # Insere o produto na tabela 'products' se ele não existir
        if is_postgres:
            cur.execute("INSERT INTO products (name, unidade_fracionada) VALUES (%s, %s) ON CONFLICT (name) DO NOTHING;", (nome, unidade))
        else: # SQLite
            cur.execute("INSERT OR IGNORE INTO products (name, unidade_fracionada) VALUES (?, ?);", (nome, unidade))
        
        # Pega o ID do produto que acabamos de inserir ou que já existia
        if is_postgres:
            cur.execute("SELECT id FROM products WHERE name = %s;", (nome,))
        else:
            cur.execute("SELECT id FROM products WHERE name = ?;", (nome,))
        
        product_id_tuple = cur.fetchone()
        if product_id_tuple:
            product_id = product_id_tuple[0] if not isinstance(product_id_tuple, dict) else product_id_tuple['id']

            # Vincula o produto ao dia da semana na tabela 'product_availability'
            if is_postgres:
                cur.execute("INSERT INTO product_availability (product_id, day_id) VALUES (%s, %s) ON CONFLICT DO NOTHING;", (product_id, day_id))
            else:
                cur.execute("INSERT OR IGNORE INTO product_availability (product_id, day_id) VALUES (?, ?);", (product_id, day_id))

print("Migração de produtos concluída.")

# Salva as mudanças e fecha a conexão
conn.commit()
cur.close()
conn.close()

print("Banco de dados e todas as tabelas foram criados/atualizados com sucesso!")
print(f"{len(USUARIOS)} usuários foram verificados/inseridos.")