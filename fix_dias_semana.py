# fix_dias_semana.py - Script para criar tabela de dias da semana no Render
import os
import sqlite3
import psycopg2

def create_dias_semana_table():
    """Cria a tabela dias_semana_config no banco do Render"""
    
    # Conectar ao banco
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
                    AND table_name = 'dias_semana_config'
                );
            """)
        else:
            cur.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='dias_semana_config';
            """)
        
        table_exists = cur.fetchone()[0] if is_postgres else cur.fetchone() is not None
        
        if table_exists:
            print("Tabela 'dias_semana_config' já existe!")
        else:
            print("Criando tabela 'dias_semana_config'...")
            
            # Criar a tabela
            if is_postgres:
                create_table_sql = """
                    CREATE TABLE dias_semana_config (
                        dia_id INTEGER PRIMARY KEY,
                        nome_dia TEXT NOT NULL,
                        ativo BOOLEAN DEFAULT TRUE
                    );
                """
            else:
                create_table_sql = """
                    CREATE TABLE dias_semana_config (
                        dia_id INTEGER PRIMARY KEY,
                        nome_dia TEXT NOT NULL,
                        ativo BOOLEAN DEFAULT TRUE
                    );
                """
            
            cur.execute(create_table_sql)
            print("Tabela criada com sucesso!")
        
        # Inserir configuração dos dias da semana
        print("Configurando dias da semana...")
        DIAS_SEMANA = {0: "SEGUNDA-FEIRA", 1: "TERÇA-FEIRA", 2: "QUARTA-FEIRA", 4: "SEXTA-FEIRA", 5: "SÁBADO"}
        
        for dia_id, nome_dia in DIAS_SEMANA.items():
            if is_postgres:
                cur.execute("""
                    INSERT INTO dias_semana_config (dia_id, nome_dia, ativo) 
                    VALUES (%s, %s, %s) 
                    ON CONFLICT (dia_id) DO NOTHING;
                """, (dia_id, nome_dia, True))
            else:
                cur.execute("""
                    INSERT OR IGNORE INTO dias_semana_config (dia_id, nome_dia, ativo) 
                    VALUES (?, ?, ?);
                """, (dia_id, nome_dia, True))
        
        conn.commit()
        print("Configuração dos dias da semana concluída!")
        
        # Verificar dados inseridos
        cur.execute("SELECT dia_id, nome_dia, ativo FROM dias_semana_config ORDER BY dia_id;")
        dias = cur.fetchall()
        print("Dias configurados:")
        for dia in dias:
            status = "Ativo" if dia[2] else "Inativo"
            print(f"  - {dia[1]} (ID: {dia[0]}) - {status}")
        
        return True
        
    except Exception as e:
        print(f"ERRO: {e}")
        if 'conn' in locals():
            conn.rollback()
        return False
        
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    print("=== CONFIGURAÇÃO DOS DIAS DA SEMANA ===")
    print("Criando tabela e configurando dias da semana...")
    
    if create_dias_semana_table():
        print("\nSUCESSO! Configuração concluída.")
        print("A funcionalidade 'Dias de Contagem' deve funcionar agora.")
    else:
        print("\nERRO! Falha na configuração.")
        print("Verifique os logs acima para mais detalhes.")
