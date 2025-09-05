# app.py

import sqlite3
import pandas as pd
import numpy as np
import psycopg2
import os
import pyodbc
import json
from flask import Flask, render_template, request, redirect, url_for, session, make_response, flash, jsonify
from datetime import datetime
from functools import wraps
from fpdf import FPDF

app = Flask(__name__)
app.secret_key = 'chave-super-secreta-para-o-projeto-hortifruti'

DATABASE = 'hortifruti.db'
DIAS_PEDIDO = {0: "SEGUNDA-FEIRA", 1: "TERÇA-FEIRA", 2: "QUARTA-FEIRA", 3: "QUINTA-FEIRA", 4: "SEXTA-FEIRA", 5: "SÁBADO"}
LOJAS = ["BCS", "SJN", "MEP", "FCL1", "FCL2", "FCL3"]

# --- FUNÇÕES DE CONEXÃO E AUXILIARES ---

def get_db():
    db_url = os.environ.get('DATABASE_URL')
    if db_url:
        return psycopg2.connect(db_url)
    else:
        conn = sqlite3.connect(DATABASE)
        conn.row_factory = sqlite3.Row
        return conn

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session: return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session: return redirect(url_for('login'))
        if session.get('role') != 'admin': return "Acesso negado.", 403
        return f(*args, **kwargs)
    return decorated_function

def api_key_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = os.environ.get('API_SECRET_KEY')
        if not api_key:
            return jsonify({"message": "Chave de API não configurada no servidor."}), 500
        if request.headers.get('X-API-KEY') and request.headers.get('X-API-KEY') == api_key:
            return f(*args, **kwargs)
        else:
            return jsonify({"message": "Chave de API inválida ou ausente."}), 401
    return decorated_function

def get_products_for_day(day_id):
    db = get_db()
    cursor = db.cursor()
    db_url = os.environ.get('DATABASE_URL')
    query = "SELECT p.id, p.name, p.unidade_fracionada, p.codigo_interno, p.cost FROM products p JOIN product_availability pa ON p.id = pa.product_id WHERE pa.day_id = %s ORDER BY p.name;" if db_url else "SELECT p.id, p.name, p.unidade_fracionada, p.codigo_interno, p.cost FROM products p JOIN product_availability pa ON p.id = pa.product_id WHERE pa.day_id = ? ORDER BY p.name;"
    cursor.execute(query, (day_id,))
    products_data = cursor.fetchall()
    products_list = [dict(zip([desc[0] for desc in cursor.description], row)) for row in products_data]
    for p in products_list: p['nome'] = p.pop('name')
    cursor.close()
    db.close()
    return products_list

def obter_dados_relatorio():
    hoje_weekday = datetime.now().weekday()
    if hoje_weekday not in DIAS_PEDIDO: return None, None
    nome_dia = DIAS_PEDIDO[hoje_weekday]
    
    produtos_do_dia = get_products_for_day(hoje_weekday)
    
    for p in produtos_do_dia:
        p['custo'] = p.get('cost') or 0.0

    if not produtos_do_dia:
        return [], nome_dia

    produtos_do_dia_nomes = [p['nome'] for p in produtos_do_dia]
    db = get_db()
    hoje_str = datetime.now().strftime('%Y-%m-%d')
    query_pedidos = f"SELECT produto, tipo, loja, quantidade FROM pedidos WHERE data_pedido = '{hoje_str}'"
    df_pedidos = pd.read_sql_query(query_pedidos, db)
    db_url = os.environ.get('DATABASE_URL')
    query_pedidos_finais = "SELECT produto_nome, loja_nome, quantidade_pedida FROM pedidos_finais WHERE data_pedido = %s" if db_url else "SELECT produto_nome, loja_nome, quantidade_pedida FROM pedidos_finais WHERE data_pedido = ?"
    df_pedidos_finais = pd.read_sql(query_pedidos_finais, db, params=(hoje_str,))
    db.close()
    
    df_caixas = df_pedidos[df_pedidos['tipo'] == 'Caixa']
    df_fracionado = df_pedidos[df_pedidos['tipo'].isin(['KG', 'UN'])]
    pivot_caixas = pd.pivot_table(df_caixas, values='quantidade', index='produto', columns='loja', aggfunc='sum').reindex(index=produtos_do_dia_nomes, columns=LOJAS).fillna(0).astype(int)
    pivot_fracionado = pd.pivot_table(df_fracionado, values='quantidade', index='produto', columns='loja', aggfunc='sum').reindex(index=produtos_do_dia_nomes, columns=LOJAS).fillna(0).astype(int)
    
    pedidos_salvos = {}
    for index, row in df_pedidos_finais.iterrows():
        key = f"{row['produto_nome']}_{row['loja_nome']}"
        pedidos_salvos[key] = row['quantidade_pedida']

    report_data = []
    for produto in produtos_do_dia:
        produto_nome = produto['nome']
        produto_row = {"produto_nome": produto_nome, "custo": f"R$ {produto['custo']:.2f}".replace('.', ','), "lojas": []}
        for loja_nome in LOJAS:
            caixa_val = pivot_caixas.loc[produto_nome, loja_nome] if produto_nome in pivot_caixas.index else 0
            fracao_val = pivot_fracionado.loc[produto_nome, loja_nome] if produto_nome in pivot_fracionado.index else 0
            fracao_str = "0"
            if fracao_val > 0:
                fracao_str = f"{fracao_val} {produto['unidade_fracionada'].lower()}"
            pedido_key = f"{produto_nome}_{loja_nome}"
            pedido_salvo_val = pedidos_salvos.get(pedido_key, '')
            loja_data = {"nome": loja_nome, "caixa": caixa_val, "fracao": fracao_str, "pedido_id": f"pedido_{produto_nome.replace(' ', '_').replace('.', '')}_{loja_nome}", "pedido_salvo": pedido_salvo_val}
            produto_row["lojas"].append(loja_data)
        report_data.append(produto_row)
            
    return report_data, nome_dia

