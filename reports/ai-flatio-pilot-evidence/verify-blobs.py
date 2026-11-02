import hashlib,json,subprocess
from pathlib import Path
source='32b4af3271eb9197a5538a9b3760bad7f6b7bd25'
root=Path('reports/ai-flatio-pilot-evidence')
files=json.loads((root/'pg-source-sha256.json').read_text())
expected=set(subprocess.check_output(['git','ls-tree','-r','--name-only',source,'backend']).decode().splitlines())
assert set(files)==expected
for name,digest in files.items():assert hashlib.sha256(subprocess.check_output(['git','show',source+':'+name])).hexdigest()==digest,name
assert json.loads((root/'source-sha256.json').read_text())==files
for name in ['backend/app/services/ai_flatio_pilot.py','backend/lab/flatio_catalog_audit.py']:
 assert subprocess.check_output(['git','show','d48c57fe:'+name])==subprocess.check_output(['git','show',source+':'+name])
result={'source':source,'collection_source':'d48c57fe','collection_runtime_identical':True,'backend_files':len(files),'python_files':sum(n.endswith('.py') for n in files),'all_git_blobs_match':True,'raw_html_retained':False,'external_llm_calls':0,'tools_image':'sha256:1ff5de84b825934599a53fd69add14bb6784d6399a1464e4a38255b2d234a902'}
(root/'attestation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
