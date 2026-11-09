"""Small, database-independent helpers shared by reports and PDF exports."""
from collections import defaultdict
from datetime import date

DAY_NAMES = {
    0: "SEGUNDA-FEIRA", 1: "TERÇA-FEIRA", 2: "QUARTA-FEIRA",
    3: "QUINTA-FEIRA", 4: "SEXTA-FEIRA", 5: "SÁBADO", 6: "DOMINGO",
}


def normalized_date(value):
    try:
        return date.fromisoformat(value)
    except (ValueError, TypeError):
        return date.today()


def build_report(products, counts, orders, stores):
    totals = defaultdict(int)
    for product, kind, store, quantity in counts:
        totals[product, kind, store] += quantity
    saved = {(product, store): quantity for product, store, quantity in orders}
    result = []
    for product in products:
        name = product['nome']
        row = {
            "produto_nome": name,
            "custo": f"R$ {product.get('cost') or 0:.2f}".replace('.', ','),
            "lojas": [],
        }
        for store in stores:
            fraction = sum(totals[name, kind, store] for kind in ('KG', 'UN'))
            row["lojas"].append({
                "nome": store, "caixa": totals[name, 'Caixa', store],
                "fracao": f"{fraction} {product['unidade_fracionada'].lower()}" if fraction else "0",
                "pedido_salvo": saved.get((name, store), ''),
            })
        result.append(row)
    return result


def aggregate_orders(orders):
    totals = defaultdict(lambda: defaultdict(int))
    for order in orders:
        totals[order['produto']][order['loja']] += int(order['pedido'])
    return sorted(totals.items())