class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 15)
        self.cell(0, 10, 'Pedido de Hortifruti', 0, 1, 'C')
        self.set_font('Arial', '', 10)
        data_hoje = datetime.now().strftime('%d/%m/%Y')
        self.cell(0, 10, f'Pedido do Dia: {data_hoje}', 0, 1, 'C')
        self.ln(5)

# --- ROTAS DA APLICAÇÃO ---
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
        if user_data: user = dict(zip([desc[0] for desc in cursor.description], user_data))
        else: user = None
        cursor.close()
        db.close()
        if user:
            session['username'] = user['username']
            session['role'] = user['role']
            session['store_name'] = user['store_name']
            if user['role'] == 'admin': return redirect(url_for('relatorio'))
            else: return redirect(url_for('index'))
        else: return render_template('login.html', error='Usuario ou senha invalidos.')
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
    if session.get('role') == 'admin': return redirect(url_for('relatorio'))
    if hoje in DIAS_PEDIDO:
        nome_dia = DIAS_PEDIDO[hoje]
        produtos_do_dia = get_products_for_day(hoje)
        db = get_db()
        cursor = db.cursor()
        hoje_str = datetime.now().strftime('%Y-%m-%d')
        db_url = os.environ.get('DATABASE_URL')
        query = "SELECT produto, tipo, quantidade FROM pedidos WHERE data_pedido = %s AND loja = %s" if db_url else "SELECT produto, tipo, quantidade FROM pedidos WHERE data_pedido = ? AND loja = ?"
        cursor.execute(query, (hoje_str, loja_logada))
        dados_salvos_raw = cursor.fetchall()
        db.close()
        dados_salvos = {}
        if db_url:
            for row in dados_salvos_raw:
                produto, tipo, quantidade = row[0], row[1], row[2]
                if tipo == 'Caixa': dados_salvos[f"caixas_{produto}"] = quantidade
                else: dados_salvos[f"fracionado_{produto}"] = quantidade
        else:
            for row in dados_salvos_raw:
                if row['tipo'] == 'Caixa': dados_salvos[f"caixas_{row['produto']}"] = row['quantidade']
                else: dados_salvos[f"fracionado_{row['produto']}"] = row['quantidade']
        return render_template('index.html', dia=nome_dia, produtos=produtos_do_dia, loja_logada=loja_logada, dados_salvos=dados_salvos)
    else:
        return render_template('inativo.html')

@app.route('/enviar', methods=['POST'])
@login_required
def enviar_pedido():
    loja = session.get('store_name')
    if not loja: return "Erro: Usuario nao associado a uma loja.", 400
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
                if nome_produto in produtos_map: tipo = produtos_map[nome_produto]
            if tipo and nome_produto: cursor.execute(insert_query, (data_pedido_str, loja, nome_produto, tipo, quantidade))
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
    report_data, nome_dia = obter_dados_relatorio()
    if report_data is None:
        return "<h1>Hoje nao e um dia de pedido, portanto nao ha relatorio.</h1>"
    return render_template('relatorio.html', report_data=report_data, lojas=LOJAS, data_hoje=datetime.now().strftime('%d/%m/%Y'))

