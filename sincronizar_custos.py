# sincronizar_custos.py
import os
import pyodbc
import requests
import json
from dotenv import load_dotenv

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
            cursor = cnxn.cursor()
            sql_query = """
                SELECT B.IDSUBPRODUTO AS CODIGO_INTERNO, CAST(E.CUSTOGERENCIAL AS DECIMAL(15,2)) AS CUSTO_GERENCIAL
                FROM DBA.PRODUTO AS A
                LEFT JOIN DBA.PRODUTO_GRADE AS B ON (A.IDPRODUTO = B.IDPRODUTO)
                LEFT JOIN DBA.SECAO AS C ON (A.IDSECAO = C.IDSECAO)
                LEFT JOIN DBA.PRODUTO_CADEIA_PRECO AS D ON (B.IDCADEIAPRECO = D.IDCADEIAPRECO)
                LEFT JOIN DBA.POLITICA_PRECO_PRODUTO AS E ON (B.IDPRODUTO = E.IDPRODUTO AND B.IDSUBPRODUTO = E.IDSUBPRODUTO AND E.IDEMPRESA = 1)
                WHERE B.FLAGINATIVO = 'F' AND B.FLAGBLOQUEIAVENDA = 'F' AND A.IDSECAO = 44 AND A.IDGRUPO <> 4410
            """
            cursor.execute(sql_query)
            rows = cursor.fetchall()
            for row in rows:
                if row.CODIGO_INTERNO and row.CUSTO_GERENCIAL is not None:
                    costs_list.append({
                        "codigo_interno": str(row.CODIGO_INTERNO),
                        "custo": float(row.CUSTO_GERENCIAL) / 100.0
                    })
            print(f"Sucesso: {len(costs_list)} custos carregados do DB2.")
    except Exception as e:
        print(f"ERRO CRÍTICO AO CONECTAR COM O DB2: {e}")
        return None
    return costs_list

def send_costs_to_api(costs_list):
    """Envia a lista de custos para a API do aplicativo na Render."""
    if not API_SECRET_KEY:
        print("ERRO: A chave da API (API_SECRET_KEY) não foi configurada no arquivo .env.")
        return

    api_url = f"{RENDER_APP_URL}/api/update-costs"
    headers = {
        'Content-Type': 'application/json',
        'X-API-KEY': API_SECRET_KEY
    }
    payload = json.dumps({"costs": costs_list})

    print(f"Enviando {len(costs_list)} custos para a API...")
    try:
        response = requests.post(api_url, headers=headers, data=payload, timeout=60)
        if response.status_code == 200:
            print("Sucesso! Resposta da API:")
            print(response.json())
        else:
            print(f"Erro ao enviar dados. Status: {response.status_code}")
            print("Resposta:", response.text)
    except requests.exceptions.RequestException as e:
        print(f"Falha na conexão com a API: {e}")

if __name__ == "__main__":
    custos_encontrados = fetch_costs_from_db2()
    if custos_encontrados:
        send_costs_to_api(custos_encontrados)
    else:
        print("Nenhum custo encontrado para sincronizar.")