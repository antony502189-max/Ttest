"""Build the runtime INE catalogue from the official 26codmun.xlsx download.

Usage: python scripts/build-municipality-catalog.py path/to/26codmun.xlsx
Source: https://www.ine.es/daco/daco42/codmun/26codmun.xlsx
No addresses or account data are sent anywhere. Output is deterministic.
"""
import hashlib
import json
import sys
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

source = Path(sys.argv[1])
ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
items = {}
with ZipFile(source) as archive:
    strings = ["".join(node.itertext()) for node in ET.fromstring(archive.read("xl/sharedStrings.xml")).findall("m:si", ns)]
    for sheet in sorted(name for name in archive.namelist() if name.startswith("xl/worksheets/sheet") and name.endswith(".xml")):
        for node in ET.fromstring(archive.read(sheet)).findall(".//m:row", ns):
            cells = {}
            for cell in node:
                value = cell.find("m:v", ns)
                if value is not None:
                    cells[''.join(c for c in cell.attrib['r'] if c.isalpha())] = strings[int(value.text)] if cell.attrib.get('t') == 's' else value.text
            province, municipality = cells.get('A', ''), cells.get('B', '')
            if province.isdigit() and len(province) == 2 and municipality.isdigit() and len(municipality) == 3:
                items[province + municipality] = cells['D']
assert len(items) == 8132, f"Unexpected INE catalogue: {len(items)}"
output = {"source": "https://www.ine.es/daco/daco42/codmun/26codmun.xlsx", "asOf": "2026-01-01",
          "sha256": hashlib.sha256(source.read_bytes()).hexdigest(), "municipalities": dict(sorted(items.items()))}
target = Path(__file__).resolve().parents[1] / 'backend/app/data/spain-municipalities.json'
target.parent.mkdir(exist_ok=True)
target.write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
frontend_target = Path(__file__).resolve().parents[1] / 'src/data/spain-municipalities.json'
frontend_target.write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(f"Built {len(items)} municipalities")
