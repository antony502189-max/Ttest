import asyncio, hashlib, json, math, re, sys, time, wave
from pathlib import Path
sys.path.insert(0, '/app/app/services')
from ai_local_asr import LocalPCMTranscriber

def words(text):
    return re.findall(r'\w+', text.casefold().replace('ё', 'е'))

def distance(a, b):
    row = list(range(len(b)+1))
    for i, x in enumerate(a, 1):
        new = [i]
        for j, y in enumerate(b, 1):
            new.append(min(new[-1]+1, row[j]+1, row[j-1]+(x != y)))
        row = new
    return row[-1]

async def main():
    root = Path('/fixtures')
    cases = json.loads((root/'manifest.json').read_text())
    results = []
    asr = LocalPCMTranscriber(python=Path('/opt/voice/bin/python'), model=Path('/opt/voice-model'), seconds=18, prewarm=True)
    try:
        for case in cases:
            path = root/case['file']
            assert path.resolve().parent == root and path.suffix == '.wav'
            audio = path.read_bytes()
            with wave.open(str(path), 'rb') as wav:
                duration = wav.getnframes()/wav.getframerate()
            row = {k: case[k] for k in ('id', 'language', 'kind')}
            row.update(sha256=hashlib.sha256(audio).hexdigest(), duration=duration)
            await asr.start()
            start = time.monotonic()
            try:
                text = await asr.transcribe(audio, 'audio/wav')
                a, b = words(case['reference']), words(text)
                row.update(completed=True, reference_words=len(a), word_errors=distance(a,b), wer=round(distance(a,b)/max(1,len(a)),4))
                # Public/synthetic samples only; ignored diagnostic output.
                row['transcript'] = text
            except (ValueError, TimeoutError) as e:
                row.update(completed=False, failure=type(e).__name__)
            row['seconds'] = round(time.monotonic()-start,3)
            results.append(row)
            print(json.dumps(row,ensure_ascii=True),flush=True)
    finally:
        await asr.close()
    print(json.dumps({'samples':results,'cpu':2,'memory_mib':1536,'memory_peak':int(Path('/sys/fs/cgroup/memory.peak').read_text()),'external_calls':0}),flush=True)

asyncio.run(main())
