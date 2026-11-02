import os,shutil,subprocess,tarfile,hashlib,json
from pathlib import Path
shutil.copytree('/source','/tmp/intent-source')
with tarfile.open('/evidence/ci-fixed.tar') as archive:
    for member in archive.getmembers():
        p=Path('/tmp/intent-source')/member.name
        if p.is_file(): p.chmod(member.mode)
for name in ['backend/app/services/ai_closed_deepseek.py','backend/lab/intent_eval.py','backend/tests/test_ai_closed_deepseek.py']:
    (Path('/tmp/intent-source')/name).chmod(0o644)
os.chdir('/tmp/intent-source/backend')
os.environ['PYTHONPATH']='/tmp/intent-source/backend'
hashes={str(p.relative_to('/tmp/intent-source')):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(Path('/tmp/intent-source/backend').rglob('*')) if p.is_file()}
Path('/evidence/tested-backend-sha256.json').write_text(json.dumps(hashes,indent=2)+'\n')
# Mirror an editable app-only install without fetching build tools; lab must NOT
# become importable from the application's package finder in console pytest.
import site
Path(site.getsitepackages()[0], 'sitecustomize.py').write_text('''import sys, importlib.abc, importlib.util
class AppOnlyFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'app':
            return importlib.util.spec_from_file_location('app', '/tmp/intent-source/backend/app/__init__.py', submodule_search_locations=['/tmp/intent-source/backend/app'])
sys.meta_path.insert(0, AppOnlyFinder())
''')
os.environ.pop('PYTHONPATH',None)
checks=[('ruff-final.log',['ruff','check','app','tests','lab/intent_eval.py','lab/test_ai_text.py']),('mypy-final.log',['mypy','app']),('unit-final.log',['pytest','-q','-m','not integration','--junitxml=/evidence/unit-final.xml']),('lab-guards-final.log',['python','-m','pytest','-q','lab/test_ai_text.py','--junitxml=/evidence/lab-guards-final.xml'])]
for name,args in checks:
    result=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
    Path('/evidence/'+name).write_text(result.stdout)
    print(name,result.returncode,result.stdout[-2500:],flush=True)
    if result.returncode: raise SystemExit(result.returncode)
