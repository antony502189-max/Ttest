"""Offline prototype only. Existing ASR wire/budgets, fresh child per sample."""
import io,json,sys,wave
sys.path.insert(0,'/prototype/sherpa-python')
import numpy as np
import sherpa_onnx
import onnxruntime
onnxruntime.disable_telemetry_events()
from faster_whisper.vad import get_speech_timestamps,get_vad_model
from ai_local_asr import validate_pcm

def load():
    base='/prototype/parakeet-model/'
    model=sherpa_onnx.OfflineRecognizer.from_transducer(
        encoder=base+'encoder.direct.onnx',decoder=base+'decoder.int8.onnx',
        joiner=base+'joiner.int8.onnx',tokens=base+'tokens.txt',
        num_threads=2,sample_rate=16000,feature_dim=80,decoding_method='greedy_search',
        model_type='nemo_transducer',provider='cpu',debug=False)
    get_vad_model()
    return model
prepared=len(sys.argv)==3 and sys.argv[2]=='--prewarm'
model=load() if prepared else None
if prepared:sys.stdout.buffer.write(b'ASR_READY\n');sys.stdout.buffer.flush()
audio=sys.stdin.buffer.read(480045);validate_pcm(audio)
with wave.open(io.BytesIO(audio),'rb')as w:samples=np.frombuffer(w.readframes(240000),dtype='<i2').astype(np.float32)/32768
if model is None:model=load()
regions=get_speech_timestamps(samples)
if not regions:raise ValueError('VOICE_TRANSCRIPT_INVALID')
speech=np.concatenate([samples[r['start']:r['end']]for r in regions])
stream=model.create_stream();stream.accept_waveform(16000,speech);model.decode_stream(stream)
text=stream.result.text.strip()
if not 1<=len(text)<=2000:raise ValueError('VOICE_TRANSCRIPT_INVALID')
sys.stdout.write(json.dumps(text,ensure_ascii=True))
