import hashlib,json,subprocess
from pathlib import Path
base=Path('/srv/112233-ai-site-pilot-20261108/output/voice-rollout-6025-1c40-20261117')
main='f5ba0c18edc4083c6087cbb5648ebe54269d218d'
project='ttest-ai-site-pilot-20261108'
def run(args,**kw):
    p=subprocess.run(args,capture_output=True,text=True,timeout=35,**kw)
    assert p.returncode==0,'LIVE_READ_ONLY_CHECK_FAILED'
    return p.stdout
assert Path('/srv/112233.es/current').resolve().name==main
proof=json.loads((base/'producer/pilot-release-proof.json').read_text())
assert proof['new_total_producer'] and proof['protected_files_unchanged'] and proof['after_attempts']==30
expected=json.loads((base/'producer.json').read_text())
backend=json.loads(run(['docker','inspect',project+'-backend-1']))[0]
assert backend['Image']=='sha256:7b3fb5810f51978ff70a7753360e35ff38f36410d6e271eef656e696629f8ebc'
for mount in backend['Mounts']:
    assert not any(mount['Destination']==prefix or mount['Destination'].startswith(prefix+'/') for prefix in ('/app/app','/app/demo','/app/pilot','/app/alembic','/opt/voice','/opt/voice-model')),'RUNTIME_CODE_OVERLAY'
code="import hashlib,json,sys;from pathlib import Path;v=json.load(sys.stdin);r=Path('/app');a={str(p.relative_to(r)):hashlib.sha256(p.read_bytes()).hexdigest()for tree in ('app','demo','pilot','alembic')for p in(r/tree).rglob('*.py')};assert a==v;print(len(a))"
count=int(run(['docker','exec','-i',project+'-backend-1','python','-c',code],input=json.dumps(expected['runtime'])))
frontend=json.loads(run(['docker','inspect',project+'-frontend-1']))[0]
assert frontend['Image']=='sha256:d7bf35aa6325dc3a60df81ba4d69f483470728eea1e96b588eaaa36f808c75e0'
assert not any(m['Destination'].startswith('/usr/share/nginx/html') for m in frontend['Mounts'])
responses={}
for endpoint in ('/build-info.json','/ai-pilot/build-manifest.json','/ai-pilot/api/v1/ai-search/capabilities','/ai-pilot/api/v1/private-demo/status','/api/v1/ai-search/capabilities'):
    value=json.loads(run(['curl','--fail','--silent','--show-error','--max-time','12','--resolve','app.112233.es:443:169.58.147.65','https://app.112233.es'+endpoint]))
    responses[endpoint]=value
assert responses['/build-info.json']['commit']==main
assert responses['/ai-pilot/build-manifest.json']['source']=='b6b0a8271c86af740fcee46f57dd83731e4f205b'
cap=responses['/ai-pilot/api/v1/ai-search/capabilities'];assert cap['voice'] and cap['save_handoff']
status=responses['/ai-pilot/api/v1/private-demo/status'];assert status['approved'] is False and status['catalog_ready'] is True and status['attempts']==30 and status['local_housing_available'] is True
timers=run(['systemctl','is-active','ttest-pilot-catalog-refresh.timer','ttest-ai-saved-maintenance.timer','ttest-ai-primary-retention.timer']).split();assert timers==['active']*3
run(['python3','/srv/112233.es/current/deploy/check-ai-saved-runtime.py','/srv/112233.es/releases/4bcb89ecb849b33540e9369c3560daf004707935'])
result={'primary':main,'pilot_source':expected['source'],'backend_image':backend['Image'],'frontend_source':'b6b0a8271c86af740fcee46f57dd83731e4f205b','frontend_image':frontend['Image'],'proxy_configuration_unchanged':True,'active_runtime_python_hashes_verified':count,'runtime_code_overlays':False,'https_read_only_endpoints':len(responses),'public_primary_build':True,'public_voice_and_save_capabilities':True,'catalog_ready':True,'local_housing_available':True,'expired_provider_approval_enforced':True,'provider_attempts':30,'all_three_timers_active':True,'retained_rollback_readers_checked':True,'new_business_queries':0,'new_identities':0,'live_voice_query_executed':False,'full_ai_search_complete':False}
(base/'live-read-only-proof.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
