import hashlib,json,os,subprocess,tarfile
from pathlib import Path
root=Path('/tmp/flatio-verified');root.mkdir()
with tarfile.open('/evidence/verify-source.tar') as archive:archive.extractall(root,filter='data')
os.chdir(root/'backend');os.environ['PYTHONPATH']=str(root/'backend')
files={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((root/'backend').rglob('*')) if p.is_file()}
Path('/evidence/source-sha256.json').write_text(json.dumps(files,indent=2)+'\n')
for name,args in [('ruff.log',['ruff','check','app','tests','lab/flatio_catalog_audit.py']),('mypy.log',['mypy','app']),('unit.log',['python','-m','pytest','-q','-m','not integration','--junitxml=/evidence/unit.xml'])]:
 p=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
 Path('/evidence/'+name).write_text(p.stdout);print(name,p.returncode,p.stdout[-2000:],flush=True)
 if p.returncode:raise SystemExit(p.returncode)
