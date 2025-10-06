# migrate_db.py - Script de Migração Segura para o Render
"""
Este script adiciona apenas a nova tabela 'dias_contagem' sem afetar dados existentes.
Execute este script APENAS no ambiente de produção (Render) para adicionar a nova funcionalidade.
"""

import os
import sqlite3
import psycopg2

def migrate_database():
    """
    Adiciona a tabela dias_contagem ao banco existente sem afetar dados.
    """
    print("Iniciando migração do banco de dados...")
    
    # Verificar se estamos no ambiente de produção (Render)
    db_url = os.environ.get('DATABASE_URL')
    is_postgres = bool(db_url)
    
    if is_postgres:
        print("Conectando ao PostgreSQL (Render)...")
        conn = psycopg2.connect(db_url)
    else:
        print("Conectando ao SQLite (local)...")
        conn = sqlite3.connect('hortifruti.db')
    
    cur = conn.cursor()
    
    try:
        # Verificar se a tabela já existe
        if is_postgres:
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'dias_contagem'
                );
            """)
        else:
            cur.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='dias_contagem';
            """)
        
        table_exists = cur.fetchone()[0] if is_postgres else cur.fetchone() is not None
        
        if table_exists:
            print("Tabela 'dias_contagem' já existe. Migração não necessária.")
            return True
        
        print("Criando tabela 'dias_contagem'...")
        
        # Criar a nova tabela
        if is_postgres:
            create_table_sql = """
                CREATE TABLE dias_contagem (
                    id SERIAL PRIMARY KEY,
                    data_contagem DATE NOT NULL UNIQUE,
                    ativo BOOLEAN DEFAULT TRUE,
                    observacoes TEXT
                );
            """
        else:
            create_table_sql = """
                CREATE TABLE dias_contagem (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    data_contagem DATE NOT NULL UNIQUE,
                    ativo BOOLEAN DEFAULT TRUE,
                    observacoes TEXT
                );
            """
        
        cur.execute(create_table_sql)
        conn.commit()
        
        print("Tabela 'dias_contagem' criada com sucesso!")
        
        # Verificar se a tabela foi criada corretamente
        if is_postgres:
            cur.execute("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = 'dias_contagem'
                ORDER BY ordinal_position;
            """)
        else:
            cur.execute("PRAGMA table_info(dias_contagem);")
        
        columns = cur.fetchall()
        print("Estrutura da tabela criada:")
        for col in columns:
            print(f"   - {col[0]}: {col[1]}")
        
        return True
        
    except Exception as e:
        print(f"Erro durante a migração: {e}")
        conn.rollback()
        return False
        
    finally:
        cur.close()
        conn.close()

def verify_existing_data():
    """
    Verifica se os dados existentes estão intactos.
    """
    print("Verificando dados existentes...")
    
    db_url = os.environ.get('DATABASE_URL')
    is_postgres = bool(db_url)
    
    if is_postgres:
        conn = psycopg2.connect(db_url)
    else:
        conn = sqlite3.connect('hortifruti.db')
    
    cur = conn.cursor()
    
    try:
        # Verificar tabelas existentes
        if is_postgres:
            cur.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                ORDER BY table_name;
            """)
        else:
            cur.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' 
                ORDER BY name;
            """)
        
        tables = [row[0] for row in cur.fetchall()]
        print("Tabelas existentes:")
        for table in tables:
            print(f"   - {table}")
        
        # Verificar contagem de registros nas tabelas principais
        main_tables = ['users', 'products', 'pedidos', 'pedidos_finais']
        for table in main_tables:
            if table in tables:
                if is_postgres:
                    cur.execute(f"SELECT COUNT(*) FROM {table};")
                else:
                    cur.execute(f"SELECT COUNT(*) FROM {table};")
                count = cur.fetchone()[0]
                print(f"   {table}: {count} registros")
        
        return True
        
    except Exception as e:
        print(f"Erro ao verificar dados: {e}")
        return False
        
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    print("Script de Migração do Banco de Dados")
    print("=" * 50)
    
    # Verificar dados existentes primeiro
    if not verify_existing_data():
        print("Falha na verificação dos dados existentes. Abortando migração.")
        exit(1)
    
    print("\n" + "=" * 50)
    
    # Executar migração
    if migrate_database():
        print("\nMigração concluída com sucesso!")
        print("A nova funcionalidade de 'Dias de Contagem' está pronta para uso.")
    else:
        print("\nMigração falhou!")
        exit(1)
    
    print("\n" + "=" * 50)
    print("Próximos passos:")
    print("1. Acesse o painel administrativo")
    print("2. Vá para 'Dias de Contagem'")
    print("3. Adicione os dias desejados")
    print("4. Configure quais dias estarão ativos")
