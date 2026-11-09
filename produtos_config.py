"""Catálogo confirmado nas fotos, vigente a partir de 09/11/2026."""
import json
from pathlib import Path
from report_data import DAY_NAMES

SCHEDULE = json.loads(Path(__file__).with_name('counting_schedule.json').read_text(encoding='utf-8'))
PRODUTOS = {
    DAY_NAMES[day]: [
        {key: item[key] for key in ('nome', 'unidade_fracionada', 'codigo_interno')}
        for item in SCHEDULE['items'] if day in item['days']
    ]
    for day in SCHEDULE['active_days']
}
