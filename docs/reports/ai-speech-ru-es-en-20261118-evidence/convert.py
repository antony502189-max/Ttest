"""Public-only conversion: decode/resample the complete source, without trimming."""
import av,hashlib,json,io,wave
from pathlib import Path
root=Path('/fixtures');meta=json.loads((root/'public-manifest.json').read_text());out=Path('/converted');rows=[]
for case in meta['samples']:
 data=(root/case['file']).read_bytes();assert hashlib.sha256(data).hexdigest()==case['source_audio_sha256']
 resampler=av.AudioResampler(format='s16',layout='mono',rate=16000);pcm=[]
 with av.open(io.BytesIO(data))as c:
  for frame in c.decode(audio=0):
   for f in resampler.resample(frame):pcm.append(f.to_ndarray().tobytes())
  for f in resampler.resample(None):pcm.append(f.to_ndarray().tobytes())
 pcm=b''.join(pcm);buf=io.BytesIO()
 with wave.open(buf,'wb')as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(16000);w.writeframes(pcm)
 wav=buf.getvalue();name=Path(case['file']).stem+'.wav';(out/name).write_bytes(wav)
 rows.append({**case,'file':name,'duration':len(pcm)/32000,'pcm_sha256':hashlib.sha256(wav).hexdigest(),'in_bounds':3200<=len(pcm)<=480000})
(out/'manifest.json').write_text(json.dumps({**meta,'samples':rows},ensure_ascii=False,indent=2));print(json.dumps({'converted_full_samples':len(rows),'durations':[r['duration']for r in rows]}))
