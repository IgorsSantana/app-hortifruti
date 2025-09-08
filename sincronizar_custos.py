# sincronizar_custos.py
import os
import pyodbc
import requests
import json
import psycopg2 # Precisamos para conectar ao nosso BD e verificar os códigos
from dotenv import load_dotenv
from datetime import datetime

# Carrega as variáveis do arquivo .env
load_dotenv()

# --- CONFIGURAÇÕES (Lidas do arquivo .env) ---
DB2_DATABASE = os.getenv('DB2_DATABASE')
DB2_HOSTNAME = os.getenv('DB2_HOSTNAME')
DB2_PORT = os.getenv('DB2_PORT')
DB2_USERNAME = os.getenv('DB2_USERNAME')
DB2_PASSWORD = os.getenv('DB2_PASSWORD')

RENDER_APP_URL = os.getenv('RENDER_APP_URL')
API_SECRET_KEY = os.getenv('API_SECRET_KEY')
POSTGRES_URL = os.getenv('DATABASE_URL') # URL do nosso banco de dados na Render

LOG_FILE = "sincronizacao_log.txt"

def get_existing_codes_from_app():
    """Busca todos os códigos internos existentes no banco de dados do nosso app."""
    if not POSTGRES_URL:
        print("ERRO: Variavel DATABASE_URL nao encontrada no .env. Nao e possivel verificar os codigos existentes.")
        return set() # Retorna um conjunto vazio

    existing_codes = set()
    try:
        conn = psycopg2.connect(POSTGRES_URL)
        cur = conn.cursor()
        cur.execute("SELECT codigo_interno FROM products WHERE codigo_interno IS NOT NULL AND codigo_interno != '';")
        rows = cur.fetchall()
        for row in rows:
            existing_codes.add(row[0])
        cur.close()
        conn.close()
        print(f"Encontrados {len(existing_codes)} codigos internos no banco de dados do aplicativo.")
    except Exception as e:
        print(f"ERRO ao buscar codigos do app: {e}")
    return existing_codes

def fetch_costs_from_db2():
    """Conecta ao DB2 e busca os custos."""
    costs_list = []
    print("Tentando conectar ao banco de dados DB2...")
    try:
        conn_str = (
            f"DRIVER={{IBM DB2 ODBC DRIVER}};"
            f"DATABASE={DB2_DATABASE};"
            f"HOSTNAME={DB2_HOSTNAME};"
            f"PORT={DB2_PORT};"
            f"PROTOCOL=TCPIP;"
            f"UID={DB2_USERNAME};"
            f"PWD={DB2_PASSWORD};"
        )
        with pyodbc.connect(conn_str, timeout=10) as cnxn:
            # ... (código da query SQL inalterado) ...
            cursor = cnxn.cursor()
            sql_query = """
                SELECT B.IDSUBPRODUTO AS CODIGO_INTERNO, CAST(E.CUSTOGERENCIAL AS DECIMAL(15,2)) AS CUSTO_GERENCIAL
                FROM DBA.PRODUTO AS A
                LEFT JOIN DBA.PRODUTO_GRADE AS B ON (A.IDPRODUTO = B.IDPRODUTO)
                LEFT JOIN DBA.SECAO AS C ON (A.IDSECAO = C.IDSECAO)
                LEFT JOIN DBA.PRODUTO_CADEIA_PRECO AS D ON (B.IDCADEIAPRECO = D.IDCADEIAPRECO)
                LEFT JOIN DBA.POLITICA_PRECO_PRODUTO AS E ON (B.IDPRODUTO = E.IDPRODUTO AND B.IDSUBPRODUTO = E.IDSUBPRODUTO AND E.IDEMPRESA = 1)
                WHERE B.FLAGINATIVO = 'F' AND A.IDSECAO = 44 AND A.IDGRUPO <> 4410
            """
            cursor.execute(sql_query)
            rows = cursor.fetchall()
            for row in rows:
                if row.CODIGO_INTERNO and row.CUSTO_GERENCIAL is not None:
                    costs_list.append({
                        "codigo_interno": str(row.CODIGO_INTERNO).strip(), # .strip() para remover espaços extras
                        "custo": float(row.CUSTO_GERENCIAL) / 100.0
                    })
            print(f"Sucesso: {len(costs_list)} custos carregados do DB2.")
    except Exception as e:
        print(f"ERRO CRÍTICO AO CONECTAR COM O DB2: {e}")
        return None
    return costs_list

