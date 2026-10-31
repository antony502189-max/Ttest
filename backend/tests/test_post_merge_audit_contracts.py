"""Behavioral regressions for post-merge test isolation and exact-SHA releases."""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).parents[2]


def workflow(name):
    # BaseLoader preserves the YAML 1.2 Actions key 'on', unlike YAML 1.1 bools.
    return yaml.load((ROOT / '.github/workflows' / name).read_text(), Loader=yaml.BaseLoader)


def test_main_ai_checks_are_unconditional_push_checks_with_real_browser_recovery():
    facts = workflow('ai-search-facts.yml')
    frontend = workflow('ai-search-frontend.yml')
    for config in (facts, frontend):
        assert config['on']['push'] == {'branches': ['main']}
    job = facts['jobs']['facts-postgres']
    assert job['env']['AI_HTTP_BROWSER_TEST'] == '1'
    recovery = next(s for s in job['steps'] if s.get('name') == 'Real HTTP frontend cookie and lost-ack recovery on PostGIS')
    assert recovery['env']['AI_UI_DIST_PATH'] == '${{ github.workspace }}/dist'
    assert 'test_ai_browser_recovery.py' in recovery['run']


def test_disabled_pages_still_builds_but_never_configures_or_deploys_a_site():
    jobs = workflow('pages-preview.yml')['jobs']
    build = jobs['build']['steps']
    assert any(s.get('name') == 'Build Pages preview' and 'if' not in s for s in build)
    for name in ('Configure Pages', 'Upload Pages artifact'):
        assert next(s for s in build if s.get('name') == name)['if'] == "vars.PAGES_PREVIEW_ENABLED == 'true'"
    assert jobs['deploy']['if'] == "vars.PAGES_PREVIEW_ENABLED == 'true'"
    assert next(s for s in build if s.get('name') == 'Record disabled optional preview')['if'] == "vars.PAGES_PREVIEW_ENABLED != 'true'"


@pytest.mark.skipif(sys.platform == 'win32' or not shutil.which('bash'), reason='POSIX Bash and executable stubs required')
def test_both_audit_entrypoints_use_the_same_executed_fixture_launcher(tmp_path):
    for name in ('final-audit-local.sh', 'ci-fullstack-audit.sh'):
        script = (ROOT / 'scripts' / name).read_text()
        assert 'bash scripts/start-fullstack-audit.sh' in script
        assert 'up -d migrate backend mail-worker' not in script
    calls = tmp_path / 'calls.jsonl'
    for name in ('docker', 'curl'):
        stub = tmp_path / name
        stub.write_text(f'#!{sys.executable}\nimport json,os,sys\n'
                        'with open(os.environ["AUDIT_CALLS"],"a") as out: '
                        'out.write(json.dumps([os.path.basename(sys.argv[0]),*sys.argv[1:]])+"\\n")\n')
        stub.chmod(0o755)
    result = subprocess.run(['bash', str(ROOT / 'scripts/start-fullstack-audit.sh')],
        env={**os.environ, 'AUDIT_CALLS': str(calls), 'PATH': str(tmp_path) + os.pathsep + os.environ['PATH']},
        capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    actual = [json.loads(line) for line in calls.read_text().splitlines()]
    docker = [call for call in actual if call[0] == 'docker']
    assert len(docker) == 2
    for call in docker:
        assert call[1:6] == ['compose', '-f', 'docker-compose.yml', '-f', 'docker-compose.fullstack-test.yml']
    assert 'backend' in docker[0] and docker[1][-4:] == ['tools', 'run', '--rm', 'seed']
    assert [call[-1] for call in actual if call[0] == 'curl'] == [
        'http://127.0.0.1:8000/health/ready', 'http://127.0.0.1:8000/metrics']


def load_verifier():
    spec = importlib.util.spec_from_file_location('main_checks', ROOT / 'scripts/verify-main-checks.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize('damage', ['none', 'missing', 'old_sha', 'pr_only', 'other_branch', 'spoofed_path',
                                    'latest_failed', 'latest_running', 'latest_cancelled', 'latest_skipped', 'old_failed'])
def test_exact_main_release_gate_rejects_missing_stale_or_unsuccessful_checks(damage):
    verifier = load_verifier()
    sha = 'a' * 40
    runs = [{'name': name, 'path': f'.github/workflows/{filename}', 'head_sha': sha, 'head_branch': 'main',
             'event': 'push', 'run_number': 1, 'run_attempt': 1, 'id': i, 'status': 'completed', 'conclusion': 'success'}
            for i, (filename, name) in enumerate(verifier.REQUIRED.items(), 1)]
    if damage == 'missing': runs.pop()
    elif damage in {'old_sha', 'pr_only', 'other_branch', 'spoofed_path'}:
        key, value = {'old_sha': ('head_sha', 'b' * 40), 'pr_only': ('event', 'pull_request'),
                      'other_branch': ('head_branch', 'feature/test'), 'spoofed_path': ('path', 'other.yml')}[damage]
        runs[-1][key] = value
    elif damage.startswith('latest_'):
        latest = {**runs[-1], 'run_attempt': 2}
        if damage == 'latest_running': latest.update(status='in_progress', conclusion=None)
        else: latest['conclusion'] = damage.removeprefix('latest_').replace('failed', 'failure')
        runs.append(latest)
    elif damage == 'old_failed': runs.insert(0, {**runs[-1], 'run_number': 0, 'conclusion': 'failure'})
    # Page boundaries must not hide the final required check or its rerun.
    pages = [{'workflow_runs': runs[:2]}, {'workflow_runs': runs[2:]}]
    if damage in {'none', 'old_failed'}: verifier.verify(pages, sha)
    else:
        with pytest.raises(ValueError): verifier.verify(pages, sha)


def test_release_workflow_executes_the_exact_main_gate_before_deploy():
    jobs = workflow('manual-production-deploy.yml')['jobs']
    steps = jobs['verify-release']['steps']
    assert steps[0]['name'] == 'Checkout exact release verifier'
    step = next(s for s in steps if s.get('name') == 'Verify post-merge checks on exact main SHA')
    assert '--paginate --slurp' in step['run']
    assert 'head_sha=$GITHUB_SHA&event=push' in step['run']
    assert 'python3 scripts/verify-main-checks.py "$GITHUB_SHA"' in step['run']
    assert jobs['deploy']['needs'] == 'verify-release'
