"""Official INE search identities, shared with the frontend catalogue."""
import json
import unicodedata
from pathlib import Path

MUNICIPALITIES = json.loads((Path(__file__).parent / 'data/spain-municipalities.json').read_text(encoding='utf-8'))['municipalities']


def municipality_aliases(name):
    aliases = []
    for part in name.split('/'):
        parts = [value.strip() for value in part.split(',')]
        aliases.append(part.strip())
        if len(parts) == 2:
            aliases.extend([f'{parts[1]} {parts[0]}', parts[0]])
    if name == 'San Cristóbal de La Laguna':
        aliases.extend(['La Laguna', 'San Cristóbal de Laguna'])
    if name == 'Santa Cruz de Tenerife':
        aliases.append('Santa Cruz')
    return aliases


def normalized_municipality(value):
    return ''.join(char for char in unicodedata.normalize('NFD', value.lower()) if not unicodedata.combining(char)).strip()
