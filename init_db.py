# init_db.py (Versão final com limpeza e recarga)
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
cur.execute(f'''CREATE TABLE IF NOT EXISTS pedidos (id {SQL_TYPE["SERIAL_PK"]}, data_pedido TEXT NOT NULL, loja TEXT NOT NULL, produto TEXT NOT NULL, tipo TEXT NOT NULL, quantidade INTEGER NOT NULL);''')
cur.execute(f'''CREATE TABLE IF NOT EXISTS users (id {SQL_TYPE["SERIAL_PK"]}, username {SQL_TYPE["TEXT_UNIQUE"]}, password TEXT NOT NULL, role TEXT NOT NULL, store_name TEXT);''')
cur.execute(f'''CREATE TABLE IF NOT EXISTS products (id {SQL_TYPE["SERIAL_PK"]}, name {SQL_TYPE["TEXT_UNIQUE"]}, unidade_fracionada TEXT NOT NULL, codigo_interno TEXT UNIQUE);''')
cur.execute(f'''CREATE TABLE IF NOT EXISTS product_availability (product_id INTEGER NOT NULL, day_id INTEGER NOT NULL, PRIMARY KEY (product_id, day_id));''')
cur.execute(f'''CREATE TABLE IF NOT EXISTS pedidos_finais (id {SQL_TYPE["SERIAL_PK"]}, data_pedido TEXT NOT NULL, produto_nome TEXT NOT NULL, loja_nome TEXT NOT NULL, quantidade_pedida INTEGER NOT NULL, UNIQUE (data_pedido, produto_nome, loja_nome));''')

# --- LÓGICA PARA POPULAR AS TABELAS ---
cur.executemany(SQL_TYPE["INSERT_USER"], USUARIOS)
conn.commit()

# --- LÓGICA DE CARGA DE PRODUTOS CORRIGIDA ---
print("Limpando dados de produtos antigos...")
cur.execute("DELETE FROM product_availability;")
cur.execute("DELETE FROM products;")

print("Verificando e carregando produtos do arquivo de configuração...")
DIAS_MAP = {"SEGUNDA-FEIRA": 0, "TERÇA-FEIRA": 1, "QUARTA-FEIRA": 2, "QUINTA-FEIRA": 3, "SEXTA-FEIRA": 4, "SÁBADO": 5}

# 1. Criar uma lista mestra de produtos únicos (por nome) para evitar duplicatas
all_products_by_name = {}
for produtos_lista in PRODUTOS.values():
    for produto_dict in produtos_lista:
        all_products_by_name[produto_dict['nome']] = produto_dict

# 2. Inserir cada produto único apenas uma vez
print(f"Inserindo {len(all_products_by_name)} produtos únicos...")
for nome, produto_info in all_products_by_name.items():
    unidade = produto_info['unidade_fracionada']
    codigo_interno = produto_info.get('codigo_interno')
    
    if is_postgres:
        cur.execute("INSERT INTO products (name, unidade_fracionada, codigo_interno) VALUES (%s, %s, %s);", (nome, unidade, codigo_interno))
    else:
        cur.execute("INSERT INTO products (name, unidade_fracionada, codigo_interno) VALUES (?, ?, ?);", (nome, unidade, codigo_interno))

# 3. Vincular produtos aos dias da semana
print("Criando vínculos de disponibilidade por dia...")
for dia_nome, produtos_lista in PRODUTOS.items():
    if dia_nome not in DIAS_MAP: 
        continue
    day_id = DIAS_MAP[dia_nome]
    for produto_dict in produtos_lista:
        nome = produto_dict['nome']
        if is_postgres:
            cur.execute("SELECT id FROM products WHERE name = %s;", (nome,))
        else:
            cur.execute("SELECT id FROM products WHERE name = ?;", (nome,))
        
        product_id_tuple = cur.fetchone()
        if product_id_tuple:
            product_id = product_id_tuple[0]
            if is_postgres:
                cur.execute("INSERT INTO product_availability (product_id, day_id) VALUES (%s, %s) ON CONFLICT DO NOTHING;", (product_id, day_id))
            else:
                cur.execute("INSERT OR IGNORE INTO product_availability (product_id, day_id) VALUES (?, ?);", (product_id, day_id))

print("Carga de produtos concluída.")
conn.commit()
cur.close()
conn.close()

print("Banco de dados e todas as tabelas foram criados/atualizados com sucesso!")