@app.route('/salvar-pedido', methods=['POST'])
@admin_required
def salvar_pedido():
    pedido_data_str = request.form.get('pedido_data')
    if not pedido_data_str:
        return {"status": "error", "message": "Nenhum dado recebido."}, 400
    pedidos = json.loads(pedido_data_str)
    hoje_str = datetime.now().strftime('%Y-%m-%d')
    db = get_db()
    cursor = db.cursor()
    db_url = os.environ.get('DATABASE_URL')
    try:
        delete_query = "DELETE FROM pedidos_finais WHERE data_pedido = %s" if db_url else "DELETE FROM pedidos_finais WHERE data_pedido = ?"
        cursor.execute(delete_query, (hoje_str,))
        if pedidos:
            insert_query = "INSERT INTO pedidos_finais (data_pedido, produto_nome, loja_nome, quantidade_pedida) VALUES (%s, %s, %s, %s)" if db_url else "INSERT INTO pedidos_finais (data_pedido, produto_nome, loja_nome, quantidade_pedida) VALUES (?, ?, ?, ?)"
            dados_para_inserir = [(hoje_str, p['produto'], p['loja'], int(p['pedido'])) for p in pedidos]
            cursor.executemany(insert_query, dados_para_inserir)
        db.commit()
        message = {"status": "success", "message": "Pedido salvo com sucesso!"}
    except Exception as e:
        db.rollback()
        message = {"status": "error", "message": f"Erro ao salvar: {e}"}
    finally:
        cursor.close()
        db.close()
    return message

# --- ROTAS DO PAINEL DE ADMIN ---
@app.route('/admin')
@admin_required
def admin_dashboard():
    return render_template('admin/dashboard.html')

@app.route('/admin/products')
@admin_required
def admin_products():
    db = get_db()
    cursor = db.cursor()
    db_url = os.environ.get('DATABASE_URL')
    query = "SELECT p.id, p.name, p.unidade_fracionada, p.codigo_interno, STRING_AGG(CAST(pa.day_id AS TEXT), ',') as days_str FROM products p LEFT JOIN product_availability pa ON p.id = pa.product_id GROUP BY p.id, p.name, p.unidade_fracionada, p.codigo_interno ORDER BY p.name;" if db_url else "SELECT p.id, p.name, p.unidade_fracionada, p.codigo_interno, GROUP_CONCAT(pa.day_id) as days_str FROM products p LEFT JOIN product_availability pa ON p.id = pa.product_id GROUP BY p.id, p.name, p.unidade_fracionada, p.codigo_interno ORDER BY p.name;"
    cursor.execute(query)
    products_data = cursor.fetchall()
    products_list = [dict(zip([desc[0] for desc in cursor.description], row)) for row in products_data]
    db.close()
    id_to_day_name = {v: k for k, v in DIAS_PEDIDO.items()}
    for product in products_list:
        if product['days_str']:
            day_ids = [int(i) for i in product['days_str'].split(',')]
            product['days'] = sorted([id_to_day_name.get(day_id, '') for day_id in day_ids])
        else: product['days'] = []
    return render_template('admin/products.html', products=products_list)

@app.route('/admin/product/add', methods=['GET', 'POST'])
@admin_required
def admin_add_product():
    if request.method == 'POST':
        name = request.form['name']
        unidade = request.form['unidade_fracionada']
        codigo_interno = request.form.get('codigo_interno')
        days = request.form.getlist('days')
        db = get_db()
        cursor = db.cursor()
        db_url = os.environ.get('DATABASE_URL')
        try:
            if db_url:
                cursor.execute("INSERT INTO products (name, unidade_fracionada, codigo_interno) VALUES (%s, %s, %s) RETURNING id;", (name, unidade, codigo_interno))
                product_id = cursor.fetchone()[0]
            else:
                cursor.execute("INSERT INTO products (name, unidade_fracionada, codigo_interno) VALUES (?, ?, ?);", (name, unidade, codigo_interno))
                product_id = cursor.lastrowid
            for day_id in days:
                if db_url: cursor.execute("INSERT INTO product_availability (product_id, day_id) VALUES (%s, %s);", (product_id, int(day_id)))
                else: cursor.execute("INSERT INTO product_availability (product_id, day_id) VALUES (?, ?);", (product_id, int(day_id)))
            db.commit()
            flash('Produto adicionado com sucesso!', 'success')
        except Exception as e:
            db.rollback()
            if 'UNIQUE constraint failed' in str(e) or 'duplicate key value violates unique constraint' in str(e): flash(f'Erro: O produto ou codigo interno "{name}" ja existe.', 'danger')
            else: flash(f'Erro ao adicionar produto: {e}', 'danger')
        finally:
            cursor.close()
            db.close()
        return redirect(url_for('admin_products'))
    dias_semana_ordenado = {k: v for k, v in sorted(DIAS_PEDIDO.items())}
    return render_template('admin/product_form.html', dias_pedido=dias_semana_ordenado, product=None)

