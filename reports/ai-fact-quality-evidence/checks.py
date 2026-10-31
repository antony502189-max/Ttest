import hashlib,json,os,subprocess,tarfile
from pathlib import Path
root=Path('/tmp/fact-quality')
root.mkdir()
with tarfile.open('/evidence/source.tar') as t:
    t.extractall(root,filter='data')
os.chdir(root/'backend')
os.environ['PYTHONPATH']=str(root/'backend')
files={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.rglob('*')) if p.is_file()}
Path('/evidence/tested-source-sha256.json').write_text(json.dumps(files,indent=2)+'\n')
checks=[('coverage.json',['python','lab/fact_coverage.py']),('ruff.log',['ruff','check','lab/fact_coverage.py','tests/test_ai_fact_bridge.py']),('unit.log',['python','-m','pytest','-q','tests/test_ai_fact_bridge.py','tests/test_ai_listing_input.py','tests/test_ai_listing_facts.py','tests/test_ai_fact_resolver.py','tests/test_ai_hard_facts.py'])]
for name,args in checks:
    p=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
    Path('/evidence/'+name).write_text(p.stdout)
    print(name,p.returncode,p.stdout[-1200:] if name!='coverage.json' else 'matrix generated',flush=True)
    if p.returncode: raise SystemExit(p.returncode)
