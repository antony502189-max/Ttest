"""Build only this owned candidate; never stop, recreate or activate a service."""
import hashlib,json,subprocess
from pathlib import Path
stage=Path('/srv/112233-ai-site-pilot-20261108/output/human-voice-20261118/immutable-b88d7280').resolve(strict=True)
assert stage.parent==Path('/srv/112233-ai-site-pilot-20261108/output/human-voice-20261118').resolve(strict=True)
value=json.loads((stage/'input-manifest.json').read_text());assert hashlib.sha256((stage/'source.tar').read_bytes()).hexdigest()==value['archive_sha256']
parent=value['parent_image'];actual=subprocess.check_output(['docker','image','inspect','ttest-ai-local-housing:producer-1c40beec','--format','{{.Id}}'],text=True).strip();assert actual==parent
subprocess.run(['docker','tag',parent,'ttest-ai-local-housing:voice-en-parent-7b3fb581'],check=True)
subprocess.run(['docker','build','--pull=false','--network=none','-t','ttest-ai-local-housing:voice-en-b88d7280','.'],cwd=stage,check=True)
image=subprocess.check_output(['docker','image','inspect','ttest-ai-local-housing:voice-en-b88d7280','--format','{{.Id}}'],text=True).strip()
print(json.dumps({'candidate_image':image,'verified_parent':parent,'activated':False}),flush=True)
