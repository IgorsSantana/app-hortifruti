import json
import sqlite3
import unittest
from contextlib import closing

import app as module
from schedule_update import CONFIG, apply_schedule
import test_app as fixtures


class ScheduleTests(unittest.TestCase):
    def setUp(self):
        fixtures.AppTests.setUp(self)
        with closing(sqlite3.connect(self.path)) as db:
            db.execute("CREATE UNIQUE INDEX unique_product_name ON products(name)")
            db.execute("UPDATE products SET name='MAÇÃ FUJI KG',codigo_interno='310140' WHERE id=1")
            db.execute("INSERT INTO products VALUES(3,'PESSEGO IMPORTADO KG','KG','310159',30)")
            db.execute("INSERT INTO pedidos(data_pedido,loja,produto,tipo,quantidade) VALUES('2026-11-07','BCS','MAÇÃ FUJI KG','Caixa',4)")
            db.commit()

    def tearDown(self):
        fixtures.AppTests.tearDown(self)

    def test_new_lists_and_active_days(self):
        with closing(sqlite3.connect(self.path)) as db:
            self.assertTrue(apply_schedule(db))
        for selected, expected in [('2026-11-10',35),('2026-11-11',36),('2026-11-14',99)]:
            report, _, _ = module.obter_dados_relatorio(selected)
            self.assertEqual(len(report), expected)
        for selected in ('2026-11-09','2026-11-12','2026-11-13','2026-11-15'):
            self.assertEqual(module.obter_dados_relatorio(selected)[0], 'INATIVO')
        self.assertEqual(len({p['codigo_interno'] for p in module.get_products_for_day(5)}), 99)

    def test_history_names_totals_and_day_status_preserved(self):
        old_report = module.obter_dados_relatorio('2026-11-07')
        with closing(sqlite3.connect(self.path)) as db:
            apply_schedule(db)
        self.assertEqual(module.obter_dados_relatorio('2026-11-07'), old_report)
        self.assertNotEqual(module.obter_dados_relatorio('2026-11-06')[0], 'INATIVO')
        self.assertEqual(module.obter_dados_relatorio('2026-11-13')[0], 'INATIVO')

    def test_costs_units_ids_orders_and_users_preserved(self):
        with closing(sqlite3.connect(self.path)) as db:
            before = db.execute('SELECT * FROM pedidos').fetchall()
            apply_schedule(db)
            self.assertEqual(db.execute("SELECT id,name,cost FROM products WHERE codigo_interno='310140'").fetchone(), (1,'MAÇÃ PINK',12.5))
            self.assertEqual(db.execute("SELECT id,cost FROM products WHERE codigo_interno='340137'").fetchone(), (3,30))
            self.assertEqual(db.execute('SELECT * FROM pedidos').fetchall(), before)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM users').fetchone()[0], 2)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM pedidos_finais').fetchone()[0], 1)

    def test_rerun_preserves_later_admin_edits(self):
        with closing(sqlite3.connect(self.path)) as db:
            apply_schedule(db)
            db.execute("DELETE FROM product_availability WHERE day_id=1 AND product_id=1")
            db.commit()
            self.assertFalse(apply_schedule(db))
            self.assertEqual(db.execute('SELECT COUNT(*) FROM product_availability WHERE day_id=1').fetchone()[0], 34)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM contagem_schedule_updates').fetchone()[0], 1)

    def test_failure_rolls_back_entire_update(self):
        config = json.loads(CONFIG.read_text(encoding='utf-8'))
        config['items'][1]['nome'] = config['items'][0]['nome']
        with closing(sqlite3.connect(self.path)) as db:
            with self.assertRaises(sqlite3.IntegrityError):
                apply_schedule(db, config=config)
            self.assertEqual(db.execute("SELECT name FROM products WHERE id=1").fetchone()[0], 'MAÇÃ FUJI KG')
            self.assertEqual(db.execute('SELECT COUNT(*) FROM product_availability').fetchone()[0],14)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM contagem_schedule_updates').fetchone()[0],0)


