# app.py

import sqlite3
import os
import json
from contextlib import closing
from report_data import DAY_NAMES, normalized_date, build_report, aggregate_orders
from flask import Flask, render_template, request, redirect, url_for, session, make_response, flash, jsonify
from datetime import datetime, date
from functools import wraps

app = Flask(__name__, static_folder='static')
app.secret_key = os.environ.get('SECRET_KEY')
if not app.secret_key:
    if os.environ.get('DATABASE_URL'):
        raise RuntimeError("Configure SECRET_KEY no ambiente antes de iniciar o servidor.")
    app.secret_key = os.urandom(32)
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 3600

DATABASE = 'hortifruti.db'
DIAS_PEDIDO = {0: "SEGUNDA-FEIRA", 1: "TERÇA-FEIRA", 2: "QUARTA-FEIRA", 4: "SEXTA-FEIRA", 5: "SÁBADO"}
LOJAS = ["BCS", "SJN", "FCL2", "MEP", "FCL3", "FCL4"]

# --- FUNÇÕES DE CONEXÃO E DECORATORS ---

def get_db():
    db_url = os.environ.get('DATABASE_URL')
    if db_url:
        import psycopg2
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

# --- FUNÇÕES AUXILIARES DE DADOS ---

def get_products_for_day(day_id, db=None):
    owns_connection = db is None
    db = db if db is not None else get_db()
    try:
        with closing(db.cursor()) as cursor:
            placeholder = "%s" if os.environ.get('DATABASE_URL') else "?"
            cursor.execute(
                "SELECT p.id, p.name AS nome, p.unidade_fracionada, p.codigo_interno, p.cost "
                "FROM products p JOIN product_availability pa ON p.id = pa.product_id "
                f"WHERE pa.day_id = {placeholder} ORDER BY p.name", (day_id,))
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
    finally:
        if owns_connection:
            db.close()


def obter_dados_relatorio(data_selecionada_str):
    data_obj = normalized_date(data_selecionada_str)
    day = data_obj.weekday()
    placeholder = "%s" if os.environ.get('DATABASE_URL') else "?"
    with closing(get_db()) as db, closing(db.cursor()) as cursor:
        cursor.execute(f"SELECT ativo FROM dias_semana_config WHERE dia_id = {placeholder}", (day,))
        config = cursor.fetchone()
        active = bool(config[0]) if config is not None else day in DIAS_PEDIDO
        if not active:
            return "INATIVO", None, None
        products = get_products_for_day(day, db)
        if not products:
            return [], DAY_NAMES[day], data_obj
        # Aggregate at the database, so Python receives one row per product/type/store.
        cursor.execute(
            "SELECT produto, tipo, loja, SUM(quantidade) FROM pedidos "
            f"WHERE data_pedido = {placeholder} GROUP BY produto, tipo, loja",
            (data_obj.isoformat(),))
        counts = cursor.fetchall()
        cursor.execute(
            "SELECT produto_nome, loja_nome, quantidade_pedida FROM pedidos_finais "
            f"WHERE data_pedido = {placeholder}", (data_obj.isoformat(),))
        orders = cursor.fetchall()
    return build_report(products, counts, orders, LOJAS), DAY_NAMES[day], data_obj


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
    
    # Verificar se o dia da semana está ativo na configuração
    db = get_db()
    cursor = db.cursor()
    db_url = os.environ.get('DATABASE_URL')
    query = "SELECT ativo FROM dias_semana_config WHERE dia_id = %s;" if db_url else "SELECT ativo FROM dias_semana_config WHERE dia_id = ?;"
    cursor.execute(query, (hoje,))
    result = cursor.fetchone()
    cursor.close()
    db.close()
    
    # Se não encontrou na configuração ou está inativo, usar lógica antiga
    dia_ativo = result and result[0] if result else (hoje in DIAS_PEDIDO)
    
    # Se o dia não está ativo, mostrar tela inativa baseada no tipo de usuário
    if not dia_ativo:
        if session.get('role') == 'admin':
            return render_template('relatorio_inativo.html', 
                                   data_selecionada=datetime.now().strftime('%Y-%m-%d'),
                                   data_formatada=datetime.now().strftime('%d/%m/%Y'))
        else:
            return render_template('inativo.html')
    
    # Se é admin e o dia está ativo, ir para relatório
    if session.get('role') == 'admin': 
        return redirect(url_for('relatorio'))
    
    # Se é usuário normal e o dia está ativo, mostrar contagem
    if dia_ativo:
        nome_dia = DAY_NAMES[hoje]
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
    hoje_weekday = datetime.now().weekday()
    produtos_do_dia = get_products_for_day(hoje_weekday)
    produtos_map = {p['nome']: p['unidade_fracionada'] for p in produtos_do_dia}
    rows = []
    for key, value in request.form.items():
        prefix, _, name = key.partition('_')
        if prefix not in ('caixas', 'fracionado') or name not in produtos_map:
            continue
        try:
            quantity = int(value) if value else 0
            if quantity < 0:
                raise ValueError
        except ValueError:
            return "Informe quantidades inteiras maiores ou iguais a zero.", 400
        if quantity:
            kind = 'Caixa' if prefix == 'caixas' else produtos_map[name]
            rows.append((data_pedido_str, loja, name, kind, quantity))
    db = get_db()
    cursor = db.cursor()
    db_url = os.environ.get('DATABASE_URL')
    if db_url:
        delete_query = "DELETE FROM pedidos WHERE data_pedido = %s AND loja = %s"
        insert_query = "INSERT INTO pedidos (data_pedido, loja, produto, tipo, quantidade) VALUES (%s, %s, %s, %s, %s)"
    else:
        delete_query = "DELETE FROM pedidos WHERE data_pedido = ? AND loja = ?"
        insert_query = "INSERT INTO pedidos (data_pedido, loja, produto, tipo, quantidade) VALUES (?, ?, ?, ?, ?)"
    try:
        cursor.execute(delete_query, (data_pedido_str, loja))
        cursor.executemany(insert_query, rows)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
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
    data_selecionada = normalized_date(request.args.get('data')).isoformat()
    report_data, nome_dia, data_obj = obter_dados_relatorio(data_selecionada)
    
    # Se o dia está inativo na configuração
    if report_data == "INATIVO":
        return render_template('relatorio_inativo.html', 
                               data_selecionada=data_selecionada, 
                               data_formatada=datetime.strptime(data_selecionada, '%Y-%m-%d').strftime('%d/%m/%Y'))
    
    # Se não há dados (dia não está no DIAS_PEDIDO)
    if report_data is None:
        return render_template('relatorio_inativo.html', 
                               data_selecionada=data_selecionada, 
                               data_formatada=datetime.strptime(data_selecionada, '%Y-%m-%d').strftime('%d/%m/%Y'))
    
    # Se há dados, mostrar relatório normal
    return render_template('relatorio.html', 
                           report_data=report_data, 
                           lojas=LOJAS,
                           data_hoje=data_obj.strftime('%d/%m/%Y'),
                           data_selecionada=data_selecionada)

