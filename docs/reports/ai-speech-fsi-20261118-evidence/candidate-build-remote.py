import hashlib,json,subprocess,tarfile
from pathlib import Path
stage=Path('/srv/112233-ai-site-pilot-20261108/output/delivery-20261118/immutable-2ff238c5').resolve(strict=True)
assert stage.parent==Path('/srv/112233-ai-site-pilot-20261108/output/delivery-20261118').resolve(strict=True)
value=json.loads((stage/'input-manifest.json').read_text())
assert hashlib.sha256((stage/'source.tar').read_bytes()).hexdigest()==value['archive_sha256']
parent=subprocess.check_output(['docker','image','inspect','ttest-ai-local-housing:voice-en-b88d7280','--format','{{.Id}}'],text=True).strip()
assert parent==value['parent_image']
with tarfile.open(stage/'source.tar')as archive:
 for member in archive.getmembers():
  assert (member.name=='backend'and member.isdir()or member.name.startswith('backend/'))and not member.issym()and not member.islnk()
  assert (stage/member.name).resolve().is_relative_to(stage)
 archive.extractall(stage,filter='data')
subprocess.run(['docker','tag',parent,'ttest-ai-local-housing:fsi-parent-4388af9a'],check=True)
subprocess.run(['docker','build','--pull=false','--network=none','-t','ttest-ai-local-housing:fsi-2ff238c5','.'],cwd=stage,check=True)
image=subprocess.check_output(['docker','image','inspect','ttest-ai-local-housing:fsi-2ff238c5','--format','{{.Id}}'],text=True).strip()
print(json.dumps({'source':value['source'],'candidate_image':image,'parent_image':parent,'activated':False}))
