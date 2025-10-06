# create_table_simple.py - Script simples para criar tabela no Render
import os
import psycopg2

# Conectar ao banco do Render
db_url = os.environ.get('DATABASE_URL')
if not db_url:
    print("ERRO: DATABASE_URL não encontrada")
    exit(1)

try:
    print("Conectando ao banco do Render...")
    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    
    print("Criando tabela dias_semana_config...")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS dias_semana_config (
            dia_id INTEGER PRIMARY KEY,
            nome_dia TEXT NOT NULL,
            ativo BOOLEAN DEFAULT TRUE
        );
    """)
    
    print("Inserindo dados dos dias da semana...")
    dias = [
        (0, 'SEGUNDA-FEIRA', True),
        (1, 'TERÇA-FEIRA', True),
        (2, 'QUARTA-FEIRA', True),
        (4, 'SEXTA-FEIRA', True),
        (5, 'SÁBADO', True)
    ]
    
    for dia_id, nome_dia, ativo in dias:
        cur.execute("""
            INSERT INTO dias_semana_config (dia_id, nome_dia, ativo) 
            VALUES (%s, %s, %s) 
            ON CONFLICT (dia_id) DO NOTHING;
        """, (dia_id, nome_dia, ativo))
    
    conn.commit()
    print("SUCESSO! Tabela criada e dados inseridos.")
    
    # Verificar dados
    cur.execute("SELECT dia_id, nome_dia, ativo FROM dias_semana_config ORDER BY dia_id;")
    rows = cur.fetchall()
    print("Dados inseridos:")
    for row in rows:
        print(f"  {row[1]} (ID: {row[0]}) - {'Ativo' if row[2] else 'Inativo'}")
    
except Exception as e:
    print(f"ERRO: {e}")
    if 'conn' in locals():
        conn.rollback()
finally:
    if 'cur' in locals():
        cur.close()
    if 'conn' in locals():
        conn.close()