@app.route('/salvar-pedido', methods=['POST'])
@admin_required
def salvar_pedido():
    pedido_data_str = request.form.get('pedido_data')
    data_do_pedido = request.form.get('data_pedido_form', date.today().strftime('%Y-%m-%d'))
    if not pedido_data_str:
        return {"status": "error", "message": "Nenhum dado recebido."}, 400
    pedidos = json.loads(pedido_data_str)
    db = get_db()
    cursor = db.cursor()
    db_url = os.environ.get('DATABASE_URL')
    try:
        delete_query = "DELETE FROM pedidos_finais WHERE data_pedido = %s" if db_url else "DELETE FROM pedidos_finais WHERE data_pedido = ?"
        cursor.execute(delete_query, (data_do_pedido,))
        if pedidos:
            insert_query = "INSERT INTO pedidos_finais (data_pedido, produto_nome, loja_nome, quantidade_pedida) VALUES (%s, %s, %s, %s)" if db_url else "INSERT INTO pedidos_finais (data_pedido, produto_nome, loja_nome, quantidade_pedida) VALUES (?, ?, ?, ?)"
            dados_para_inserir = [(data_do_pedido, p['produto'], p['loja'], int(p['pedido'])) for p in pedidos]
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
    id_to_day_name = DAY_NAMES
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

# --- ROTAS PARA GERENCIAR DIAS DE CONTAGEM ---
@app.route('/admin/dias-contagem')
@admin_required
def admin_dias_contagem():
    db = get_db()
    cursor = db.cursor()
    db_url = os.environ.get('DATABASE_URL')
    
    # Buscar configuração dos dias da semana
    query = "SELECT dia_id, nome_dia, ativo FROM dias_semana_config ORDER BY dia_id;"
    cursor.execute(query)
    dias_data = cursor.fetchall()
    dias_list = [dict(zip([desc[0] for desc in cursor.description], row)) for row in dias_data]
    
    cursor.close()
    db.close()
    return render_template('admin/dias_contagem.html', dias=dias_list)

# Removidas rotas desnecessárias - apenas ativar/desativar dias da semana

@app.route('/admin/lojas')
@admin_required
def admin_lojas():
    """Lista todas as lojas e seus usuários"""
    db = get_db()
    cursor = db.cursor()
    db_url = os.environ.get('DATABASE_URL')
    
    # Buscar todos os usuários de loja
    query = "SELECT username, store_name, role FROM users WHERE role = 'loja' ORDER BY store_name;"
    cursor.execute(query)
    users_data = cursor.fetchall()
    users_list = [dict(zip([desc[0] for desc in cursor.description], row)) for row in users_data]
    
    cursor.close()
    db.close()
    
    # Criar dicionário de lojas com seus usuários
    lojas_dict = {}
    for loja_nome in LOJAS:
        lojas_dict[loja_nome] = {
            'nome': loja_nome,
            'usuarios': [u for u in users_list if u['store_name'] == loja_nome]
        }
    
    return render_template('admin/lojas.html', lojas=lojas_dict, todas_lojas=LOJAS)

