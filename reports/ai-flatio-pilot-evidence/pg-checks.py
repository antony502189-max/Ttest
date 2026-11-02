import hashlib,json,os,subprocess,tarfile
from pathlib import Path
root=Path('/tmp/flatio-pg');root.mkdir()
with tarfile.open('/evidence/pg-source.tar') as archive:archive.extractall(root,filter='data')
os.chdir(root/'backend');os.environ['PYTHONPATH']=str(root/'backend')
os.environ['AI_FACTS_TEST_DATABASE_URL']='postgresql+psycopg://postgres:synthetic-only@127.0.0.1/ai_facts_test_flatio_pilot'
os.environ['AI_FLATIO_PILOT_DATA']='/private/records.json'
os.environ['AI_FLATIO_PILOT_RESULT']='/evidence/real-cohort-result.json'
files={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((root/'backend').rglob('*')) if p.is_file()}
Path('/evidence/pg-source-sha256.json').write_text(json.dumps(files,indent=2)+'\n')
for name,args in [('pg-ruff.log',['ruff','check','app','tests','lab/flatio_catalog_audit.py']),('real-cohort.log',['python','-m','pytest','-q','tests/ai_facts_pg/test_flatio_pilot.py','--tb=short','--junitxml=/evidence/real-cohort.xml']),('pg.log',['python','-m','pytest','-q','tests/ai_facts_pg','--junitxml=/evidence/pg.xml'])]:
 p=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
 Path('/evidence/'+name).write_text(p.stdout);print(name,p.returncode,p.stdout[-3000:],flush=True)
 if p.returncode:raise SystemExit(p.returncode)
