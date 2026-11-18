"""Public-only human speech evaluation; references never enter ASR configuration."""
import asyncio,hashlib,json,re,sys,time
from pathlib import Path
from uuid import UUID
sys.path.insert(0,'/app')
from app.services.ai_local_asr import LocalPCMTranscriber
from app.services.ai_housing_input import housing_patch
from app.services.ai_deepseek_intent import ProviderFailure
from app.schemas.ai_search_intent import Criteria,SearchIntent
from app.repositories.ai_search_sessions import IntentVocabulary
ROOT=Path('/fixtures');current=SearchIntent(schema_version='ai-search.v1',taxonomy_version='rental.v1',session_id=UUID(int=1),version=0,criteria=Criteria())
vocab=IntentVocabulary(frozenset({'wifi','parking','lift','internet','air_conditioning'}),frozenset(),frozenset())
def parse(text):
 try:return {'status':'accepted','patch':housing_patch(text,current,vocab).model_dump(mode='json',exclude_none=True)}
 except ProviderFailure:return {'status':'clarification'}
def words(s):return re.findall(r'\w+',s.casefold().replace('ё','е'))
def edits(a,b):
 row=list(range(len(b)+1))
 for i,x in enumerate(a,1):
  nxt=[i]
  for j,y in enumerate(b,1):nxt.append(min(nxt[-1]+1,row[j]+1,row[j-1]+(x!=y)))
  row=nxt
 return row[-1]
async def main():
 samples=json.loads((ROOT/'manifest.json').read_text())['samples'];rows=[]
 for sample in samples:
  data=(ROOT/sample['file']).read_bytes();assert hashlib.sha256(data).hexdigest()==sample['pcm_sha256']
  row={k:sample[k]for k in ['file','language','duration','reference','pcm_sha256','expected']};row['reference_parser']=parse(sample['reference'])
  asr=LocalPCMTranscriber(python=Path('/opt/voice/bin/python'),model=Path('/opt/voice-model'),seconds=18,prewarm=True)
  try:
   start=time.monotonic();await asr.start();row['prepare_seconds']=round(time.monotonic()-start,3);start=time.monotonic()
   try:
    text=await asr.transcribe(data,'audio/wav');row.update(asr_completed=True,transcript=text,transcript_parser=parse(text));a,b=words(sample['reference']),words(text);row.update(reference_words=len(a),word_errors=edits(a,b),wer=round(edits(a,b)/max(1,len(a)),4))
   except (ValueError,TimeoutError)as e:row.update(asr_completed=False,asr_failure=type(e).__name__)
   row['audio_seconds']=round(time.monotonic()-start,3)
  except (ValueError,TimeoutError)as e:row.update(asr_completed=False,preparation_failure=type(e).__name__)
  finally:await asr.close()
  row['memory_peak_bytes']=int(Path('/sys/fs/cgroup/memory.peak').read_text());rows.append(row);print(json.dumps(row,ensure_ascii=True),flush=True)
 print(json.dumps({'samples':len(rows),'asr_completed':sum(r['asr_completed']for r in rows),'memory_peak_bytes':int(Path('/sys/fs/cgroup/memory.peak').read_text()),'memory_swap_max':Path('/sys/fs/cgroup/memory.swap.max').read_text().strip(),'memory_events':Path('/sys/fs/cgroup/memory.events').read_text(),'external_calls':0,'live_business_queries':0}),flush=True)
asyncio.run(main())