@app.route('/admin/dias-contagem/toggle/<int:dia_id>', methods=['POST'])
@admin_required
def admin_toggle_dia_contagem(dia_id):
    db = get_db()
    cursor = db.cursor()
    db_url = os.environ.get('DATABASE_URL')
    
    try:
        # Buscar o status atual
        cursor.execute("SELECT ativo, nome_dia FROM dias_semana_config WHERE dia_id = %s;" if db_url else "SELECT ativo, nome_dia FROM dias_semana_config WHERE dia_id = ?;", (dia_id,))
        result = cursor.fetchone()
        if result:
            ativo_atual, nome_dia = result[0], result[1]
            novo_status = not ativo_atual
            cursor.execute("UPDATE dias_semana_config SET ativo = %s WHERE dia_id = %s;" if db_url else "UPDATE dias_semana_config SET ativo = ? WHERE dia_id = ?;", (novo_status, dia_id))
            db.commit()
            status_text = "ativado" if novo_status else "desativado"
            flash(f'{nome_dia} {status_text} com sucesso!', 'success')
        else:
            flash('Dia da semana não encontrado.', 'danger')
    except Exception as e:
        db.rollback()
        flash(f'Erro ao alterar status: {e}', 'danger')
    finally:
        cursor.close()
        db.close()
    return redirect(url_for('admin_dias_contagem'))

@app.route('/exportar-pedido-pdf', methods=['POST'])
@admin_required
def exportar_pedido_pdf():
    pedido_data_str = request.form.get('pedido_data')
    data_do_pedido = request.form.get('data_pedido_pdf', date.today().strftime('%Y-%m-%d'))
    if not pedido_data_str:
        return "Nenhum dado de pedido recebido.", 400
    pedidos = json.loads(pedido_data_str)
    from fpdf import FPDF

    class PDF(FPDF):
        def header(self):
            self.set_font('Helvetica', 'B', 15)
            self.cell(0, 10, 'Pedido de Hortifruti', new_x="LMARGIN", new_y="NEXT", align='C')
            self.set_font('Helvetica', '', 10)
            self.cell(0, 10, f'Pedido do Dia: {normalized_date(data_do_pedido).strftime("%d/%m/%Y")}',
                      new_x="LMARGIN", new_y="NEXT", align='C')
            self.ln(5)

    tabela_pedido = aggregate_orders(pedidos)
    pdf = PDF(orientation='P', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_font('Helvetica', size=9)
    col_widths = [75] + [18] * len(LOJAS)
    line_height = pdf.font_size * 2
    pdf.set_font('Helvetica', 'B', 9)
    headers = ['Produto'] + LOJAS
    for i, header in enumerate(headers):
        pdf.cell(col_widths[i], line_height, header, border=1, align='C')
    pdf.ln(line_height)
    pdf.set_font('Helvetica', '', 9)
    for produto, row in tabela_pedido:
        try:
            produto_encoded = produto.encode('latin-1', 'replace').decode('latin-1')
        except:
            produto_encoded = 'Produto Invalido'
        pdf.cell(col_widths[0], line_height, produto_encoded, border=1)
        for i, loja in enumerate(LOJAS):
            value = row.get(loja, 0)
            display_value = str(value) if value > 0 else ''
            pdf.cell(col_widths[i+1], line_height, display_value, border=1, align='C')
        pdf.ln(line_height)
    nome_arquivo = f'pedido_hortifruti_{datetime.strptime(data_do_pedido, "%Y-%m-%d").strftime("%d-%m-%Y")}.pdf'
    pdf_output = pdf.output()
    final_pdf_bytes = bytes(pdf_output)
    response = make_response(final_pdf_bytes)
    response.headers.set('Content-Type', 'application/pdf')
    response.headers.set('Content-Disposition', 'attachment', filename=nome_arquivo)
    return response

@app.route('/api/update-costs', methods=['POST'])
@api_key_required
def update_costs():
    data = request.json
    if not data or 'costs' not in data:
        return jsonify({"message": "Dados inválidos."}), 400
    costs_list = data['costs']
    db = get_db()
    cursor = db.cursor()
    db_url = os.environ.get('DATABASE_URL')
    updates = 0
    try:
        for item in costs_list:
            codigo = item.get('codigo_interno')
            custo = item.get('custo')
            if codigo and custo is not None:
                if db_url:
                    cursor.execute("UPDATE products SET cost = %s WHERE codigo_interno = %s;", (custo, codigo))
                else: # SQLite
                    cursor.execute("UPDATE products SET cost = ? WHERE codigo_interno = ?;", (custo, codigo))
                updates += cursor.rowcount
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Erro ao atualizar custos: {e}")
        return jsonify({"message": "Ocorreu um erro durante a atualização."}), 500
    finally:
        cursor.close()
        db.close()
    return jsonify({"message": f"{updates} produtos tiveram seus custos atualizados com sucesso."}), 200

if __name__ == '__main__':
    app.run(debug=True)
