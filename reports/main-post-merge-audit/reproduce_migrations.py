"""Run only against the audit's disposable local PostGIS container.

Requires /audit-src to be the native extraction of the audited Git archive,
pinned backend dependencies and a local ttest PostgreSQL test role. Creates a
new ai_migration_test_main_audit DB; never drops a database or modifies main.
"""
import json
import os
from pathlib import Path
import subprocess
from uuid import uuid4

import psycopg
from sqlalchemy import create_engine, inspect
from app.db.base import Base
import app.models  # noqa: F401

out = Path('/src/output/main-integration-audit')
database = 'ai_migration_test_main_audit'
admin_dsn = 'postgresql://ttest:ttest@127.0.0.1:5432/postgres'
dsn = admin_dsn.rsplit('/', 1)[0] + '/' + database
with psycopg.connect(admin_dsn, autocommit=True) as conn:
    conn.execute('CREATE DATABASE ' + database)
env = {**os.environ, 'DATABASE_URL': dsn.replace('postgresql://', 'postgresql+asyncpg://')}
stages = []
def alembic(*args, name):
    result = subprocess.run(['alembic', *args], cwd='/audit-src/backend', env=env,
                            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    (out/(name+'.log')).write_text(result.stdout)
    stages.append({'name':name, 'command':['alembic',*args], 'exit_code':result.returncode})
    return result.returncode
def revision(prefix):
    import ast
    for p in Path('/audit-src/backend/alembic/versions').glob(prefix+'*.py'):
        for n in ast.parse(p.read_text()).body:
            if isinstance(n, ast.Assign) and any(isinstance(t,ast.Name) and t.id=='revision' for t in n.targets):
                return ast.literal_eval(n.value)
    raise ValueError(prefix)

uid, saved, sid, key = [uuid4() for _ in range(4)]
assert alembic('upgrade', revision('0066'), name='history-0066') == 0
with psycopg.connect(dsn) as conn:
    conn.execute('INSERT INTO users(id,email,name) VALUES (%s,%s,%s)',(uid,'legacy-audit@example.invalid','Legacy audit'))
    conn.execute("INSERT INTO saved_searches(id,user_id,name,query,rental_mode) VALUES (%s,%s,'Legacy','Madrid','long')",(saved,uid))
assert alembic('upgrade', revision('0071'), name='history-0071') == 0
with psycopg.connect(dsn) as conn:
    conn.execute("INSERT INTO ai_search_sessions(id,subject_kind,subject_id,schema_version,taxonomy_version,criteria,expires_at) VALUES (%s,'auth',%s,'ai-search.v1','rental.v1','{}',now()+interval '1 hour')",(sid,uid))
assert alembic('upgrade', revision('0072'), name='history-0072') == 0
with psycopg.connect(dsn) as conn:
    conn.execute("INSERT INTO ai_session_commands(subject_kind,subject_id,idempotency_key,action,result_id) VALUES ('auth',%s,%s,'create',%s)",(uid,key,sid))
assert alembic('upgrade', revision('0073'), name='history-0073') == 0
with psycopg.connect(dsn) as conn:
    assert conn.execute('SELECT seed_mode FROM ai_session_commands WHERE idempotency_key=%s',(key,)).fetchone() == (None,)
assert alembic('upgrade', 'head', name='history-0074') == 0
assert alembic('upgrade', 'head', name='history-repeat-head') == 0
assert alembic('check', name='history-alembic-check') == 0
with psycopg.connect(dsn) as conn:
    assert conn.execute('SELECT email FROM users WHERE id=%s',(uid,)).fetchone() == ('legacy-audit@example.invalid',)
    assert conn.execute('SELECT name,query,matcher FROM saved_searches WHERE id=%s',(saved,)).fetchone() == ('Legacy','Madrid','manual.v1')
    assert conn.execute('SELECT criteria FROM ai_search_sessions WHERE id=%s',(sid,)).fetchone() == ({},)
    assert conn.execute('SELECT result_id,seed_mode FROM ai_session_commands WHERE idempotency_key=%s',(key,)).fetchone() == (sid,None)
    stamp=conn.execute('SELECT version_num FROM alembic_version').fetchone()
assert alembic('downgrade', revision('0073'), name='history-downgrade-refused') != 0
with psycopg.connect(dsn) as conn:
    assert conn.execute('SELECT version_num FROM alembic_version').fetchone() == stamp
    assert conn.execute('SELECT matcher FROM saved_searches WHERE id=%s',(saved,)).fetchone() == ('manual.v1',)

engine=create_engine(dsn.replace('postgresql://','postgresql+psycopg://'))
inspector=inspect(engine)
drift=[]
inventory={}
for name, model in Base.metadata.tables.items():
    actual={c['name']:c for c in inspector.get_columns(name)}
    missing=sorted(set(model.c.keys())-set(actual)); extra=sorted(set(actual)-set(model.c.keys()))
    if missing or extra: drift.append({'table':name,'missing':missing,'extra':extra})
    if name.startswith('ai_'):
        nullable=[c.name for c in model.c if c.nullable!=actual[c.name]['nullable']]
        if nullable: drift.append({'table':name,'nullable_mismatch':nullable})
        inventory[name]={'columns':sorted(actual), 'indexes':inspector.get_indexes(name),
                         'foreign_keys':inspector.get_foreign_keys(name), 'checks':inspector.get_check_constraints(name)}
(out/'schema-inventory.json').write_text(json.dumps(inventory,indent=2,default=str))
assert not drift, drift
# Reversible canary in the disposable DB: demonstrate exactly what alembic check covers.
with psycopg.connect(dsn) as conn:
    conn.execute('ALTER TABLE ai_session_commands RENAME COLUMN seed_mode TO audit_drift_seed_mode')
try:
    canary=alembic('check',name='history-drift-canary')
    # The repository has a separate, stricter integration contract. Confirm
    # that it closes the deliberately limited alembic/env.py column check.
    import importlib.util
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext
    spec=importlib.util.spec_from_file_location('audit_schema_parity','/audit-src/backend/tests/integration/test_schema_parity.py')
    parity=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(parity)
    with engine.connect() as connection:
        raw=compare_metadata(MigrationContext.configure(connection,opts={'include_object':parity._include_application_object,'compare_type':True}),Base.metadata)
    strict=[parity._describe_diff(d) for d in parity._flatten_diffs(raw) if d and str(d[0]) in parity.SCHEMA_CONTRACT_DIFF_KINDS and not parity._is_documented_legacy_nullable_diff(d)]
    assert any('seed_mode' in d for d in strict), strict
finally:
    with psycopg.connect(dsn) as conn:
        conn.execute('ALTER TABLE ai_session_commands RENAME COLUMN audit_drift_seed_mode TO seed_mode')
engine.dispose()
(out/'historical-migrations-results.json').write_text(json.dumps({'stages':stages,'legacy_data_preserved':True,'downgrade_preserves_stamp':True,'application_tables_compared':len(Base.metadata.tables),'column_drift':drift,'drift_canary_alembic_exit':canary,'strict_schema_contract_canary':strict},indent=2))
print('Historical chain, legacy records, command seed and rollback refusal verified; canary exit:',canary)
