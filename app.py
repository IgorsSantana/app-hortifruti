# app.py - Versão com integração de custos do DB2

import sqlite3
import pandas as pd
import numpy as np
import psycopg2
import os
import pyodbc # Nova importação
from flask import Flask, render_template, request, redirect, url_for, session, flash
from datetime import datetime
from functools import wraps

app = Flask(__name__)
app.secret_key = 'chave-super-secreta-para-o-projeto-hortifruti'

DATABASE = 'hortifruti.db'
DIAS_PEDIDO = {0: "SEGUNDA-FEIRA", 1: "TERÇA-FEIRA", 2: "QUARTA-FEIRA", 4: "SEXTA-FEIRA", 5: "SÁBADO"}
LOJAS = ["BCS", "SJN", "MEP", "FCL1", "FCL2", "FCL3"]

def get_db():
    db_url = os.environ.get('DATABASE_URL')
    if db_url:
        conn = psycopg2.connect(db_url)
    else:
        conn = sqlite3.connect(DATABASE)
        conn.row_factory = sqlite3.Row
    return conn

# --- NOVA FUNÇÃO PARA BUSCAR CUSTOS DO DB2 ---
def get_product_costs():
    """Conecta ao banco DB2 via ODBC e busca os custos dos produtos."""
    costs = {}
    try:
        db_database = os.environ.get('DB2_DATABASE')
        db_hostname = os.environ.get('DB2_HOSTNAME')
        db_port = os.environ.get('DB2_PORT')
        db_username = os.environ.get('DB2_USERNAME')
        db_password = os.environ.get('DB2_PASSWORD')

        if not all([db_database, db_hostname, db_port, db_username, db_password]):
            print("AVISO: Variaveis de ambiente do DB2 nao configuradas. Custos nao serao carregados.")
            return {}

        conn_str = (
            f"DRIVER={{IBM DB2 ODBC DRIVER}};"
            f"DATABASE={db_database};"
            f"HOSTNAME={db_hostname};"
            f"PORT={db_port};"
            f"PROTOCOL=TCPIP;"
            f"UID={db_username};"
            f"PWD={db_password};"
        )
        
        with pyodbc.connect(conn_str) as cnxn:
            cursor = cnxn.cursor()
            sql_query = """
                SELECT
                    B.IDSUBPRODUTO AS CODIGO_INTERNO,
                    CAST (E.CUSTOGERENCIAL AS DECIMAL(15,2)) AS CUSTO_GERENCIAL
                FROM
                    DBA.PRODUTO AS A
                    LEFT JOIN DBA.PRODUTO_GRADE AS B ON (A.IDPRODUTO = B.IDPRODUTO)
                    LEFT JOIN DBA.SECAO AS C ON (A.IDSECAO = C.IDSECAO)
                    LEFT JOIN DBA.PRODUTO_CADEIA_PRECO AS D ON (B.IDCADEIAPRECO = D.IDCADEIAPRECO)
                    LEFT JOIN DBA.POLITICA_PRECO_PRODUTO AS E ON (B.IDPRODUTO = E.IDPRODUTO AND B.IDSUBPRODUTO = E.IDSUBPRODUTO AND E.IDEMPRESA = 1)
                WHERE
                    B.FLAGINATIVO = 'F' AND
                    B.FLAGBLOQUEIAVENDA = 'F' AND
                    A.IDSECAO = 44 AND
                    A.IDGRUPO <> 4410
            """
            cursor.execute(sql_query)
            rows = cursor.fetchall()
            
            for row in rows:
                if row.CODIGO_INTERNO and row.CUSTO_GERENCIAL is not None:
                    costs[str(row.CODIGO_INTERNO)] = float(row.CUSTO_GERENCIAL)
            
            print(f"Sucesso: {len(costs)} custos carregados do DB2.")

    except Exception as e:
        print(f"ERRO AO CONECTAR COM O DB2: {e}")
    return costs

# --- FUNÇÕES AUXILIARES E DECORATORS ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login'))
        if session.get('role') != 'admin':
            return "Acesso negado. Apenas administradores podem ver esta página.", 403
        return f(*args, **kwargs)
    return decorated_function

def get_products_for_day(day_id):
    db = get_db()
    cursor = db.cursor()
    db_url = os.environ.get('DATABASE_URL')
    # ATUALIZADO: Busca também o codigo_interno
    query = """
        SELECT p.id, p.name, p.unidade_fracionada, p.codigo_interno
        FROM products p JOIN product_availability pa ON p.id = pa.product_id 
        WHERE pa.day_id = %s ORDER BY p.name;
    """ if db_url else """
        SELECT p.id, p.name, p.unidade_fracionada, p.codigo_interno
        FROM products p JOIN product_availability pa ON p.id = pa.product_id 
        WHERE pa.day_id = ? ORDER BY p.name;
    """
    cursor.execute(query, (day_id,))
    products_data = cursor.fetchall()
    products_list = [dict(zip([desc[0] for desc in cursor.description], row)) for row in products_data]
    for p in products_list:
        p['nome'] = p.pop('name')
    cursor.close()
    db.close()
    return products_list

