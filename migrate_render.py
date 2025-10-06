# migrate_render.py - Script de migração seguro para o Render
"""
Este script configura a tabela dias_semana_config no Render sem apagar dados existentes.
Pode ser executado múltiplas vezes sem causar problemas.
"""

import os
import sqlite3
import psycopg2

def migrate_database():
    """Migra o banco de dados adicionando a tabela dias_semana_config"""
    
    # Verificar ambiente
    db_url = os.environ.get('DATABASE_URL')
    is_postgres = bool(db_url)
    
    print("=== MIGRAÇÃO DO BANCO DE DADOS ===")
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
        
        # 1. Criar tabela dias_semana_config se não existir
        print("Verificando/criando tabela dias_semana_config...")
        
        if is_postgres:
            create_table_sql = """
                CREATE TABLE IF NOT EXISTS dias_semana_config (
                    dia_id INTEGER PRIMARY KEY,
                    nome_dia TEXT NOT NULL,
                    ativo BOOLEAN DEFAULT TRUE
                );
            """
        else:
            create_table_sql = """
                CREATE TABLE IF NOT EXISTS dias_semana_config (
                    dia_id INTEGER PRIMARY KEY,
                    nome_dia TEXT NOT NULL,
                    ativo BOOLEAN DEFAULT TRUE
                );
            """
        
        cur.execute(create_table_sql)
        print("✅ Tabela dias_semana_config verificada/criada")
        
        # 2. Configurar dias da semana (apenas se não existirem)
        print("Configurando dias da semana...")
        DIAS_SEMANA = {0: "SEGUNDA-FEIRA", 1: "TERÇA-FEIRA", 2: "QUARTA-FEIRA", 4: "SEXTA-FEIRA", 5: "SÁBADO"}
        
        dias_inseridos = 0
        for dia_id, nome_dia in DIAS_SEMANA.items():
            if is_postgres:
                # Verificar se já existe
                cur.execute("SELECT COUNT(*) FROM dias_semana_config WHERE dia_id = %s;", (dia_id,))
                exists = cur.fetchone()[0] > 0
                
                if not exists:
                    cur.execute("""
                        INSERT INTO dias_semana_config (dia_id, nome_dia, ativo) 
                        VALUES (%s, %s, %s);
                    """, (dia_id, nome_dia, True))
                    dias_inseridos += 1
                    print(f"  ✅ {nome_dia} inserido")
                else:
                    print(f"  ⏭️  {nome_dia} já existe")
            else:
                # SQLite
                cur.execute("SELECT COUNT(*) FROM dias_semana_config WHERE dia_id = ?;", (dia_id,))
                exists = cur.fetchone()[0] > 0
                
                if not exists:
                    cur.execute("""
                        INSERT INTO dias_semana_config (dia_id, nome_dia, ativo) 
                        VALUES (?, ?, ?);
                    """, (dia_id, nome_dia, True))
                    dias_inseridos += 1
                    print(f"  ✅ {nome_dia} inserido")
                else:
                    print(f"  ⏭️  {nome_dia} já existe")
        
        # 3. Verificar dados existentes
        print("\nVerificando dados existentes...")
        cur.execute("SELECT dia_id, nome_dia, ativo FROM dias_semana_config ORDER BY dia_id;")
        dias_config = cur.fetchall()
        
        print("Dias configurados:")
        for dia in dias_config:
            status = "Ativo" if dia[2] else "Inativo"
            print(f"  - {dia[1]} (ID: {dia[0]}) - {status}")
        
        # 4. Verificar outras tabelas importantes
        print("\nVerificando outras tabelas...")
        tabelas_importantes = ['users', 'products', 'pedidos', 'pedidos_finais']
        
        for tabela in tabelas_importantes:
            try:
                if is_postgres:
                    cur.execute(f"SELECT COUNT(*) FROM {tabela};")
                else:
                    cur.execute(f"SELECT COUNT(*) FROM {tabela};")
                count = cur.fetchone()[0]
                print(f"  - {tabela}: {count} registros")
            except Exception as e:
                print(f"  - {tabela}: Erro ao verificar ({e})")
        
        # Commit das alterações
        conn.commit()
        print(f"\n✅ Migração concluída com sucesso!")
        print(f"   - {dias_inseridos} novos dias inseridos")
        print(f"   - {len(dias_config)} dias configurados no total")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro durante a migração: {e}")
        if 'conn' in locals():
            conn.rollback()
        return False
        
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    print("🚀 Iniciando migração do banco de dados...")
    print("=" * 50)
    
    if migrate_database():
        print("\n🎉 Migração executada com sucesso!")
        print("✅ A funcionalidade de 'Dias de Contagem' está pronta para uso.")
    else:
        print("\n❌ Falha na migração!")
        print("Verifique os logs acima para mais detalhes.")
        exit(1)
    
    print("\n" + "=" * 50)
    print("📝 Próximos passos:")
    print("1. Acesse o painel administrativo")
    print("2. Vá para 'Dias de Contagem'")
    print("3. Configure quais dias estarão ativos")
    print("4. Teste a funcionalidade")
