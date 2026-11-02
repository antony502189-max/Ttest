import os,subprocess,tarfile
from pathlib import Path
root=Path('/tmp/fact-quality-pg');root.mkdir()
with tarfile.open('/evidence/source.tar') as t:t.extractall(root,filter='data')
os.chdir(root/'backend')
os.environ['PYTHONPATH']=str(root/'backend')
os.environ['AI_FACTS_TEST_DATABASE_URL']='postgresql+psycopg://postgres:synthetic-only@127.0.0.1/ai_facts_test_quality'
p=subprocess.run(['python','-m','pytest','-q','tests/ai_facts_pg','--junitxml=/evidence/pg.xml'],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
Path('/evidence/pg.log').write_text(p.stdout)
print(p.stdout[-3000:],flush=True)
raise SystemExit(p.returncode)