def send_costs_to_api(costs_list, existing_codes):
    """Envia a lista de custos para a API e gera um log detalhado."""
    if not API_SECRET_KEY:
        print("ERRO: A chave da API (API_SECRET_KEY) não foi configurada no arquivo .env.")
        return

    # Filtra apenas os custos para produtos que realmente existem no nosso app
    costs_to_send = [item for item in costs_list if item['codigo_interno'] in existing_codes]
    codes_not_found = [item for item in costs_list if item['codigo_interno'] not in existing_codes]

    with open(LOG_FILE, "w", encoding="utf-8") as f:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        f.write(f"--- Log de Sincronizacao de Custos - {now} ---\n\n")
        f.write(f"Total de custos encontrados no DB2: {len(costs_list)}\n")
        f.write(f"Total de codigos correspondentes encontrados no app: {len(costs_to_send)}\n")
        f.write(f"Total de codigos NAO encontrados no app: {len(codes_not_found)}\n\n")

        if not costs_to_send:
            f.write("Nenhum custo para enviar. Verifique se os codigos internos correspondem.\n")
            print("Nenhum custo correspondente para enviar.")
            return

        api_url = f"{RENDER_APP_URL}/api/update-costs"
        headers = {'Content-Type': 'application/json', 'X-API-KEY': API_SECRET_KEY}
        payload = json.dumps({"costs": costs_to_send})

        print(f"Enviando {len(costs_to_send)} custos para a API...")
        f.write(f"--- DETALHES DA EXECUCAO ---\n")
        try:
            response = requests.post(api_url, headers=headers, data=payload, timeout=60)
            if response.status_code == 200:
                print("Sucesso! Resposta da API:")
                print(response.json())
                f.write(f"Status do Envio: SUCESSO\n")
                f.write(f"Resposta da API: {response.json().get('message')}\n\n")
            else:
                print(f"Erro ao enviar dados. Status: {response.status_code}")
                print("Resposta:", response.text)
                f.write(f"Status do Envio: ERRO {response.status_code}\n")
                f.write(f"Resposta da API: {response.text}\n\n")

        except requests.exceptions.RequestException as e:
            print(f"Falha na conexão com a API: {e}")
            f.write(f"Status do Envio: FALHA NA CONEXAO\n")
            f.write(f"Erro: {e}\n\n")

        # Escreve os logs detalhados
        f.write("\n--- Produtos com Custo ATUALIZADO ---\n")
        for item in costs_to_send:
            f.write(f"Codigo: {item['codigo_interno']} - Novo Custo: R$ {item['custo']:.2f}\n")
        
        f.write("\n--- Produtos com Custo NAO ATUALIZADO (Codigo nao encontrado no app) ---\n")
        for item in codes_not_found:
            f.write(f"Codigo do DB2: {item['codigo_interno']}\n")

    print(f"Processo finalizado. Log detalhado foi salvo no arquivo: {LOG_FILE}")

if __name__ == "__main__":
    # É necessário ter a URL do banco da Render no .env para este script funcionar
    if not POSTGRES_URL:
        print("ERRO: Variavel DATABASE_URL (do banco PostgreSQL da Render) nao foi encontrada no arquivo .env.")
    else:
        codigos_no_app = get_existing_codes_from_app()
        custos_do_db2 = fetch_costs_from_db2()
        if custos_do_db2:
            send_costs_to_api(custos_do_db2, codigos_no_app)
        else:
            print("Nenhum custo encontrado para sincronizar.")