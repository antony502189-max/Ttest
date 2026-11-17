import hashlib,json,subprocess,tarfile
from pathlib import Path
root=Path('/srv/112233-ai-site-pilot-20261108/output/voice-rollout-6025-1c40-20261117')
meta=json.loads((root/'frontend.json').read_text())
archive=root/'frontend.tar'
assert hashlib.sha256(archive.read_bytes()).hexdigest()==meta['archive_sha256']
stage=root/'frontend';stage.mkdir(mode=0o700)
with tarfile.open(archive) as t:t.extractall(stage,filter='data')
def run(args,**kw):
    p=subprocess.run(args,capture_output=True,text=True,**kw)
    assert p.returncode==0,'FRONTEND_CANDIDATE_CHECK_FAILED: '+p.stderr[-300:]
    return p.stdout
parent='ttest-ai-saved-proxy:bf33d106'
info=json.loads(run(['docker','image','inspect',parent]))[0]
assert info['Id']=='sha256:9af18c4c07e558f0452bc1c93b52eb89b8853759a1ef7fb8133cff2c63ffa0d7'
user=info['Config']['User'];assert all(c.isalnum() or c in ':_-. ' for c in user)
source=meta['source'];image='ttest-ai-saved-proxy:party-reader-'+source[:8]
s='FROM '+parent+'\n'
if user:s+='USER root\n'
s+='RUN rm -rf /usr/share/nginx/html/ai-pilot\nCOPY dist /usr/share/nginx/html/ai-pilot\nLABEL es.ttest.ui-source='+source+'\n'
if user:s+='USER '+user+'\n'
(stage/'Dockerfile').write_text(s)
p=subprocess.run(['docker','build','--pull=false','--network=none','-t',image,str(stage)],capture_output=True,text=True,timeout=240)
(stage/'build.log').write_text(p.stdout+p.stderr);assert p.returncode==0,'FRONTEND_BUILD_FAILED'
new=json.loads(run(['docker','image','inspect',image]))[0]
common=['docker','run','--rm','--log-driver=none','--network=none','--read-only','--entrypoint','cat']
old_config=run(common+[parent,'/etc/nginx/conf.d/default.conf'])
new_config=run(common+[image,'/etc/nginx/conf.d/default.conf'])
assert old_config==new_config,'SEALED_PROXY_CONFIGURATION_CHANGED'
assert new['Config']['User']==info['Config']['User']
assert new['Config']['Labels']['es.ttest.proxy_source']==info['Config']['Labels']['es.ttest.proxy_source']
proof={'source':source,'image':new['Id'],'base_proxy_image':info['Id'],'proxy_config_unchanged':True,'proxy_source':new['Config']['Labels']['es.ttest.proxy_source'],'public_access_unchanged':True,'artifact_file_count':len(meta['files']),'activated':False,'new_business_requests':0}
# Tar exports only static, public frontend bytes; verify all files, no stale assets.
container=run(['docker','create','--log-driver=none',image]).strip()
try:
    p=subprocess.run(['docker','cp',container+':/usr/share/nginx/html/ai-pilot/.','-'],capture_output=True,check=True,timeout=30)
    import io
    with tarfile.open(fileobj=io.BytesIO(p.stdout)) as t:
        actual={m.name.removeprefix('./'):hashlib.sha256(t.extractfile(m).read()).hexdigest()for m in t.getmembers()if m.isfile()}
    assert actual==meta['files'],'FRONTEND_BYTES_MISMATCH'
finally:run(['docker','rm',container])
proof['all_artifact_hashes_verified']=True
(stage/'candidate-proof.json').write_text(json.dumps(proof,indent=2));print(json.dumps(proof))
