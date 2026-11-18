import hashlib,json,sys
from pathlib import Path
from uuid import UUID
sys.path.insert(0, "/app")
from app.schemas.ai_search_intent import Criteria,SearchIntent,apply_patch
from app.schemas.ai_listing_facts import FactVocabulary
from app.repositories.ai_search_sessions import IntentVocabulary
from app.services.ai_hard_matching import compile_hard_match
from app.services.ai_housing_input import housing_patch
from app.services.ai_deepseek_intent import ProviderFailure
v=json.load(sys.stdin)
root=Path('/app')
actual={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for tree in ('app','demo','pilot','alembic') for p in (root/tree).rglob('*.py')}
assert actual==v['runtime'],'RUNTIME_MISMATCH'
model=Path('/opt/voice-model')
assets={str(p.relative_to(model)):hashlib.sha256(p.read_bytes()).hexdigest() for p in model.rglob('*') if p.is_file()}
assert assets==v['model']['files'],'MODEL_MISMATCH'
for value in ({'persons':1},{'persons':10},{'adults':2,'children':1,'relationship':'family'}):
    c=Criteria.model_validate({'party':{'strength':'hard','value':value}})
    assert c.party.value.model_dump()==value
saved=SearchIntent(schema_version='ai-search.v1',taxonomy_version='rental.v1',session_id=UUID(int=1),version=0,criteria=Criteria.model_validate({'party':{'strength':'hard','value':{'persons':1}}}))
fv=FactVocabulary(amenity_codes=frozenset(),catalog_other_codes=frozenset(),tenant_group_codes=frozenset(),municipality_zones=frozenset())
assert {r.key for r in compile_hard_match(saved,fv).criteria[0].rules}=={'capacity_total','available_spots'}
iv=IntentVocabulary(frozenset(),frozenset(),frozenset())
assert apply_patch(saved,housing_patch('furnished',saved,iv)).criteria.party==saved.criteria.party
empty=saved.model_copy(update={'criteria':Criteria()})
texts=['комната для одного человека до 650 евро в месяц','una habitación para una persona hasta seiscientos cincuenta euros al mes']
for text in texts:
    try: patch=housing_patch(text,empty,iv)
    except ProviderFailure:
        assert v['role']=='reader','PRODUCER_REJECTED'
    else:
        assert v['role']=='producer','READER_ENABLED_NEW_WRITER'
        assert patch.set.party.value.model_dump()=={'persons':1}
        assert patch.set.budget.value.amount=='650'
        assert patch.set.accommodation.value.kind=='room'
print(json.dumps({'runtime_python_files':len(actual),'model_assets_verified':True,'retained_readers':True,'producer_enabled':v['role']=='producer','new_business_requests':0}))
