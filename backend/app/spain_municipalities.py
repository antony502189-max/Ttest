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


# Match the browser's NFD folding, including Catalan/Basque/Galician names.
CITY_ACCENTS = ''.join(chr(code) for code in range(0xC0, 0x250)
                       if chr(code).islower() and normalized_municipality(chr(code)) in 'abcdefghijklmnopqrstuvwxyz'
                       and normalized_municipality(chr(code)) != chr(code))
CITY_BASE_LETTERS = ''.join(normalized_municipality(char) for char in CITY_ACCENTS)


_alias_owners: dict[str, set[str]] = {}
for _code, _name in MUNICIPALITIES.items():
    for _alias in municipality_aliases(_name):
        _alias_owners.setdefault(normalized_municipality(_alias), set()).add(_code)


def unique_municipality_aliases(code):
    return [normalized_municipality(alias) for alias in municipality_aliases(MUNICIPALITIES[code])
            if len(_alias_owners[normalized_municipality(alias)]) == 1]
