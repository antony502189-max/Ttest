import json, os, pathlib, subprocess, sys, time, urllib.request
import psycopg
root=pathlib.Path('/audit-src'); out=pathlib.Path('/src/output/main-integration-audit')
dsn='postgresql://ttest:ttest@127.0.0.1:5432/ttest_fullstack'
with psycopg.connect('postgresql://ttest:ttest@127.0.0.1:5432/postgres',autocommit=True) as c:
    c.execute('CREATE DATABASE ttest_fullstack')
env={**os.environ,'APP_ENV':'development','DATABASE_URL':dsn.replace('postgresql://','postgresql+asyncpg://'),
     'PYTHONPATH':'/audit-src/backend:/audit-src/scripts:/audit-src',
     'REDIS_URL':'redis://127.0.0.1:6379/2','MEDIA_ROOT':'/audit-src/backend/var/fullstack-media',
     'FRONTEND_APP_URL':'http://127.0.0.1:4174','FRONTEND_ORIGINS':'http://127.0.0.1:4174',
     'FULLSTACK_TEST_HARNESS':'1','EXTERNAL_IMPORT_ENABLED':'false','EXTERNAL_REMOVAL_CHECK_ENABLED':'false',
     'VITE_E2E_BYPASS_ONBOARDING':'1','VITE_GOOGLE_MAPS_TEST_SDK':'1'}
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    env['PLAYWRIGHT_EXECUTABLE_PATH']=p.chromium.executable_path
results=[]
def run(name,command,cwd):
    print('START',name,flush=True)
    with (out/(name+'.log')).open('w') as log:
        r=subprocess.run(command,cwd=cwd,env=env,stdout=log,stderr=subprocess.STDOUT)
    results.append({'name':name,'command':command,'exit_code':r.returncode})
    (out/'fullstack-results.json').write_text(json.dumps(results,indent=2))
    print('END',name,r.returncode,flush=True)
    return r.returncode
assert run('fullstack-migrate',['alembic','upgrade','head'],root/'backend')==0
assert run('fullstack-seed',[sys.executable,'-m','app.commands.seed'],root/'backend')==0
# Reproduce no verified address candidate without issuing an external geocoding request.
(root/'audit_empty_geocoder.py').write_text('from app.services import address_geography\nasync def empty(*args): return []\naddress_geography.address_candidates=empty\nfrom app.main import app\n')
for name,module in [('fullstack-empty-provider','audit_empty_geocoder:app'),('fullstack-fixture-provider','fullstack_test_app:app')]:
    with (out/(name+'-server.log')).open('w') as serverlog:
        server=subprocess.Popen(['uvicorn',module,'--host','0.0.0.0','--port','8000','--no-access-log'],cwd=root,env=env,stdout=serverlog,stderr=subprocess.STDOUT)
        try:
            for i in range(100):
                try:
                    urllib.request.urlopen('http://127.0.0.1:8000/health/ready',timeout=1)
                    break
                except Exception:
                    if server.poll() is not None: raise RuntimeError('server failed to start')
                    time.sleep(.1)
            for endpoint in ['/api/v1/ai-search/capabilities','/api/v1/listings/catalog-version']:
                print(name,endpoint,urllib.request.urlopen('http://127.0.0.1:8000'+endpoint).read().decode(),flush=True)
            run(name,['node','node_modules/@playwright/test/cli.js','test','--config','playwright.fullstack.config.ts'],root)
        finally:
            server.terminate(); server.wait(timeout=20)
print('Fullstack evidence complete',flush=True)
