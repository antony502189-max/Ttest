"""Read GitHub Actions for a verified commit; never print Git credentials."""
import http.client
import json
import subprocess
import sys
import io
import zipfile
import urllib.request
from pathlib import Path
from urllib.parse import quote

task_git = 'C:/Users/HONOR/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe'
credential = subprocess.run([task_git,'-c','safe.directory=C:/Users/HONOR/Documents/Codex/Ttest','credential','fill'],
    input='protocol=https\nhost=github.com\n\n',text=True,capture_output=True,check=True)
values = dict(line.split('=',1) for line in credential.stdout.splitlines() if '=' in line)
token = values.get('password')
if not token:
    raise SystemExit('GitHub credential unavailable')

connection = http.client.HTTPSConnection('api.github.com',timeout=30)
path = '/repos/antony502189-max/Ttest/actions/runs?branch=feature%2Fpayments-promotions-ads&head_sha=' + quote(sys.argv[1]) + '&per_page=20'
connection.request('GET',path,headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json','User-Agent':'Ttest-payment-CI','X-GitHub-Api-Version':'2022-11-28'})
response = connection.getresponse()
if response.status != 200:
    raise SystemExit('GitHub Actions read returned HTTP '+str(response.status))
data = json.loads(response.read())
runs = [item for item in data['workflow_runs'] if item['name'] == 'Payment audit']
for item in runs:
    print(json.dumps({key:item.get(key) for key in ['id','name','head_sha','status','conclusion','html_url']}))
    if '--logs' in sys.argv:
        connection.request('GET',f"/repos/antony502189-max/Ttest/actions/runs/{item['id']}/logs",
            headers={'Authorization':'Bearer '+token,'User-Agent':'Ttest-payment-CI'})
        log_response = connection.getresponse()
        location = log_response.getheader('Location')
        log_response.read()
        if log_response.status == 302 and location:
            archive = zipfile.ZipFile(io.BytesIO(urllib.request.urlopen(location,timeout=30).read()))
            for name in archive.namelist():
                if name.endswith('.txt') and ('Server unit' in name or 'PostgreSQL payment' in name):
                    content = archive.read(name).decode('utf-8','replace')
                    output = Path('output/payment-audit/ci') / Path(name).name
                    output.parent.mkdir(parents=True,exist_ok=True)
                    output.write_text(content,encoding='utf-8')
                    print(content[-18000:])
    connection.request('GET',f"/repos/antony502189-max/Ttest/actions/runs/{item['id']}/jobs",
        headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json','User-Agent':'Ttest-payment-CI'})
    result = connection.getresponse()
    if result.status == 200:
        jobs = json.loads(result.read())
        for job in jobs['jobs']:
            print(json.dumps({'id':job['id'],'job':job['name'],'status':job['status'],'conclusion':job['conclusion'],
                'steps':[{'name':step['name'],'conclusion':step.get('conclusion'),'status':step['status']} for step in job.get('steps',[])]}))
    else:
        result.read()
connection.close()
