# init_db.py
import os
import sqlite3
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

# --- LÓGICA DE CONEXÃO E CRIAÇÃO ---
db_url = os.environ.get('DATABASE_URL')

if db_url:
    # --- LÓGICA PARA POSTGRESQL (NA RENDER) ---
    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS pedidos (
            id SERIAL PRIMARY KEY,
            data_pedido TEXT NOT NULL,
            loja TEXT NOT NULL,
            produto TEXT NOT NULL,
            tipo TEXT NOT NULL,
            quantidade INTEGER NOT NULL
        );''')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL,
            store_name TEXT
        );''')
        
    # Insere usuários para PostgreSQL
    insert_query = 'INSERT INTO users (username, password, role, store_name) VALUES (%s, %s, %s, %s) ON CONFLICT (username) DO NOTHING;'
    cur.executemany(insert_query, USUARIOS)

else:
    # --- LÓGICA PARA SQLITE (NO SEU PC) ---
    conn = sqlite3.connect('hortifruti.db')
    cur = conn.cursor()
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS pedidos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_pedido TEXT NOT NULL,
            loja TEXT NOT NULL,
            produto TEXT NOT NULL,
            tipo TEXT NOT NULL,
            quantidade INTEGER NOT NULL
        );''')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL,
            store_name TEXT
        );''')
    
    # Insere usuários para SQLite
    insert_query = 'INSERT OR IGNORE INTO users (username, password, role, store_name) VALUES (?, ?, ?, ?);'
    cur.executemany(insert_query, USUARIOS)

# Salva as mudanças e fecha a conexão
conn.commit()
cur.close()
conn.close()

print("Banco de dados e tabelas 'pedidos' e 'users' criados com sucesso!")
print(f"{len(USUARIOS)} usuários foram verificados/inseridos.")