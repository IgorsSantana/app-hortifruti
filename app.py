# app.py - Versão final e simplificada (SOLUÇÃO 1 - RECOMENDADA)

import sqlite3
import pandas as pd
import numpy as np
from flask import Flask, render_template, request, redirect, url_for, session
from datetime import datetime
from functools import wraps

from produtos_config import PRODUTOS

app = Flask(__name__)
app.secret_key = 'chave-super-secreta-para-o-projeto-hortifruti'

DATABASE = 'hortifruti.db'
DIAS_PEDIDO = {0: "SEGUNDA-FEIRA", 1: "TERÇA-FEIRA", 2: "QUARTA-FEIRA", 4: "SEXTA-FEIRA", 5: "SÁBADO"}
LOJAS = ["BCS", "SJN", "MEP", "FCL1", "FCL2", "FCL3"]

def get_db():
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

def obter_dados_relatorio():
    hoje_weekday = datetime.now().weekday()
    if hoje_weekday not in DIAS_PEDIDO:
        return None, None
    nome_dia = DIAS_PEDIDO[hoje_weekday]
    produtos_do_dia = PRODUTOS[nome_dia]
    db = get_db()
    hoje_str = datetime.now().strftime('%Y-%m-%d')
    query = f"SELECT produto, tipo, loja, quantidade FROM pedidos WHERE data_pedido = '{hoje_str}'"
    df_pedidos = pd.read_sql_query(query, db)
    db.close()
    df_caixas = df_pedidos[df_pedidos['tipo'] == 'Caixa']
    df_unidades = df_pedidos[df_pedidos['tipo'] == 'Unidade']
    pivot_caixas = pd.pivot_table(df_caixas, values='quantidade', index='produto', columns='loja', aggfunc='sum')
    pivot_unidades = pd.pivot_table(df_unidades, values='quantidade', index='produto', columns='loja', aggfunc='sum')
    pivot_caixas = pivot_caixas.reindex(index=produtos_do_dia, columns=LOJAS).fillna(0).astype(int)
    pivot_unidades = pivot_unidades.reindex(index=produtos_do_dia, columns=LOJAS).fillna(0).astype(int)
    def formatar_celula(cx, un):
        cx_str = f"{cx} cx" if cx > 0 else ""
        un_str = f"{un} kg" if un > 0 else ""
        if cx > 0 and un > 0: return f"{cx_str} {un_str}"
        elif cx > 0: return cx_str
        elif un > 0: return un_str
        else: return "0 kg"
    tabela_final = pd.DataFrame(index=pivot_caixas.index, columns=pivot_caixas.columns)
    for produto in tabela_final.index:
        for loja in tabela_final.columns:
            cx_val = pivot_caixas.loc[produto, loja]
            un_val = pivot_unidades.loc[produto, loja]
            tabela_final.loc[produto, loja] = formatar_celula(cx_val, un_val)
    return tabela_final, nome_dia

@app.route('/login', methods=['GET', 'POST'])
def login():
    # ... código sem alteração ...
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        db = get_db()
        user = db.execute('SELECT * FROM users WHERE username = ? AND password = ?', (username, password)).fetchone()
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
        produtos_do_dia = PRODUTOS[nome_dia]
        return render_template('index.html', dia=nome_dia, produtos=produtos_do_dia, loja_logada=loja_logada)
    else:
        return "<h1>Hoje nao e um dia de fazer pedidos.</h1>"

@app.route('/enviar', methods=['POST'])
@login_required
def enviar_pedido():
    # ... código sem alteração ...
    loja = session.get('store_name')
    if not loja:
        return "Erro: Usuario nao associado a uma loja.", 400
    data_pedido_str = datetime.now().strftime('%Y-%m-%d')
    db = get_db()
    db.execute('DELETE FROM pedidos WHERE data_pedido = ? AND loja = ?', (data_pedido_str, loja))
    for key, quantidade_str in request.form.items():
        if key.startswith('caixas_') or key.startswith('unidades_'):
            if quantidade_str and int(quantidade_str) > 0:
                quantidade = int(quantidade_str)
                tipo = 'Caixa' if key.startswith('caixas_') else 'Unidade'
                nome_produto = key.replace('caixas_', '').replace('unidades_', '')
                db.execute('INSERT INTO pedidos (data_pedido, loja, produto, tipo, quantidade) VALUES (?, ?, ?, ?, ?)', (data_pedido_str, loja, nome_produto, tipo, quantidade))
    db.commit()
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

if __name__ == '__main__':
    app.run(debug=True)