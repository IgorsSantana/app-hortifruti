# init_db.py
import sqlite3

DATABASE = 'hortifruti.db'

# --- DEFINIÇÃO DOS USUÁRIOS ---
# (Você pode e deve alterar as senhas aqui)
USUARIOS = [
    # ('usuario', 'senha', 'permissao', 'nome_da_loja_associada')
    ('bcs', 'bcs123', 'loja', 'BCS'),
    ('sjn', 'sjn123', 'loja', 'SJN'),
    ('mep', 'mep123', 'loja', 'MEP'),
    ('fcl1', 'fcl123', 'loja', 'FCL1'),
    ('fcl2', 'fcl223', 'loja', 'FCL2'),
    ('fcl3', 'fcl323', 'loja', 'FCL3'),
    ('Igor', 'S4nt4n4', 'admin', None), # Admins não têm loja associada
    ('Gabriel', 'G1a2l', 'admin', None)
]

# Conecta ao banco de dados (isso vai criar o arquivo)
connection = sqlite3.connect(DATABASE)
cursor = connection.cursor()

# --- CRIA A TABELA DE PEDIDOS ---
cursor.execute('''
    CREATE TABLE IF NOT EXISTS pedidos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        data_pedido TEXT NOT NULL,
        loja TEXT NOT NULL,
        produto TEXT NOT NULL,
        tipo TEXT NOT NULL,
        quantidade INTEGER NOT NULL
    )
''')

# --- CRIA A TABELA DE USUÁRIOS ---
cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL,
        store_name TEXT
    )
''')

# --- INSERE OS USUÁRIOS NA TABELA ---
# O IGNORE previne erros se você rodar o script mais de uma vez
cursor.executemany('INSERT OR IGNORE INTO users (username, password, role, store_name) VALUES (?, ?, ?, ?)', USUARIOS)

# Salva as mudanças e fecha a conexão
connection.commit()
connection.close()

print("Banco de dados e tabelas 'pedidos' e 'users' criados com sucesso!")
print(f"{len(USUARIOS)} usuários foram inseridos.")