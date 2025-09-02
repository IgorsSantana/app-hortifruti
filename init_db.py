# init_db.py
import sqlite3
import os
import psycopg2

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

# --- COMANDOS SQL PARA CRIAR AS TABELAS ---
# Obs: a sintaxe é um pouco diferente para PostgreSQL (ex: SERIAL PRIMARY KEY)
CREATE_PEDIDOS_TABLE = '''
    CREATE TABLE IF NOT EXISTS pedidos (
        id SERIAL PRIMARY KEY,
        data_pedido TEXT NOT NULL,
        loja TEXT NOT NULL,
        produto TEXT NOT NULL,
        tipo TEXT NOT NULL,
        quantidade INTEGER NOT NULL
    );'''

CREATE_USERS_TABLE = '''
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL,
        store_name TEXT
    );'''

# --- LÓGICA DE CONEXÃO ---
db_url = os.environ.get('DATABASE_URL')
if db_url:
    # Conexão com PostgreSQL na Render
    connection = psycopg2.connect(db_url)
else:
    # Conexão com SQLite local
    connection = sqlite3.connect('hortifruti.db')

cursor = connection.cursor()

# Executa a criação das tabelas
cursor.execute(CREATE_PEDIDOS_TABLE)
cursor.execute(CREATE_USERS_TABLE)

# Insere os usuários
# A sintaxe de placeholder também muda (%s para psycopg2)
INSERT_USERS_QUERY = 'INSERT INTO users (username, password, role, store_name) VALUES (%s, %s, %s, %s) ON CONFLICT (username) DO NOTHING;'
cursor.executemany(INSERT_USERS_QUERY, USUARIOS)

connection.commit()
cursor.close()
connection.close()

print("Banco de dados e tabelas 'pedidos' e 'users' criados com sucesso!")
print(f"{len(USUARIOS)} usuários foram verificados/inseridos.")