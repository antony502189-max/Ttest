"""Offline CPU diagnostic: production statement building, no DB or SLO claims."""
import asyncio,cProfile,pstats,time,json,os,functools
from uuid import uuid4
from app.repositories.ai_fact_pipeline import FactPipeline
from app.repositories.ai_verified_cards import VerifiedCardSearch
from app.schemas.ai_fact_pipeline import FactQueuePolicy
from app.schemas.ai_listing_facts import FactVocabulary
from app.schemas.ai_search_intent import SearchIntent
from app.schemas.listings import ListingMapRequest
from sqlalchemy.dialects.postgresql.asyncpg import PGDialect_asyncpg

if os.environ.get('CACHE_SIGNATURE') == '1':
    import app.repositories.ai_query_proofs as qp
    qp.projection_signature=functools.lru_cache(maxsize=64)(qp.projection_signature)

class Empty:
    def all(self):return []
class Offline:
    def __init__(self):self.keys=set();self.compilations=0
    async def execute(self,stmt):
        key=stmt._generate_cache_key().key
        if key not in self.keys:
            stmt.compile(dialect=PGDialect_asyncpg())
            self.keys.add(key);self.compilations+=1
        return Empty()
async def main():
    pipe=FactPipeline(None,FactQueuePolicy(lease_seconds=600,max_attempts=2,retry_delay_seconds=1),
        FactVocabulary(amenity_codes=frozenset({'wifi'}),catalog_other_codes=frozenset(),
            tenant_group_codes=frozenset({'students'}),municipality_zones=frozenset()),resolver_version='r01-synthetic.v1')
    q=VerifiedCardSearch.__new__(VerifiedCardSearch);q.pipeline=pipe
    intent=SearchIntent.model_validate_json(json.dumps({'schema_version':'ai-search.v1','taxonomy_version':'rental.v1',
        'session_id':str(uuid4()),'version':1,'criteria':{'pets':{'strength':'hard','value':[{'species':'dog','size':'small','count':1}]}}}))
    for zoom in (8,13):
        s=Offline();view=ListingMapRequest(west=-16.90001,east=-16.79999,south=27.99999,north=28.01,zoom=zoom)
        await q._map_intent(s,intent,view)
        profile=cProfile.Profile();profile.enable();start=time.perf_counter()
        for _ in range(100):await q._map_intent(s,intent,view)
        elapsed=time.perf_counter()-start;profile.disable()
        print('OFFLINE, no DB, profiled CPU only',zoom,'mean_ms',elapsed*10,'compilations',s.compilations)
        pstats.Stats(profile).strip_dirs().sort_stats('cumtime').print_stats(20)
asyncio.run(main())


