import hashlib,json,os,subprocess,tarfile
from pathlib import Path
root=Path('/tmp/quality-next');root.mkdir();Path('/evidence/final').mkdir(exist_ok=True)
with tarfile.open('/snapshot/quality-final.tar') as archive:archive.extractall(root,filter='data')
os.chdir(root/'backend')
os.environ['PYTHONPATH']=str(root/'backend')
os.environ['AI_FACTS_TEST_DATABASE_URL']='postgresql+psycopg://postgres:synthetic-only@127.0.0.1/ai_facts_test_quality_next'
files={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((root/'backend').rglob('*')) if p.is_file()}
Path('/evidence/final/source-sha256.json').write_text(json.dumps(files,indent=2)+'\n')
checks=[('ruff.log',['ruff','check','app','tests']),('mypy.log',['mypy','app']),('unit.log',['python','-m','pytest','-q','-m','not integration','--junitxml=/evidence/final/unit.xml']),('pg.log',['python','-m','pytest','-q','tests/ai_facts_pg','--junitxml=/evidence/final/pg.xml'])]
for name,args in checks:
    p=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
    Path('/evidence/final/'+name).write_text(p.stdout)
    print(name,p.returncode,p.stdout[-2200:],flush=True)
    if p.returncode: raise SystemExit(p.returncode)

