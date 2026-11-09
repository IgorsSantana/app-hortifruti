import json
import os
import sqlite3
import secrets
import tempfile
import unittest
import io
from contextlib import redirect_stdout
from contextlib import closing
from datetime import date
from pathlib import Path
from unittest.mock import patch

import app as module
from report_data import aggregate_orders


SCHEMA = """
CREATE TABLE users(id INTEGER PRIMARY KEY, username TEXT, password TEXT, role TEXT, store_name TEXT);
CREATE TABLE products(id INTEGER PRIMARY KEY, name TEXT, unidade_fracionada TEXT, codigo_interno TEXT, cost NUMERIC);
CREATE TABLE product_availability(product_id INTEGER, day_id INTEGER, PRIMARY KEY(product_id,day_id));
CREATE TABLE dias_semana_config(dia_id INTEGER PRIMARY KEY, nome_dia TEXT, ativo BOOLEAN);
CREATE TABLE pedidos(id INTEGER PRIMARY KEY, data_pedido TEXT, loja TEXT, produto TEXT, tipo TEXT, quantidade INTEGER);
CREATE TABLE pedidos_finais(id INTEGER PRIMARY KEY, data_pedido TEXT, produto_nome TEXT, loja_nome TEXT, quantidade_pedida INTEGER);
"""


def seed_database(path):
    password = secrets.token_urlsafe(24)
    with closing(sqlite3.connect(path)) as db:
        db.executescript(SCHEMA)
        db.executemany("INSERT INTO users VALUES(?,?,?,?,?)", [
            (1, 'demo', password, 'loja', 'BCS'), (2, 'admin-demo', password, 'admin', None)])
        db.executemany("INSERT INTO products VALUES(?,?,?,?,?)", [
            (1, 'Maçã', 'KG', '101', 12.5), (2, 'Alface', 'UN', '102', None)])
        db.executemany("INSERT INTO product_availability VALUES(?,?)", [(p, d) for p in (1, 2) for d in range(7)])
        db.executemany("INSERT INTO dias_semana_config VALUES(?,?,?)", [(d, module.DAY_NAMES[d], True) for d in range(7)])
        db.executemany("INSERT INTO pedidos(data_pedido,loja,produto,tipo,quantidade) VALUES(?,?,?,?,?)", [
            ('2026-11-09','BCS','Maçã','Caixa',2), ('2026-11-09','BCS','Maçã','Caixa',3),
            ('2026-11-09','SJN','Maçã','KG',4), ('2026-11-08','BCS','Maçã','Caixa',99)])
        db.execute("INSERT INTO pedidos_finais(data_pedido,produto_nome,loja_nome,quantidade_pedida) VALUES(?,?,?,?)",
                   ('2026-11-09','Maçã','BCS',7))
        db.commit()
    return password


class AppTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.temp.name) / 'test.db')
        self.password = seed_database(self.path)
        self.env = patch.dict(os.environ, {'DATABASE_URL': ''})
        self.env.start()
        self.database = patch.object(module, 'DATABASE', self.path)
        self.database.start()
        module.app.config['TESTING'] = True
        self.client = module.app.test_client()

    def tearDown(self):
        self.database.stop()
        self.env.stop()
        self.temp.cleanup()

    def login(self, role='admin'):
        with self.client.session_transaction() as session:
            session.update(username='Demo', role=role, store_name='BCS')

    def test_report_totals_dates_and_missing_values(self):
        report, day, _ = module.obter_dados_relatorio('2026-11-09')
        apple = next(row for row in report if row['produto_nome'] == 'Maçã')
        self.assertEqual(apple['lojas'][0]['caixa'], 5)
        self.assertEqual(apple['lojas'][0]['pedido_salvo'], 7)
        self.assertEqual(apple['lojas'][1]['fracao'], '4 kg')
        self.assertEqual(apple['lojas'][2]['caixa'], 0)
        self.assertEqual(apple['custo'], 'R$ 12,50')

    def test_report_uses_one_connection(self):
        with patch.object(module, 'get_db', wraps=module.get_db) as connect:
            module.obter_dados_relatorio('2026-11-09')
            self.assertEqual(connect.call_count, 1)

    def test_disabled_day_is_respected(self):
        with closing(sqlite3.connect(self.path)) as db:
            db.execute('UPDATE dias_semana_config SET ativo = 0 WHERE dia_id = 0')
            db.commit()
        self.assertEqual(module.obter_dados_relatorio('2026-11-09')[0], 'INATIVO')

    def test_enabled_thursday(self):
        self.assertEqual(module.obter_dados_relatorio('2026-11-12')[1], 'QUINTA-FEIRA')

    def test_invalid_date_and_sql_input_are_normalized(self):
        self.login()
        self.assertEqual(self.client.get("/relatorio?data=' OR 1=1 --").status_code, 200)

    def test_login_and_authorization(self):
        self.assertEqual(self.client.get('/relatorio').status_code, 302)
        self.assertEqual(self.client.post('/login', data={'username':'demo','password':self.password}).status_code, 302)
        self.assertEqual(self.client.get('/relatorio').status_code, 403)
        self.assertEqual(self.client.get('/').status_code, 200)

    def test_save_selected_date(self):
        self.login()
        response = self.client.post('/salvar-pedido', data={
            'pedido_data': json.dumps([{'produto':'Maçã','loja':'BCS','pedido':'8'}]),
            'data_pedido_form': '2026-11-08'})
        self.assertEqual(response.json['status'], 'success')
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute("SELECT quantidade_pedida FROM pedidos_finais WHERE data_pedido='2026-11-08'").fetchone()[0], 8)
            self.assertEqual(db.execute("SELECT quantidade_pedida FROM pedidos_finais WHERE data_pedido='2026-11-09'").fetchone()[0], 7)
        self.assertIn(b'data_pedido_form', self.client.get('/relatorio?data=2026-11-09').data)

    def test_count_submission_and_validation(self):
        self.login('loja')
        self.assertEqual(self.client.post('/enviar', data={'caixas_Maçã':'6','fracionado_Alface':'2'}).status_code, 302)
        self.assertEqual(self.client.post('/enviar', data={'caixas_Maçã':'-1'}).status_code, 400)
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute("SELECT quantidade FROM pedidos WHERE data_pedido=? AND produto='Maçã' AND loja='BCS'", (date.today().isoformat(),)).fetchone()[0], 6)

    def test_pdf_aggregates_numeric_strings(self):
        orders = [{'produto':'Maçã','loja':'BCS','pedido':value} for value in ('2','3')]
        self.assertEqual(aggregate_orders(orders)[0][1]['BCS'], 5)
        self.login()
        response = self.client.post('/exportar-pedido-pdf', data={
            'pedido_data':json.dumps(orders), 'data_pedido_pdf':'2026-11-09'})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data.startswith(b'%PDF'))

    def test_all_admin_templates_and_static_cache(self):
        self.login()
        for path in ('/admin','/admin/products','/admin/product/add','/admin/dias-contagem','/admin/lojas'):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)
        with self.client.get('/static/app.css') as response:
            self.assertIn('max-age=3600', response.headers['Cache-Control'])

    def test_index_migration_is_repeatable_and_preserves_data(self):
        import migrate_render
        connect = sqlite3.connect
        with patch.object(migrate_render.sqlite3, 'connect', side_effect=lambda _: connect(self.path)):
            with redirect_stdout(io.StringIO()):
                self.assertTrue(migrate_render.migrate_database())
                self.assertTrue(migrate_render.migrate_database())
        with closing(connect(self.path)) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM pedidos').fetchone()[0], 4)
            plan = db.execute("EXPLAIN QUERY PLAN SELECT * FROM pedidos WHERE data_pedido=? AND loja=?", ('2026-11-09','BCS')).fetchall()
            self.assertIn('idx_pedidos_data_loja', str(plan))


if __name__ == '__main__':
    unittest.main()
