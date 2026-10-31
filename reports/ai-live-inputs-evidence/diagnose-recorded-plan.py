"""Read-only post-run planning diagnostic; never an accepted capacity sample."""
import asyncio,json
from pathlib import Path
import asyncpg
ROOT=Path('/evidence')
OUT=ROOT/'post-run-plan-diagnostic.json'
async def main():
    assert not OUT.exists()
    raw=ROOT/'capacity'
    provenance=json.loads((raw/'experiment.json').read_text())
    records=json.loads((raw/'baseline-100000.json').read_text())
    r=next(r for r in records if r['candidates']==100000 and r['zoom']==8)
    sql=next(s for s in r['statements'] if s['category']=='map-query')
    c=await asyncpg.connect(host='127.0.0.1',user='r01',password='r01-synthetic-only',database='r01_synthetic',
        server_settings={'statement_timeout':'5000','lock_timeout':'1000','application_name':'codex-live-inputs-post-run-diagnostic'})
    result={'capacity_acceptance':False,'purpose':'read-only post-run planner diagnosis','provenance':provenance,
        'sql_sha256':sql['sql_sha256'],'settings':{'jit':'off','enable_nestloop':'off','statement_timeout':'5s'}}
    try:
        async with c.transaction(readonly=True,isolation='repeatable_read'):
            assert await c.fetchval('SELECT current_database()||\'|\'||current_user')=='r01_synthetic|r01'
            meta=json.loads(await c.fetchval('SELECT data FROM r01_meta'))
            assert meta['provenance']==provenance and meta['synthetic_only'] is True
            result['relations']=[dict(x) for x in await c.fetch("SELECT relname,relpages,relallvisible,pg_relation_size(oid) AS bytes FROM pg_class WHERE relname IN ('ai_query_proofs','ix_ai_proof_live_read','ai_query_proofs_pkey','listings')")]
            result['indexes']=[dict(x) for x in await c.fetch("SELECT i.relname,ix.indisvalid,ix.indisready,pg_get_indexdef(i.oid) AS definition FROM pg_class i JOIN pg_index ix ON ix.indexrelid=i.oid WHERE ix.indrelid='ai_query_proofs'::regclass")]
            await c.execute('SET LOCAL jit=off')
            await c.execute('SET LOCAL enable_nestloop=off')
            plan=await c.fetchval('EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) '+sql['sql'],*sql['parameters'])
            result.update(status='actual',plan=json.loads(plan))
    except Exception as e:
        result.update(status='failed',error=type(e).__name__,detail=str(e)[:400])
    finally:
        await c.close()
        OUT.write_text(json.dumps(result,indent=2)+'\n')
    print(result['status'],result.get('error'),[(x['relname'],x['relpages'],x['relallvisible']) for x in result.get('relations',[])])
    if result.get('plan'):print('Planning ms',result['plan'][0]['Planning Time'],'execution ms',result['plan'][0]['Execution Time'])
asyncio.run(main())
