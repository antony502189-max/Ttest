import asyncio,json,sys,time
from pathlib import Path
from uuid import UUID
sys.path.insert(0,'/app')
from app.services.ai_local_asr import LocalPCMTranscriber
from app.services.ai_housing_input import housing_patch
from app.repositories.ai_search_sessions import IntentVocabulary
from app.schemas.ai_search_intent import SearchIntent,Criteria

async def main():
    rows=[];asr=LocalPCMTranscriber(python=Path('/opt/voice/bin/python'),model=Path('/opt/voice-model'),seconds=18,prewarm=True)
    cases=[('english.wav',{'accommodation':{'kind':'room'},'budget':{'amount':'600','currency':'EUR','period':'monthly'}}),
      ('russian.wav',{'budget':{'amount':'600','currency':'EUR','period':'monthly'}}),
      ('russian-700-irina.wav',{'budget':{'amount':'700','currency':'EUR','period':'monthly'}}),
      ('russian-700-pavel.wav',{'budget':{'amount':'700','currency':'EUR','period':'monthly'}}),
      ('en-conditions.wav',{'accommodation':{'kind':'room'},'budget':{'amount':'700','currency':'EUR','period':'monthly'},'furnished':True,'bills_included':True}),
      ('ru-composite.wav',{'accommodation':{'kind':'room'},'budget':{'amount':'700','currency':'EUR','period':'monthly'},'furnished':True,'geography':{'province_code':'38','municipality_code':'38023'}})]
    vocab=IntentVocabulary(frozenset({'wifi','parking','lift','internet','air_conditioning'}),frozenset(),frozenset())
    try:
      for name,expected in cases:
        row={'sample':name};start=time.monotonic()
        try:
          await asr.start();start=time.monotonic();text=await asr.transcribe((Path('/fixtures')/name).read_bytes(),'audio/wav')
          current=SearchIntent(schema_version='ai-search.v1',taxonomy_version='rental.v1',session_id=UUID(int=1),version=0,criteria=Criteria())
          c=housing_patch(text,current,vocab).set.model_dump(mode='json',exclude_none=True)
          values={k:v['value']for k,v in c.items()};row.update(criteria=values,passed=values==expected,transcript=text)
        except Exception as e:row.update(passed=False,failure=type(e).__name__)
        row['seconds']=round(time.monotonic()-start,3);rows.append(row);print(json.dumps(row),flush=True)
      await asr.start();start=time.monotonic()
      try:await asr.transcribe(Path('/fixtures/silence.wav').read_bytes(),'audio/wav');passed=False
      except ValueError:passed=True
      except TimeoutError:passed=False
      rows.append({'sample':'silence.wav','passed':passed,'seconds':round(time.monotonic()-start,3)})
    finally:await asr.close()
    print(json.dumps({'prototype':True,'samples':rows,'passed':all(r['passed']for r in rows),'memory_peak':int(Path('/sys/fs/cgroup/memory.peak').read_text()),'external_calls':0}),flush=True)
asyncio.run(main())