@app.route('/admin/product/edit/<int:product_id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_product(product_id):
    db = get_db()
    cursor = db.cursor()
    db_url = os.environ.get('DATABASE_URL')
    if request.method == 'POST':
        name = request.form['name']
        unidade = request.form['unidade_fracionada']
        codigo_interno = request.form.get('codigo_interno')
        days = request.form.getlist('days')
        try:
            cursor.execute("UPDATE products SET name = %s, unidade_fracionada = %s, codigo_interno = %s WHERE id = %s;" if db_url else "UPDATE products SET name = ?, unidade_fracionada = ?, codigo_interno = ? WHERE id = ?;", (name, unidade, codigo_interno, product_id))
            cursor.execute("DELETE FROM product_availability WHERE product_id = %s;" if db_url else "DELETE FROM product_availability WHERE product_id = ?;", (product_id,))
            for day_id in days:
                if db_url: cursor.execute("INSERT INTO product_availability (product_id, day_id) VALUES (%s, %s);", (product_id, int(day_id)))
                else: cursor.execute("INSERT INTO product_availability (product_id, day_id) VALUES (?, ?);", (product_id, int(day_id)))
            db.commit()
            flash('Produto atualizado com sucesso!', 'success')
        except Exception as e:
            db.rollback()
            flash(f'Erro ao atualizar produto: {e}', 'danger')
        finally:
            cursor.close()
            db.close()
        return redirect(url_for('admin_products'))
    cursor.execute("SELECT * FROM products WHERE id = %s;" if db_url else "SELECT * FROM products WHERE id = ?;", (product_id,))
    product_data = cursor.fetchone()
    product = dict(zip([desc[0] for desc in cursor.description], product_data))
    cursor.execute("SELECT day_id FROM product_availability WHERE product_id = %s;" if db_url else "SELECT day_id FROM product_availability WHERE product_id = ?;", (product_id,))
    availability_data = cursor.fetchall()
    product['days_ids'] = [row[0] for row in availability_data]
    cursor.close()
    db.close()
    dias_semana_ordenado = {k: v for k, v in sorted(DIAS_PEDIDO.items())}
    return render_template('admin/product_form.html', dias_pedido=dias_semana_ordenado, product=product)

@app.route('/admin/product/delete/<int:product_id>', methods=['POST'])
@admin_required
def admin_delete_product(product_id):
    db = get_db()
    cursor = db.cursor()
    db_url = os.environ.get('DATABASE_URL')
    try:
        cursor.execute("DELETE FROM product_availability WHERE product_id = %s;" if db_url else "DELETE FROM product_availability WHERE product_id = ?;", (product_id,))
        cursor.execute("DELETE FROM products WHERE id = %s;" if db_url else "DELETE FROM products WHERE id = ?;", (product_id,))
        db.commit()
        flash('Produto apagado com sucesso!', 'success')
    except Exception as e:
        db.rollback()
        flash(f'Erro ao apagar produto: {e}', 'danger')
    finally:
        cursor.close()
        db.close()
    return redirect(url_for('admin_products'))

@app.route('/exportar-pedido-pdf', methods=['POST'])
@admin_required
def exportar_pedido_pdf():
    pedido_data_str = request.form.get('pedido_data')
    if not pedido_data_str:
        return "Nenhum dado de pedido recebido.", 400
    pedidos = json.loads(pedido_data_str)
    df = pd.DataFrame(pedidos)
    tabela_pedido = pd.pivot_table(df, values='pedido', index='produto', columns='loja', aggfunc='sum').fillna(0).astype(int)
    tabela_pedido = tabela_pedido.reindex(columns=LOJAS).fillna(0).astype(int)
    pdf = PDF(orientation='P', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_font('Arial', size=9)
    col_widths = [75] + [18] * len(tabela_pedido.columns)
    line_height = pdf.font_size * 2
    pdf.set_font('Arial', 'B', 9)
    headers = ['Produto'] + list(tabela_pedido.columns)
    for i, header in enumerate(headers):
        pdf.cell(col_widths[i], line_height, header, border=1, align='C')
    pdf.ln(line_height)
    pdf.set_font('Arial', '', 9)
    for produto, row in tabela_pedido.iterrows():
        try:
            produto_encoded = produto.encode('latin-1', 'replace').decode('latin-1')
        except:
            produto_encoded = 'Produto Invalido'
        pdf.cell(col_widths[0], line_height, produto_encoded, border=1)
        for i, value in enumerate(row):
            display_value = str(value) if value > 0 else ''
            pdf.cell(col_widths[i+1], line_height, display_value, border=1, align='C')
        pdf.ln(line_height)
    data_hoje_str = datetime.now().strftime('%d-%m-%Y')
    nome_arquivo = f'pedido_hortifruti_{data_hoje_str}.pdf'
    pdf_output = pdf.output()
    final_pdf_bytes = bytes(pdf_output)
    response = make_response(final_pdf_bytes)
    response.headers.set('Content-Type', 'application/pdf')
    response.headers.set('Content-Disposition', 'attachment', filename=nome_arquivo)
    return response

if __name__ == '__main__':
    app.run(debug=True)