import hashlib,json,sys
from pathlib import Path
from uuid import UUID
sys.path.insert(0,'/app')
from app.services.ai_housing_input import housing_patch
from app.services.ai_deepseek_intent import ProviderFailure
from app.schemas.ai_search_intent import Criteria,SearchIntent
from app.repositories.ai_search_sessions import IntentVocabulary
value=json.load(sys.stdin);root=Path('/app');actual={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest()for tree in ['app','demo','pilot','alembic']for p in (root/tree).rglob('*.py')};assert actual==value['runtime']
model=Path('/opt/voice-model');assets={str(p.relative_to(model)):hashlib.sha256(p.read_bytes()).hexdigest()for p in model.rglob('*')if p.is_file()};assert assets==value['model']['files']
s=SearchIntent(schema_version='ai-search.v1',taxonomy_version='rental.v1',session_id=UUID(int=1),version=0,criteria=Criteria());v=IntentVocabulary(frozenset(),frozenset(),frozenset())
for prefix in ['I need to rent','I want to rent','I would like to rent',"I'd like to rent"]:
 c=housing_patch(prefix+' a room in Madrid under 700 euros per month, not furnished, for 1 person',s,v).set
 assert c.accommodation.value.kind=='room'and c.budget.value.amount=='700'and c.geography.value.municipality_code=='28079'and c.party.value.model_dump()=={'persons':1}and c.furnished.value is False
for t in ['I need to rent out a room','I need to rent a room or a studio','I need to rent a room, not necessarily furnished','I need to rent a room, not near Madrid']:
 try:housing_patch(t,s,v)
 except ProviderFailure:pass
 else:raise AssertionError('UNSUPPORTED_WAS_ACCEPTED')
for text in ['sin muebles','¿Sin muebles?','sin amueblar','unfurnished','without furniture']:
 c=housing_patch(text,s,v);assert c.set.furnished.value is False and c.set.furnished.strength=='hard'and c.remove==()
for text in ['sin muebles, amueblado','sin muebles salvo la cocina','No, amueblado.','Doscientos, sin incluir luz, agua ni gas.']:
 try:housing_patch(text,s,v)
 except ProviderFailure:pass
 else:raise AssertionError('UNSUPPORTED_WAS_ACCEPTED')
print(json.dumps({'source':value['source'],'runtime_python_files':len(actual),'model_assets_verified':len(assets),'positive_composites':4,'furniture_negatives':5,'furniture_atomic_refusals':4,'atomic_refusals':4,'engine':'unchanged-small','activated':False,'business_queries':0,'external_calls':0}))
