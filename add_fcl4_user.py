# add_fcl4_user.py - Script para adicionar usuário FCL4 ao banco de dados
"""
Este script adiciona o usuário FCL4 ao banco de dados sem afetar dados existentes.
Pode ser executado múltiplas vezes sem causar problemas.
"""

import os
import sqlite3
import psycopg2

def add_fcl4_user():
    """Adiciona o usuário FCL4 ao banco de dados"""
    
    # Verificar ambiente
    db_url = os.environ.get('DATABASE_URL')
    is_postgres = bool(db_url)
    
    print("=== ADICIONANDO USUÁRIO FCL4 ===")
    print(f"Ambiente: {'PostgreSQL (Render)' if is_postgres else 'SQLite (Local)'}")
    
    try:
        # Conectar ao banco
        if is_postgres:
            print("Conectando ao PostgreSQL...")
            conn = psycopg2.connect(db_url)
        else:
            print("Conectando ao SQLite...")
            conn = sqlite3.connect('hortifruti.db')
        
        cur = conn.cursor()
        
        # Dados do novo usuário
        username = 'fcl4'
        password = 'fcl423'
        role = 'loja'
        store_name = 'FCL4'
        
        # Verificar se o usuário já existe
        print(f"Verificando se o usuário '{username}' já existe...")
        if is_postgres:
            cur.execute("SELECT COUNT(*) FROM users WHERE username = %s;", (username,))
        else:
            cur.execute("SELECT COUNT(*) FROM users WHERE username = ?;", (username,))
        
        user_exists = cur.fetchone()[0] > 0
        
        if user_exists:
            print(f"✅ Usuário '{username}' já existe no banco de dados.")
            print("Nenhuma alteração necessária.")
        else:
            # Inserir o novo usuário
            print(f"Inserindo usuário '{username}' para a loja '{store_name}'...")
            if is_postgres:
                cur.execute(
                    "INSERT INTO users (username, password, role, store_name) VALUES (%s, %s, %s, %s) ON CONFLICT (username) DO NOTHING;",
                    (username, password, role, store_name)
                )
            else:
                cur.execute(
                    "INSERT OR IGNORE INTO users (username, password, role, store_name) VALUES (?, ?, ?, ?);",
                    (username, password, role, store_name)
                )
            
            conn.commit()
            print(f"✅ Usuário '{username}' adicionado com sucesso!")
            print(f"   - Username: {username}")
            print(f"   - Password: {password}")
            print(f"   - Role: {role}")
            print(f"   - Store: {store_name}")
        
        # Verificar todos os usuários de loja
        print("\nVerificando usuários de loja cadastrados...")
        if is_postgres:
            cur.execute("SELECT username, store_name FROM users WHERE role = 'loja' ORDER BY store_name;")
        else:
            cur.execute("SELECT username, store_name FROM users WHERE role = 'loja' ORDER BY store_name;")
        
        loja_users = cur.fetchall()
        print("Usuários de loja:")
        for user in loja_users:
            print(f"  - {user[0]} (Loja: {user[1]})")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro ao adicionar usuário: {e}")
        if 'conn' in locals():
            conn.rollback()
        return False
        
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    print("🚀 Iniciando adição do usuário FCL4...")
    print("=" * 50)
    
    if add_fcl4_user():
        print("\n🎉 Operação concluída com sucesso!")
        print("✅ O usuário FCL4 está pronto para uso.")
    else:
        print("\n❌ Falha na operação!")
        print("Verifique os logs acima para mais detalhes.")
        exit(1)
    
    print("\n" + "=" * 50)
    print("📝 Informações do novo usuário:")
    print("   Username: fcl4")
    print("   Password: fcl423")
    print("   Loja: FCL4")
