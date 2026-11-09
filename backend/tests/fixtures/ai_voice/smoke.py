"""Runs in the sealed ASR image against synthetic speech fixtures only."""
import asyncio
import json
import sys
import time
from pathlib import Path


async def main():
    sys.path.insert(0, "/worker")
    from ai_local_asr import LocalPCMTranscriber
    asr = LocalPCMTranscriber(python=Path("/opt/voice/bin/python"),model=Path("/opt/voice-model"))
    proof = []
    for name, expected in (("english.wav", "find rooms under 600 euros per month"),
                           ("russian.wav", "до 600 евро в месяц"),
                           ("russian-700-irina.wav", "до 700 евро в месяц"),
                           ("russian-700-pavel.wav", "до 700 евро в месяц")):
        started = time.monotonic()
        transcript = await asr.transcribe((Path("/fixtures")/name).read_bytes(), "audio/wav")
        assert transcript.casefold().strip().rstrip(".!?").strip() == expected, "SYNTHETIC_ASR_MISMATCH"
        proof.append({"sample":name, "seconds":round(time.monotonic()-started,3), "matched":True,
                      "external_provider_calls":0})
    print(json.dumps(proof))


asyncio.run(main())
