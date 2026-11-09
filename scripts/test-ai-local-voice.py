"""Build local ASR assets, then transcribe synthetic samples with networking off."""
import json
import subprocess
from pathlib import Path
from uuid import uuid4

root = Path(__file__).resolve().parents[1]
out = root/"output"/("voice-asr-review-"+uuid4().hex)
out.mkdir(parents=True)
tag = "ai-voice-asr-review:"+uuid4().hex
image_id = None
try:
    result = subprocess.run(["docker","build","--target","voice_assets","--build-arg",
        "BASE_IMAGE=mirror.gcr.io/library/python:3.13-slim@sha256:6771159cd4fa5d9bba1258caf0b82e6b73458c694d178ad97c5e925c2d0e1a91",
        "-f","deploy/ai-site-pilot/voice-backend.Dockerfile","-t",tag,"."],cwd=root,capture_output=True,text=True)
    (out/"build.log").write_text(result.stdout+result.stderr)
    result.check_returncode()
    image_id = subprocess.check_output(["docker","image","inspect",tag,"--format","{{.Id}}"],text=True).strip()
    result = subprocess.run(["docker","run","--rm","--network","none","--read-only","--memory","1536m",
        "--cpus","2","--user","65534:65534","--tmpfs","/tmp:size=16m,noexec,nosuid",
        "--security-opt","no-new-privileges:true","--cap-drop","ALL","-e","HF_HUB_OFFLINE=1",
        "--mount",f"type=bind,src={root/'backend/app/services'},dst=/worker,readonly",
        "--mount",f"type=bind,src={root/'backend/tests/fixtures/ai_voice'},dst=/fixtures,readonly",
        image_id,"/opt/voice/bin/python","/fixtures/smoke.py"],capture_output=True,text=True,timeout=45)
    (out/"run.log").write_text(result.stdout+result.stderr)
    result.check_returncode()
    proof = json.loads(result.stdout)
    (out/"proof.json").write_text(json.dumps({"image":image_id,"proof":proof},indent=2))
    print(json.dumps({"output":str(out),"proof":proof}))
finally:
    if image_id:
        subprocess.run(["docker","image","rm",tag],capture_output=True,check=False)
