import hashlib,json,os,subprocess,tarfile
from pathlib import Path
root=Path('/srv/112233-ai-site-pilot-20261108/output/voice-rollout-6025-1c40-20261117')
parent='ttest-ai-local-housing:b0af9f99'
parent_id='sha256:60a1c713382876c6c7aa62a422d5707a0b204ec2bb02f77e81ca4f52e162e6bb'
def run(args,**kwargs):
    p=subprocess.run(args,capture_output=True,text=True,**kwargs)
    if p.returncode:raise RuntimeError('CANDIDATE_CHECK_FAILED: '+args[0]+' '+p.stderr[-500:])
    return p.stdout
assert json.loads(run(['docker','image','inspect',parent]))[0]['Id']==parent_id
for role in ('reader','producer'):
    v=json.loads((root/(role+'.json')).read_text())
    archive=root/(role+'.tar')
    assert hashlib.sha256(archive.read_bytes()).hexdigest()==v['archive_sha256']
    stage=root/role
    stage.mkdir(mode=0o700,exist_ok=True)
    with tarfile.open(archive) as t:t.extractall(stage,filter='data')
    source=v['source']; image='ttest-ai-local-housing:'+role+'-'+source[:8]
    dockerfile='FROM '+parent+'\nUSER root\nLABEL es.ttest.source='+source+' es.ttest.release-role='+role+'\n'+''.join('COPY --chown=app:app backend/'+p+' /app/'+p+'\n' for p in ('app','demo','pilot','alembic'))+'USER app\n'
    (stage/'Dockerfile').write_text(dockerfile)
    p=subprocess.run(['docker','build','--pull=false','--network=none','-t',image,str(stage)],capture_output=True,text=True,timeout=240)
    (stage/'build.log').write_text(p.stdout+p.stderr)
    assert p.returncode==0,'BUILD_FAILED_SEE_OWNED_LOG'
    info=json.loads(run(['docker','image','inspect',image]))[0]
    assert info['Config']['Labels']['es.ttest.source']==source
    common=['docker','run','--rm','-i','--log-driver=none','--network=none','--read-only','--cpus=2','--memory=1536m','--memory-swap=1536m','--user=65534:65534','--tmpfs','/tmp:size=16m,noexec,nosuid','--cap-drop=ALL','--security-opt=no-new-privileges:true']
    probe=run(common+['--mount','type=bind,src='+str(root/'probe.v2.py')+',dst=/probe.py,readonly','--entrypoint','python',image,'/probe.py'],input=json.dumps(v),timeout=35)
    pins=run(common+['--entrypoint','/opt/voice/bin/python',image,'-c',"import json,sys,importlib.metadata;v=json.load(sys.stdin);assert all(importlib.metadata.version(k)==x for k,x in v.items());print(len(v))"],input=json.dumps(v['voice']),timeout=25)
    proof={'source':source,'tree':v['tree'],'role':role,'image':info['Id'],'parent_image':parent_id,'checks':json.loads(probe),'voice_pins_verified':int(pins),'network':'none','logging':'none','container_swap':False,'activated':False,'provider_calls':0}
    (stage/'candidate-proof.json').write_text(json.dumps(proof,indent=2))
    print(json.dumps(proof),flush=True)
