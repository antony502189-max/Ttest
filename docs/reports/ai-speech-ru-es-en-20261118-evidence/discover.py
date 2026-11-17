import urllib.request,json,csv,io,re,concurrent.futures,hashlib
from pathlib import Path
root=Path('output/housing-validation/human-voice-20261118'); rev='8262c16bf297c87a9cd88c51997c4758ed7a8ba2'
base=f'https://huggingface.co/datasets/fsicoli/common_voice_17_0/resolve/{rev}/'
def go(lang):
 p=root/f'{lang}-test.tsv'
 if not p.exists():p.write_bytes(urllib.request.urlopen(base+f'transcript/{lang}/test.tsv',timeout=40).read())
 rows=list(csv.DictReader(io.StringIO(p.read_text(encoding='utf-8')),delimiter='\t'))
 pattern={'en':r'\b(rent|renting|apartment|furnished|bedroom)\b','es':r'alquil|amueblad|habitaci[oó]n|dormitorio','ru':r'квартир|снять|сним[ау]|мебел|аренд'}[lang]
 matches=[{'path':r['path'],'sentence':r['sentence'],'speaker_hash':hashlib.sha256(r['client_id'].encode()).hexdigest()} for r in rows if re.search(pattern,r['sentence'],re.I)]
 (root/f'{lang}-candidates.json').write_text(json.dumps(matches,ensure_ascii=False,indent=2),encoding='utf-8')
 print(lang,len(rows),len(matches),json.dumps(matches,ensure_ascii=False))
with concurrent.futures.ThreadPoolExecutor() as ex:list(ex.map(go,['en','es','ru']))
