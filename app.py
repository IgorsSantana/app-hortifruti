# app.py - Versão com a base do Painel de Administrador

import sqlite3
import pandas as pd
import numpy as np
import psycopg2
import os
from flask import Flask, render_template, request, redirect, url_for, session
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
    """Busca no banco de dados a lista de produtos para um determinado dia da semana."""
    db = get_db()
    cursor = db.cursor()
    
    db_url = os.environ.get('DATABASE_URL')
    if db_url: # PostgreSQL
        query = """
            SELECT p.name, p.unidade_fracionada 
            FROM products p 
            JOIN product_availability pa ON p.id = pa.product_id 
            WHERE pa.day_id = %s 
            ORDER BY p.name;
        """
    else: # SQLite
        query = """
            SELECT p.name, p.unidade_fracionada 
            FROM products p 
            JOIN product_availability pa ON p.id = pa.product_id 
            WHERE pa.day_id = ? 
            ORDER BY p.name;
        """
    
    cursor.execute(query, (day_id,))
    products_data = cursor.fetchall()
    
    # Converte o resultado (lista de tuplas) em uma lista de dicionários
    products_list = [dict(zip([desc[0] for desc in cursor.description], row)) for row in products_data]
    
    # Renomeia as chaves para corresponder ao que o template espera ('nome')
    for p in products_list:
        p['nome'] = p.pop('name')

    cursor.close()
    db.close()
    return products_list

def obter_dados_relatorio():
    hoje_weekday = datetime.now().weekday()
    if hoje_weekday not in DIAS_PEDIDO:
        return None, None
    
    nome_dia = DIAS_PEDIDO[hoje_weekday]
    produtos_do_dia_dict = get_products_for_day(hoje_weekday)
    if not produtos_do_dia_dict:
        return pd.DataFrame(columns=LOJAS), nome_dia

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
            
    return tabela_final, nome_dia

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        db = get_db()
        cursor = db.cursor()
        
        db_url = os.environ.get('DATABASE_URL')
        query = "SELECT * FROM users WHERE username = %s AND password = %s" if db_url else "SELECT * FROM users WHERE username = ? AND password = ?"
        
        cursor.execute(query, (username, password))
        user_data = cursor.fetchone()
        
        if user_data:
            user = dict(zip([desc[0] for desc in cursor.description], user_data))
        else:
            user = None
        cursor.close()
        db.close()
        if user:
            session['username'] = user['username']
            session['role'] = user['role']
            session['store_name'] = user['store_name']
            if user['role'] == 'admin':
                return redirect(url_for('relatorio'))
            else:
                return redirect(url_for('index'))
        else:
            return render_template('login.html', error='Usuario ou senha invalidos.')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    hoje = datetime.now().weekday()
    loja_logada = session.get('store_name')
    if session.get('role') == 'admin':
        return redirect(url_for('relatorio'))
    if hoje in DIAS_PEDIDO:
        nome_dia = DIAS_PEDIDO[hoje]
        produtos_do_dia = get_products_for_day(hoje)
        return render_template('index.html', dia=nome_dia, produtos=produtos_do_dia, loja_logada=loja_logada)
    else:
        return render_template('inativo.html')

@app.route('/enviar', methods=['POST'])
@login_required
def enviar_pedido():
    loja = session.get('store_name')
    if not loja:
        return "Erro: Usuario nao associado a uma loja.", 400
    
    data_pedido_str = datetime.now().strftime('%Y-%m-%d')
    db = get_db()
    cursor = db.cursor()
    
    hoje_weekday = datetime.now().weekday()
    produtos_do_dia = get_products_for_day(hoje_weekday)
    produtos_map = {p['nome']: p['unidade_fracionada'] for p in produtos_do_dia}

    db_url = os.environ.get('DATABASE_URL')
    if db_url:
        delete_query = "DELETE FROM pedidos WHERE data_pedido = %s AND loja = %s"
        insert_query = "INSERT INTO pedidos (data_pedido, loja, produto, tipo, quantidade) VALUES (%s, %s, %s, %s, %s)"
        cursor.execute(delete_query, (data_pedido_str, loja))
    else:
        delete_query = "DELETE FROM pedidos WHERE data_pedido = ? AND loja = ?"
        insert_query = "INSERT INTO pedidos (data_pedido, loja, produto, tipo, quantidade) VALUES (?, ?, ?, ?, ?)"
        cursor.execute(delete_query, (data_pedido_str, loja))
    
    for key, quantidade_str in request.form.items():
        if quantidade_str and int(quantidade_str) > 0:
            quantidade = int(quantidade_str)
            tipo = None
            nome_produto = None
            
            if key.startswith('caixas_'):
                tipo = 'Caixa'
                nome_produto = key.replace('caixas_', '')
            elif key.startswith('fracionado_'):
                nome_produto = key.replace('fracionado_', '')
                if nome_produto in produtos_map:
                    tipo = produtos_map[nome_produto]

            if tipo and nome_produto:
                cursor.execute(insert_query, (data_pedido_str, loja, nome_produto, tipo, quantidade))
    
    db.commit()
    cursor.close()
    db.close()
    return redirect(url_for('sucesso'))
    
@app.route('/sucesso')
@login_required
def sucesso():
    return render_template('sucesso.html')

@app.route('/relatorio')
@admin_required
def relatorio():
    tabela_final, nome_dia = obter_dados_relatorio()
    if tabela_final is None:
        return "<h1>Hoje nao e um dia de pedido, portanto nao ha relatorio.</h1>"
    
    tabela_final.index.name = None
    html_table = tabela_final.to_html(classes='table table-bordered table-striped table-hover', border=0, table_id='relatorio-tabela')
    return render_template('relatorio.html', tabela_html=html_table, data_hoje=datetime.now().strftime('%d/%m/%Y'))

# --- NOVAS ROTAS DO PAINEL DE ADMIN ---

@app.route('/admin')
@admin_required
def admin_dashboard():
    return render_template('admin/dashboard.html')

@app.route('/admin/products')
@admin_required
def admin_products():
    db = get_db()
    cursor = db.cursor()
    
    # Busca todos os produtos
    cursor.execute("SELECT * FROM products ORDER BY name;")
    products_data = cursor.fetchall()
    
    # Busca a disponibilidade de todos os produtos
    cursor.execute("SELECT * FROM product_availability;")
    availability_data = cursor.fetchall()
    
    db.close()
    
    # Converte os resultados em dicionários para facilitar o uso
    products_dicts = [dict(zip([desc[0] for desc in cursor.description], row)) for row in products_data]
    availability_dicts = [dict(zip([desc[0] for desc in cursor.description], row)) for row in availability_data]

    # Organiza a disponibilidade por produto
    availability_map = {}
    for row in availability_dicts:
        product_id = row['product_id']
        day_id = row['day_id']
        if product_id not in availability_map:
            availability_map[product_id] = []
        
        for dia_nome, dia_num in DIAS_PEDIDO.items():
            if dia_num == day_id:
                availability_map[product_id].append(dia_nome)
                break

    # Combina os dados para enviar ao template
    for product in products_dicts:
        product['days'] = sorted(availability_map.get(product['id'], []))
        
    return render_template('admin/products.html', products=products_dicts)


if __name__ == '__main__':
    app.run(debug=True)