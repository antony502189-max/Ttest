"""Deterministic stress variants of three full public clips, not new speakers."""
import hashlib,io,json,wave
from pathlib import Path
import numpy as np
root=Path('/fixtures');out=Path('/derived');meta=json.loads((root/'manifest.json').read_text());rows=[];seen=set()
for case in meta['samples']:
 if case['language']in seen:continue
 seen.add(case['language']);data=(root/case['file']).read_bytes();assert hashlib.sha256(data).hexdigest()==case['pcm_sha256']
 with wave.open(io.BytesIO(data))as w:samples=np.frombuffer(w.readframes(w.getnframes()),dtype='<i2').astype(np.float64)
 for variant in ['quiet_20db','noise_20db_with_pause']:
  if variant=='quiet_20db':changed=samples*.1
  else:
   rng=np.random.default_rng(20261118);noise=rng.normal(0,np.sqrt(np.mean(samples**2))/10,len(samples));changed=np.concatenate([np.zeros(16000),samples+noise,np.zeros(8000)])
  pcm=np.clip(np.rint(changed),-32768,32767).astype('<i2').tobytes();buf=io.BytesIO()
  with wave.open(buf,'wb')as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(16000);w.writeframes(pcm)
  wav=buf.getvalue();name=Path(case['file']).stem+'-'+variant+'.wav';(out/name).write_bytes(wav)
  rows.append({**case,'file':name,'duration':len(pcm)/32000,'pcm_sha256':hashlib.sha256(wav).hexdigest(),'parent_pcm_sha256':case['pcm_sha256'],'variant':variant,'in_bounds':len(pcm)<=480000})
(out/'manifest.json').write_text(json.dumps({**meta,'samples':rows},ensure_ascii=False,indent=2));print(json.dumps({'derived_samples':len(rows),'original_speakers':len(seen),'no_utterance_trimming':True}))
