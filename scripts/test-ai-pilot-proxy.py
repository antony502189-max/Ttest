"""Owned sealed Docker contract runner. Never touches production/pilot state."""
import importlib.util
import json
import os
import subprocess
import time
from pathlib import Path
from uuid import uuid4

root = Path(__file__).resolve().parents[1]
out = root/"output"/("pilot-proxy-review-"+uuid4().hex)
out.mkdir(parents=True)
spec = importlib.util.spec_from_file_location("render",root/"deploy/ai-site-pilot/render_nginx.py")
renderer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(renderer)
(out/"nginx.conf").write_text(renderer.render((root/"deploy/ai-site-pilot/nginx.conf").read_text(),"172.30.41.9"))
password = subprocess.run(["openssl","passwd","-apr1","-stdin"],input="fixture-password\n",text=True,capture_output=True,check=True).stdout.strip()
(out/"htpasswd").write_text("tester:"+password+"\n")
(out/"index.html").write_text("<!doctype html><title>sealed proxy contract</title>")
(out/"traefik.yml").write_text("http:\n  routers:\n    test:\n      rule: Host(`app.112233.es`)\n      service: pilot\n      entryPoints: [web]\n  services:\n    pilot:\n      loadBalancer:\n        servers:\n          - url: http://frontend:8443\n")
for path in out.iterdir():path.chmod(0o644)
env = dict(os.environ,PILOT_TEST_DIR=str(out))
project = "ai-pilot-proxy-review-"+uuid4().hex[:12]
command = ["docker","compose","-p",project,"-f",str(root/"deploy/ai-site-pilot/proxy-test.yml")]
def run(*args,check=True):return subprocess.run(command+list(args),cwd=root,env=env,capture_output=True,text=True,check=check)
try:
    result = run("up","-d","--build",check=False)
    (out/"build.log").write_text(result.stdout+result.stderr)
    result.check_returncode()
    for attempt in range(40):
        health = run("exec","-T","frontend","wget","-qO-","http://127.0.0.1:8443/health",check=False)
        if health.returncode == 0:break
        time.sleep(.5)
    else:raise RuntimeError("sealed nginx startup failed")
    # Ensure backend + Traefik have completed startup, without any provider IO.
    for attempt in range(40):
        probe=run("exec","-T","clientb","python","-c","import httpx; r=httpx.get('http://traefik:8080/ai-pilot/api/v1/private-demo/status',headers={'Host':'app.112233.es'},auth=('tester','fixture-password')); assert r.status_code==200",check=False)
        if probe.returncode==0:break
        time.sleep(.5)
    else:raise RuntimeError("sealed proxy startup failed")
    proofs=[]
    for service,phase in (("clienta","a"),("clientb","b")):
        checked=run("exec","-T",service,"python","/app/proxy_client.py",phase)
        proofs.append(json.loads(checked.stdout.strip().splitlines()[-1]))
    (out/"proof.json").write_text(json.dumps(proofs,indent=2))
    print(json.dumps({"proofs":proofs,"output":str(out)}))
except BaseException as error:
    logs=run("logs","--no-color",check=False)
    (out/"failure.log").write_text(logs.stdout+logs.stderr+str(getattr(error,"stdout","") or "")+str(getattr(error,"stderr","") or ""))
    raise
finally:
    run("down","--volumes","--remove-orphans",check=False)  # Only this generated project, no shared resources.
