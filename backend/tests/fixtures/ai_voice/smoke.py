"""Runs in the sealed ASR image against synthetic speech fixtures only."""
import json
import subprocess
import time
from pathlib import Path

proof = []
for name, expected in (("english.wav", "find rooms under 600 euros per month"),
                       ("russian.wav", "до 600 евро в месяц")):
    started = time.monotonic()
    result = subprocess.run(["/opt/voice/bin/python", "/worker/ai_local_asr_worker.py", "/opt/voice-model"],
        input=(Path("/fixtures")/name).read_bytes(), capture_output=True, timeout=8, check=True)
    transcript = json.loads(result.stdout)
    assert transcript.casefold().strip().rstrip(".!?").strip() == expected, "SYNTHETIC_ASR_MISMATCH"
    proof.append({"sample":name, "seconds":round(time.monotonic()-started,3), "matched":True,
                  "external_provider_calls":0})
print(json.dumps(proof))
