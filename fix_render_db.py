# fix_render_db.py - Script simples para corrigir o banco no Render
import os
import psycopg2

def create_dias_contagem_table():
    """Cria a tabela dias_contagem no banco do Render"""
    
    # Conectar ao banco do Render
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        print("ERRO: DATABASE_URL não encontrada. Execute este script no Render.")
        return False
    
    try:
        print("Conectando ao banco do Render...")
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        
        # Verificar se a tabela já existe
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'dias_contagem'
            );
        """)
        
        table_exists = cur.fetchone()[0]
        
        if table_exists:
            print("Tabela 'dias_contagem' já existe!")
            return True
        
        print("Criando tabela 'dias_contagem'...")
        
        # Criar a tabela
        cur.execute("""
            CREATE TABLE dias_contagem (
                id SERIAL PRIMARY KEY,
                data_contagem DATE NOT NULL UNIQUE,
                ativo BOOLEAN DEFAULT TRUE,
                observacoes TEXT
            );
        """)
        
        conn.commit()
        print("Tabela criada com sucesso!")
        
        # Verificar estrutura
        cur.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'dias_contagem'
            ORDER BY ordinal_position;
        """)
        
        columns = cur.fetchall()
        print("Estrutura da tabela:")
        for col in columns:
            print(f"  - {col[0]}: {col[1]}")
        
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
    print("=== CORREÇÃO DO BANCO NO RENDER ===")
    print("Criando tabela 'dias_contagem'...")
    
    if create_dias_contagem_table():
        print("\nSUCESSO! Tabela criada com sucesso.")
        print("A funcionalidade 'Dias de Contagem' deve funcionar agora.")
    else:
        print("\nERRO! Falha ao criar a tabela.")
        print("Verifique os logs acima para mais detalhes.")