def obter_dados_relatorio():
    hoje_weekday = datetime.now().weekday()
    if hoje_weekday not in DIAS_PEDIDO: return None, None
    nome_dia = DIAS_PEDIDO[hoje_weekday]
    
    # ATUALIZADO: Busca produtos do nosso banco e os custos do DB2
    produtos_do_dia_dict = get_products_for_day(hoje_weekday)
    custos = get_product_costs()

    # Adiciona o custo a cada produto da lista
    for produto in produtos_do_dia_dict:
        codigo = produto.get('codigo_interno')
        if codigo and str(codigo) in custos:
            produto['custo'] = custos[str(codigo)]
        else:
            produto['custo'] = 0.0

    if not produtos_do_dia_dict:
        cols = ['Custo'] + LOJAS
        return pd.DataFrame(columns=cols), nome_dia

    produtos_do_dia_nomes = [p['nome'] for p in produtos_do_dia_dict]
    
    db = get_db()
    hoje_str = datetime.now().strftime('%Y-%m-%d')
    query = f"SELECT produto, tipo, loja, quantidade FROM pedidos WHERE data_pedido = '{hoje_str}'"
    df_pedidos = pd.read_sql_query(query, db)
    db.close()
    
    df_caixas = df_pedidos[df_pedidos['tipo'] == 'Caixa']
    df_fracionado = df_pedidos[df_pedidos['tipo'].isin(['KG', 'UN'])]
    pivot_caixas = pd.pivot_table(df_caixas, values='quantidade', index='produto', columns='loja', aggfunc='sum')
    pivot_fracionado = pd.pivot_table(df_fracionado, values='quantidade', index='produto', columns='loja', aggfunc='sum')
    pivot_caixas = pivot_caixas.reindex(index=produtos_do_dia_nomes, columns=LOJAS).fillna(0).astype(int)
    pivot_fracionado = pivot_fracionado.reindex(index=produtos_do_dia_nomes, columns=LOJAS).fillna(0).astype(int)
    
    def formatar_celula(cx, frac_val, unidade):
        cx_str = f"{cx} cx" if cx > 0 else ""
        frac_str = f"{frac_val} {unidade.lower()}" if frac_val > 0 else ""
        if cx > 0 and frac_val > 0: return f"{cx_str} {frac_str}"
        elif cx > 0: return cx_str
        elif frac_val > 0: return frac_str
        else: return "0"

    tabela_final = pd.DataFrame(index=produtos_do_dia_nomes, columns=LOJAS)
    mapa_unidades = {p['nome']: p['unidade_fracionada'] for p in produtos_do_dia_dict}
    
    for produto_nome in tabela_final.index:
        unidade_fracionada = mapa_unidades.get(produto_nome, 'un')
        for loja in tabela_final.columns:
            cx_val = pivot_caixas.loc[produto_nome, loja] if produto_nome in pivot_caixas.index else 0
            un_val = pivot_fracionado.loc[produto_nome, loja] if produto_nome in pivot_fracionado.index else 0
            tabela_final.loc[produto_nome, loja] = formatar_celula(cx_val, un_val, unidade_fracionada)
    
    # Adiciona a coluna de custo à tabela final
    mapa_custos = {p['nome']: f"R$ {p['custo']:.2f}".replace('.', ',') for p in produtos_do_dia_dict}
    tabela_final.reset_index(inplace=True)
    tabela_final.rename(columns={'index': 'Produto'}, inplace=True)
    tabela_final.insert(1, 'Custo', tabela_final['Produto'].map(mapa_custos))
    tabela_final.set_index('Produto', inplace=True)
            
    return tabela_final, nome_dia

# --- ROTAS DA APLICAÇÃO (sem alterações significativas) ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    # ... código sem alteração ...
@app.route('/logout')
def logout():
    # ... código sem alteração ...
@app.route('/')
@login_required
def index():
    # ... código sem alteração ...
@app.route('/enviar', methods=['POST'])
@login_required
def enviar_pedido():
    # ... código sem alteração ...
@app.route('/sucesso')
@login_required
def sucesso():
    # ... código sem alteração ...

@app.route('/relatorio')
@admin_required
def relatorio():
    tabela_final, nome_dia = obter_dados_relatorio()
    if tabela_final is None:
        return "<h1>Hoje nao e um dia de pedido, portanto nao ha relatorio.</h1>"
    tabela_final.index.name = "Produto"
    html_table = tabela_final.to_html(classes='table table-bordered table-striped table-hover', border=0, table_id='relatorio-tabela')
    return render_template('relatorio.html', tabela_html=html_table, data_hoje=datetime.now().strftime('%d/%m/%Y'))

# --- ROTAS DO PAINEL DE ADMIN (sem alterações significativas) ---
@app.route('/admin')
@admin_required
def admin_dashboard():
    # ... código sem alteração ...
@app.route('/admin/products')
@admin_required
def admin_products():
    # ... código sem alteração ...
@app.route('/admin/product/add', methods=['GET', 'POST'])
@admin_required
def admin_add_product():
    # ... código sem alteração ...
@app.route('/admin/product/edit/<int:product_id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_product(product_id):
    # ... código sem alteração ...
@app.route('/admin/product/delete/<int:product_id>', methods=['POST'])
@admin_required
def admin_delete_product(product_id):
    # ... código sem alteração ...

if __name__ == '__main__':
    app.run(debug=True)