"""PUBLIC FSI discovery only; not a production latency or private-audio runner."""
import av,io,json,sys,wave,hashlib,time
from pathlib import Path
import numpy as np
sys.path.insert(0,'/prototype/sherpa-python')
import sherpa_onnx,onnxruntime
onnxruntime.disable_telemetry_events()
from faster_whisper.vad import get_speech_timestamps,VadOptions
root=Path('/fixtures');out=Path('/segments');source=root/'unit07a.mp3';resampler=av.AudioResampler(format='s16',layout='mono',rate=16000);parts=[];count=0
with av.open(str(source))as c:
 for frame in c.decode(audio=0):
  for f in resampler.resample(frame):parts.append(f.to_ndarray().tobytes());count+=f.samples
  if count>=600*16000:break
pcm=b''.join(parts)[:600*32000];samples=np.frombuffer(pcm,dtype='<i2').astype(np.float32)/32768
regions=get_speech_timestamps(samples,VadOptions(min_silence_duration_ms=1000,speech_pad_ms=400))
selected=[r for r in regions if r['start']>0 and r['end']<len(samples)-8000][:100]
model=sherpa_onnx.OfflineRecognizer.from_transducer(encoder='/prototype/parakeet-model/encoder.direct.onnx',decoder='/prototype/parakeet-model/decoder.int8.onnx',joiner='/prototype/parakeet-model/joiner.int8.onnx',tokens='/prototype/parakeet-model/tokens.txt',num_threads=2,sample_rate=16000,feature_dim=80,decoding_method='greedy_search',model_type='nemo_transducer',provider='cpu',debug=False)
rows=[]
for i,r in enumerate(selected):
 a,b=r['start'],r['end'];duration=(b-a)/16000;row={'ordinal':i,'start':a/16000,'end':b/16000,'duration':duration,'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest()}
 if duration>15:row['rejected']='FULL_REGION_OVER_15_SECONDS'
 else:
  clip=samples[a:b];stream=model.create_stream();stream.accept_waveform(16000,clip);model.decode_stream(stream);row['discovery_transcript']=stream.result.text.strip()
  buf=io.BytesIO()
  with wave.open(buf,'wb')as w:w.setparams((1,2,16000,0,'NONE','not compressed'));w.writeframes(np.clip(np.rint(clip*32768),-32768,32767).astype('<i2').tobytes())
  data=buf.getvalue();name=f'fsi7-{i:03}.wav';(out/name).write_bytes(data);row.update(file=name,pcm_sha256=hashlib.sha256(data).hexdigest())
 rows.append(row);print(json.dumps(row,ensure_ascii=True),flush=True)
(out/'discovery.json').write_text(json.dumps({'selection':'All first100 complete VAD regions within the first600seconds; no ASR-quality filtering; oversized whole regions rejected rather than cropped.','vad':{'min_silence_duration_ms':1000,'speech_pad_ms':400},'model_reused_for_public_discovery_only':True,'samples':rows},indent=2));print(json.dumps({'regions':len(rows),'memory_peak':int(Path('/sys/fs/cgroup/memory.peak').read_text())}))
