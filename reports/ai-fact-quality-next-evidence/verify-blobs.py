import hashlib,json,subprocess
from pathlib import Path
source='55bafffd557df9e6d745552f863154267885dd0a'
root=Path('reports/ai-fact-quality-next-evidence')
files=json.loads((root/'final/source-sha256.json').read_text())
expected=set(subprocess.check_output(['git','ls-tree','-r','--name-only',source,'backend']).decode().splitlines())
assert set(files)==expected,(set(files)-expected,expected-set(files))
for name,digest in files.items():
    assert hashlib.sha256(subprocess.check_output(['git','show',source+':'+name])).hexdigest()==digest,name
result={'source':source,'backend_files_matched':len(files),'python_files_matched':sum(p.endswith('.py') for p in files),'all_git_blobs_match':True,'archive_sha256':hashlib.sha256(Path('reports/ai-fact-quality-evidence/quality-final.tar').read_bytes()).hexdigest(),'tools_image':'sha256:1ff5de84b825934599a53fd69add14bb6784d6399a1464e4a38255b2d234a902','real_records':0,'external_provider_calls':0}
(root/'attestation.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))

