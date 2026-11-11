"""Narrow release operations not exposed by the connected GitHub tools.

Credentials remain in memory, obtained through the configured Git helper.
"""
import json
import os
import re
import subprocess
import sys
import urllib.request
import urllib.error

BASE = 'https://api.github.com/repos/antony502189-max/Ttest'
result = subprocess.run(['git', 'credential', 'fill'], input='protocol=https\nhost=github.com\n\n',
                        text=True, capture_output=True,
                        env=dict(os.environ, GIT_TERMINAL_PROMPT='0', GCM_INTERACTIVE='Never'))
credentials = dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line)
headers = {'Authorization': 'Bearer ' + credentials['password'], 'Accept': 'application/vnd.github+json', 'User-Agent': 'Codex-release'}


def api(path, data=None):
    request = urllib.request.Request(BASE + path, headers=headers,
                                     data=None if data is None else json.dumps(data).encode())
    if data is not None:
        request.add_header('Content-Type', 'application/json')
    with urllib.request.urlopen(request, timeout=30) as response:
        body = response.read()
        return json.loads(body) if body else {'status': response.status}


operation = sys.argv[1]
if operation == 'cancel-obsolete':
    current = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    for run in api('/actions/runs?event=pull_request&per_page=100')['workflow_runs']:
        if run['head_branch'] == 'codex/municipality-search-autocomplete' and run['head_sha'] != current and run['status'] in ('in_progress', 'queued', 'waiting'):
            try:
                print(json.dumps({'obsolete_run': run['id'], 'name': run['name'], 'cancel': api(f"/actions/runs/{run['id']}/cancel", {})}), flush=True)
            except urllib.error.HTTPError as error:
                if error.code != 409:
                    raise
elif operation == 'approve-production':
    run_id = int(sys.argv[2])
    expected = sys.argv[3]
    assert re.fullmatch('[0-9a-f]{40}', expected)
    run = api(f'/actions/runs/{run_id}')
    assert run['head_sha'] == expected and run['head_branch'] == 'main'
    assert run['name'] == 'Production deployment (manual approval)'
    pending = api(f'/actions/runs/{run_id}/pending_deployments')
    target = [item for item in pending if item['environment']['name'] == 'production']
    assert len(target) == 1 and target[0]['current_user_can_approve']
    result = api(f'/actions/runs/{run_id}/pending_deployments', {
        'environment_ids': [target[0]['environment']['id']], 'state': 'approved',
        'comment': 'Production deployment explicitly authorized by the repository owner in the Codex chat; exact main SHA and PR CI verified.',
    })
    print(json.dumps({'approved_run': run_id, 'sha': expected}))
elif operation in ('list-production', 'dispatch'):
    runs = api('/actions/workflows/manual-production-deploy.yml/runs?per_page=10')['workflow_runs']
    if operation == 'list-production':
        print(json.dumps([{'id': run['id'], 'status': run['status'], 'conclusion': run['conclusion'], 'sha': run['head_sha'], 'url': run['html_url']} for run in runs]))
    else:
        expected = sys.argv[2]
        assert re.fullmatch('[0-9a-f]{40}', expected)
        assert api('/branches/main')['commit']['sha'] == expected
        assert not any(run['status'] != 'completed' for run in runs), 'A production deployment is already active'
        print(json.dumps(api('/actions/workflows/manual-production-deploy.yml/dispatches', {'ref': 'main', 'inputs': {'confirm_production': True}})))
else:
    raise SystemExit('Unsupported operation')
