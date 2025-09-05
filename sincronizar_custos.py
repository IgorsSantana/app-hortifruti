# sincronizar_custos.py
import os
import pyodbc
import requests
import json
from dotenv import load_dotenv

# Carrega as variáveis de um arquivo .env para não deixar senhas no código
load_dotenv()

# --- CONFIGURAÇÕES ---
# (Preencha com seus dados ou crie um arquivo .env)
DB2_DATABASE = os.environ.get('DB2_DATABASE', 'SAB')
DB2_HOSTNAME = os.environ.get('DB2_HOSTNAME', '10.64.1.11')
DB2_PORT = os.environ.get('DB2_PORT', '50000')
DB2_USERNAME = os.environ.get('DB2_USERNAME', 'db2user_ro')
DB2_PASSWORD = os.environ.get('DB2_PASSWORD', 'Sup3rs4nt0')

RENDER_APP_URL = os.environ.get('RENDER_APP_URL', 'https://contagem-hortifruti.onrender.com')
API_SECRET_KEY = os.environ.get('API_SECRET_KEY') # A chave que você gerou

def fetch_costs_from_db2():
    # ... (código da função get_product_costs, mas adaptado para este script) ...

def send_costs_to_api(costs_list):
    if not API_SECRET_KEY:
        print("ERRO: A chave da API (API_SECRET_KEY) não foi configurada.")
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