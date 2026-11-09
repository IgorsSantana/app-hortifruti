"""Aplica uma revisão de contagens uma única vez, mantendo os relatórios antigos."""
import json
import os
import sqlite3
from contextlib import closing
from datetime import date
from pathlib import Path

from report_data import DAY_NAMES

CONFIG = Path(__file__).with_name('counting_schedule.json')


def ensure_schema(db):
    with closing(db.cursor()) as cur:
        cur.execute("""CREATE TABLE IF NOT EXISTS contagem_schedule_updates (
            effective_from TEXT PRIMARY KEY)""")
        cur.execute("""CREATE TABLE IF NOT EXISTS contagem_product_history (
            effective_until TEXT NOT NULL, day_id INTEGER NOT NULL, product_id INTEGER NOT NULL,
            nome TEXT NOT NULL, unidade_fracionada TEXT NOT NULL, codigo_interno TEXT,
            cost NUMERIC, PRIMARY KEY(effective_until, day_id, product_id))""")
        cur.execute("""CREATE TABLE IF NOT EXISTS contagem_day_history (
            effective_until TEXT NOT NULL, day_id INTEGER NOT NULL, ativo BOOLEAN NOT NULL,
            PRIMARY KEY(effective_until, day_id))""")


def history_boundary(db, selected_date, placeholder):
    with closing(db.cursor()) as cur:
        cur.execute(
            f"SELECT MIN(effective_from) FROM contagem_schedule_updates WHERE effective_from > {placeholder}",
            (selected_date.isoformat(),))
        return cur.fetchone()[0]


def day_is_active(db, day, selected_date, placeholder):
    boundary = history_boundary(db, selected_date, placeholder)
    with closing(db.cursor()) as cur:
        if boundary:
            cur.execute(
                f"SELECT ativo FROM contagem_day_history WHERE effective_until={placeholder} AND day_id={placeholder}",
                (boundary, day))
        else:
            cur.execute(f"SELECT ativo FROM dias_semana_config WHERE dia_id={placeholder}", (day,))
        row = cur.fetchone()
        return bool(row[0]) if row is not None else day in (0, 1, 2, 4, 5)


def apply_schedule(db, is_postgres=False, config=None):
    config = config or json.loads(CONFIG.read_text(encoding='utf-8'))
    effective = date.fromisoformat(config['effective_from']).isoformat()
    items = config['items']
    codes = [item['codigo_interno'] for item in items]
    if len(items) != 99 or len(set(codes)) != 99:
        raise ValueError('A revisão deve conter exatamente 99 códigos distintos.')
    if {day: sum(day in item['days'] for item in items) for day in (1, 2, 5)} != {1: 35, 2: 36, 5: 99}:
        raise ValueError('As listas não correspondem às contagens confirmadas.')
    ph = '%s' if is_postgres else '?'
    try:
        with closing(db.cursor()) as cur:
            if is_postgres:
                cur.execute("SELECT pg_advisory_xact_lock(9426711)")
            else:
                cur.execute("BEGIN IMMEDIATE")
            ensure_schema(db)
            cur.execute(f"SELECT effective_from FROM contagem_schedule_updates WHERE effective_from={ph}", (effective,))
            if cur.fetchone():
                db.commit()
                return False
            # Snapshot includes names and units because existing orders refer to product names.
            cur.execute(
                "INSERT INTO contagem_product_history "
                "(effective_until,day_id,product_id,nome,unidade_fracionada,codigo_interno,cost) "
                f"SELECT {ph},pa.day_id,p.id,p.name,p.unidade_fracionada,p.codigo_interno,p.cost "
                "FROM products p JOIN product_availability pa ON pa.product_id=p.id", (effective,))
            for day in range(7):
                cur.execute(f"SELECT ativo FROM dias_semana_config WHERE dia_id={ph}", (day,))
                row = cur.fetchone()
                active = bool(row[0]) if row is not None else day in (0, 1, 2, 4, 5)
                cur.execute(
                    f"INSERT INTO contagem_day_history VALUES ({ph},{ph},{ph})", (effective, day, active))
            # Replace only the three lists; retain all products, costs, users and submitted orders.
            cur.execute("DELETE FROM product_availability WHERE day_id IN (1,2,5)")
            for item in items:
                code = item['codigo_interno']
                cur.execute(
                    f"SELECT id,unidade_fracionada FROM products WHERE codigo_interno={ph}", (code,))
                existing = cur.fetchone()
                # The imported-peach item had an older internal code in the existing catalog.
                if existing is None and code == '340137':
                    cur.execute(
                        f"SELECT id,unidade_fracionada FROM products WHERE codigo_interno={ph}", ('310159',))
                    existing = cur.fetchone()
                if existing:
                    product_id, unit = existing
                    cur.execute(
                        f"UPDATE products SET name={ph},codigo_interno={ph} WHERE id={ph}",
                        (item['nome'], code, product_id))
                else:
                    unit = item['unidade_fracionada']
                    sql = f"INSERT INTO products(name,unidade_fracionada,codigo_interno,cost) VALUES({ph},{ph},{ph},0)"
                    cur.execute(sql + (" RETURNING id" if is_postgres else ''),
                                (item['nome'], unit, code))
                    product_id = cur.fetchone()[0] if is_postgres else cur.lastrowid
                cur.executemany(
                    f"INSERT INTO product_availability(product_id,day_id) VALUES({ph},{ph})",
                    [(product_id, day) for day in item['days']])
            for day, name in DAY_NAMES.items():
                cur.execute(
                    f"INSERT INTO dias_semana_config(dia_id,nome_dia,ativo) VALUES({ph},{ph},{ph}) "
                    "ON CONFLICT(dia_id) DO UPDATE SET nome_dia=excluded.nome_dia,ativo=excluded.ativo",
                    (day, name, day in config['active_days']))
            cur.execute(f"INSERT INTO contagem_schedule_updates VALUES({ph})", (effective,))
            cur.execute("CREATE INDEX IF NOT EXISTS idx_pedidos_data_loja ON pedidos(data_pedido,loja)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_availability_day ON product_availability(day_id,product_id)")
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise


def run_schedule_update():
    db_url = os.environ.get('DATABASE_URL')
    if db_url:
        import psycopg2
        db = psycopg2.connect(db_url)
    else:
        db = sqlite3.connect('hortifruti.db')
    with closing(db):
        changed = apply_schedule(db, is_postgres=bool(db_url))
    print('Contagens: revisão 2026-11-09 aplicada.' if changed else 'Contagens: revisão já aplicada.')


if __name__ == '__main__':
    run_schedule_update()
