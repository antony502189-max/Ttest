"""FK-serialized proof invalidation; no per-candidate dependency reads. Explicit SQL for static compatibility inspection."""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = '0078_ai_live_validity'
down_revision = '0077_ai_live_inputs'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('ai_live_match_cohorts', sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('features', postgresql.JSONB(), nullable=False),
        sa.CheckConstraint("id ~ '^[0-9a-f]{64}$' AND id=encode(sha256(convert_to(features::text,'UTF8')),'hex') "
            "AND jsonb_typeof(features)='array' AND jsonb_array_length(features)<=128", name='ck_ai_live_cohort_identity'))
    op.add_column('ai_query_proofs', sa.Column('input_status', sa.String(16), nullable=False, server_default='legacy'))
    op.add_column('ai_query_proofs', sa.Column('input_contract', sa.String(64), nullable=True))
    op.add_column('ai_query_proofs', sa.Column('input_epoch', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('ai_query_proofs', sa.Column('input_schema', sa.String(64), nullable=True))
    op.add_column('ai_query_proofs', sa.Column('match_cohort_id', sa.String(64), nullable=True))
    op.create_foreign_key('fk_ai_proof_cohort', 'ai_query_proofs', 'ai_live_match_cohorts', ['match_cohort_id'], ['id'],
        onupdate='CASCADE', ondelete='SET NULL')
    op.create_index('ix_ai_proof_live_read', 'ai_query_proofs', ['canonical_listing_id'],
        postgresql_include=['resolver_version','vocabulary_hash','signature','input_status','input_contract','input_epoch','input_schema','match_cohort_id'])
    op.create_check_constraint('ck_ai_query_proof_input_status', 'ai_query_proofs', "input_status IN ('legacy','current','changed','missing')")
    op.create_unique_constraint('uq_ai_live_input_reference', 'ai_live_input_versions', ['kind', 'record_id', 'token'])
    op.create_table('ai_live_proof_dependencies', sa.Column('proof_listing_id', postgresql.UUID(as_uuid=True), primary_key=True), sa.Column('kind', sa.String(16), primary_key=True), sa.Column('record_id', postgresql.UUID(as_uuid=True), primary_key=True), sa.Column('token', postgresql.UUID(as_uuid=True), nullable=False), sa.ForeignKeyConstraint(['proof_listing_id'], ['ai_query_proofs.canonical_listing_id'], name='fk_ai_live_dep_proof', onupdate='CASCADE', ondelete='CASCADE'), sa.ForeignKeyConstraint(['kind', 'record_id', 'token'], ['ai_live_input_versions.kind', 'ai_live_input_versions.record_id', 'ai_live_input_versions.token'], name='fk_ai_live_dep_version', onupdate='CASCADE', ondelete='CASCADE'))
    op.create_index('ix_ai_live_dependency_input', 'ai_live_proof_dependencies', ['kind', 'record_id', 'token'])
    op.execute("""CREATE OR REPLACE FUNCTION ai_proof_population_changed() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE changed boolean;
    BEGIN
        IF TG_OP = 'INSERT' THEN changed := EXISTS (SELECT FROM new_proofs);
        ELSIF TG_OP = 'DELETE' THEN changed := EXISTS (SELECT FROM old_proofs);
        ELSIF TG_OP = 'UPDATE' THEN
            changed := EXISTS ((SELECT canonical_listing_id, signature, vocabulary_hash, resolver_version, feature_revision, input_signature, input_binding, input_vector, input_contract, input_epoch, input_schema, match_cohort_id FROM new_proofs EXCEPT SELECT canonical_listing_id, signature, vocabulary_hash, resolver_version, feature_revision, input_signature, input_binding, input_vector, input_contract, input_epoch, input_schema, match_cohort_id FROM old_proofs)
                UNION ALL (SELECT canonical_listing_id, signature, vocabulary_hash, resolver_version, feature_revision, input_signature, input_binding, input_vector, input_contract, input_epoch, input_schema, match_cohort_id FROM old_proofs EXCEPT SELECT canonical_listing_id, signature, vocabulary_hash, resolver_version, feature_revision, input_signature, input_binding, input_vector, input_contract, input_epoch, input_schema, match_cohort_id FROM new_proofs));
        ELSE changed := TRUE;
        END IF;
        IF changed THEN
            INSERT INTO ai_proof_population (id, revision) VALUES (1,1)
            ON CONFLICT (id) DO UPDATE SET revision=ai_proof_population.revision+1;
        END IF;
        RETURN NULL;
    END $$""")
    op.execute("""CREATE FUNCTION ai_live_dependencies_changed() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
        IF TG_OP = 'INSERT' THEN
            UPDATE ai_query_proofs SET input_status='missing'
            WHERE canonical_listing_id IN (SELECT proof_listing_id FROM new_dependencies);
        ELSIF TG_OP = 'DELETE' THEN
            UPDATE ai_query_proofs SET input_status='missing'
            WHERE canonical_listing_id IN (SELECT proof_listing_id FROM old_dependencies);
        ELSIF TG_OP = 'UPDATE' THEN
            UPDATE ai_query_proofs SET input_status=CASE WHEN input_status='missing' THEN 'missing' ELSE 'changed' END
            WHERE canonical_listing_id IN (SELECT proof_listing_id FROM old_dependencies
                UNION SELECT proof_listing_id FROM new_dependencies);
        ELSE
            UPDATE ai_query_proofs SET input_status='missing' WHERE input_signature IS NOT NULL;
        END IF;
        RETURN NULL;
    END $$""")
    op.execute("""CREATE TRIGGER ai_live_dependencies_insert AFTER INSERT ON ai_live_proof_dependencies REFERENCING NEW TABLE AS new_dependencies FOR EACH STATEMENT EXECUTE FUNCTION ai_live_dependencies_changed()""")
    op.execute("""ALTER TABLE ai_live_proof_dependencies ENABLE ALWAYS TRIGGER ai_live_dependencies_insert""")
    op.execute("""CREATE TRIGGER ai_live_dependencies_update AFTER UPDATE ON ai_live_proof_dependencies REFERENCING OLD TABLE AS old_dependencies NEW TABLE AS new_dependencies FOR EACH STATEMENT EXECUTE FUNCTION ai_live_dependencies_changed()""")
    op.execute("""ALTER TABLE ai_live_proof_dependencies ENABLE ALWAYS TRIGGER ai_live_dependencies_update""")
    op.execute("""CREATE TRIGGER ai_live_dependencies_delete AFTER DELETE ON ai_live_proof_dependencies REFERENCING OLD TABLE AS old_dependencies FOR EACH STATEMENT EXECUTE FUNCTION ai_live_dependencies_changed()""")
    op.execute("""ALTER TABLE ai_live_proof_dependencies ENABLE ALWAYS TRIGGER ai_live_dependencies_delete""")
    op.execute("""CREATE TRIGGER ai_live_dependencies_truncate AFTER TRUNCATE ON ai_live_proof_dependencies FOR EACH STATEMENT EXECUTE FUNCTION ai_live_dependencies_changed()""")
    op.execute("""ALTER TABLE ai_live_proof_dependencies ENABLE ALWAYS TRIGGER ai_live_dependencies_truncate""")
    op.execute("""CREATE FUNCTION ai_live_match_features(target uuid) RETURNS jsonb LANGUAGE sql STABLE PARALLEL SAFE AS $$
        SELECT (SELECT coalesce(jsonb_agg(item.value-'supporting_fact_ids' ORDER BY item.n),'[]'::jsonb)
                FROM jsonb_array_elements(p.features) WITH ORDINALITY AS item(value,n))
        FROM ai_listing_search_features p WHERE p.canonical_listing_id=target
    $$""")
    op.execute("""CREATE FUNCTION ai_live_cohort_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
        IF OLD.id IS DISTINCT FROM NEW.id OR OLD.features::text IS DISTINCT FROM NEW.features::text THEN
            RAISE EXCEPTION 'match cohorts are immutable' USING ERRCODE='23514', CONSTRAINT='ck_ai_live_cohort_identity';
        END IF;
        RETURN NEW;
    END $$""")
    op.execute("""CREATE TRIGGER ai_live_cohort_immutable BEFORE UPDATE ON ai_live_match_cohorts
        FOR EACH ROW EXECUTE FUNCTION ai_live_cohort_immutable()""")
    op.execute("""ALTER TABLE ai_live_match_cohorts ENABLE ALWAYS TRIGGER ai_live_cohort_immutable""")
    op.execute("""CREATE FUNCTION ai_live_proof_guard() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
        IF NEW.input_signature IS NOT NULL AND (
            NEW.input_contract IS NULL OR NEW.input_epoch IS DISTINCT FROM (NEW.input_vector->>'epoch')::uuid OR
            NEW.input_schema IS DISTINCT FROM (NEW.input_vector->>'schema') OR NEW.input_signature IS DISTINCT FROM
                encode(sha256(convert_to(NEW.input_vector::text,'UTF8')),'hex') OR
            NEW.input_binding IS DISTINCT FROM encode(sha256(convert_to(jsonb_build_object(
                'contract','live-proof-binding.v1','proof_contract',NEW.input_contract,
                'signature',NEW.signature,'inputs',NEW.input_signature,'resolver',NEW.resolver_version,
                'vocabulary',NEW.vocabulary_hash,'revision',NEW.feature_revision)::text,'UTF8')),'hex')
        ) THEN
            NEW.input_status := 'missing';
            RETURN NEW;
        END IF;
        IF NEW.input_status='current' THEN
            IF NOT EXISTS (SELECT FROM ai_live_match_cohorts c WHERE c.id=NEW.match_cohort_id
                           AND c.features::text=ai_live_match_features(NEW.canonical_listing_id)::text) THEN
                NEW.input_status := 'missing';
                RETURN NEW;
            END IF;
            IF NEW.input_signature IS NULL OR NEW.input_signature IS DISTINCT FROM
                    ai_live_input_signature(NEW.canonical_listing_id) OR
                    NEW.input_signature IS DISTINCT FROM encode(sha256(convert_to(NEW.input_vector::text,'UTF8')),'hex') THEN
                RAISE EXCEPTION 'live proof input snapshot changed' USING ERRCODE='23514', CONSTRAINT='ck_ai_live_current_proof';
            END IF;
            IF EXISTS (
                WITH expected AS (
                    SELECT 'listing'::varchar AS kind, NEW.canonical_listing_id AS record_id,
                        (NEW.input_vector->>'listing')::uuid AS token
                    UNION ALL SELECT 'external', (v->>0)::uuid, (v->>1)::uuid
                        FROM jsonb_array_elements(NEW.input_vector->'authority') v
                    UNION ALL SELECT 'batch', (v->>0)::uuid, (v->>1)::uuid
                        FROM jsonb_array_elements(NEW.input_vector->'batches') v
                ), actual AS (
                    SELECT kind,record_id,token FROM ai_live_proof_dependencies
                    WHERE proof_listing_id=NEW.canonical_listing_id
                )
                (SELECT * FROM expected EXCEPT SELECT * FROM actual)
                UNION ALL (SELECT * FROM actual EXCEPT SELECT * FROM expected)
            ) THEN
                RAISE EXCEPTION 'live proof dependencies missing' USING ERRCODE='23514', CONSTRAINT='ck_ai_live_current_proof';
            END IF;
        END IF;
        RETURN NEW;
    END $$""")
    op.execute("""CREATE TRIGGER ai_live_proof_guard BEFORE INSERT OR UPDATE ON ai_query_proofs FOR EACH ROW EXECUTE FUNCTION ai_live_proof_guard()""")
    op.execute("""ALTER TABLE ai_query_proofs ENABLE ALWAYS TRIGGER ai_live_proof_guard""")
    op.execute("""DO $$ DECLARE item record; BEGIN
        FOR item IN SELECT t.tgrelid::regclass AS relation, t.tgname FROM pg_trigger t
            JOIN pg_constraint c ON c.oid=t.tgconstraint
            WHERE (c.conrelid='ai_live_proof_dependencies'::regclass
            AND c.conname IN ('fk_ai_live_dep_proof','fk_ai_live_dep_version'))
            OR (c.conrelid='ai_query_proofs'::regclass AND c.conname='fk_ai_proof_cohort')
        LOOP EXECUTE format('ALTER TABLE %s ENABLE ALWAYS TRIGGER %I', item.relation, item.tgname); END LOOP;
    END $$""")
    op.execute("""CREATE OR REPLACE FUNCTION ai_live_input_schema_signature() RETURNS text
    LANGUAGE sql STABLE PARALLEL SAFE AS $$
    WITH triggers AS (
        SELECT count(*) AS n, bool_and(tgenabled='A') AS enabled,
            jsonb_agg(jsonb_build_array(tgrelid,tgname,tgtype,tgenabled,tgfoid,t.xmin::text,t.ctid::text,
                f.prosrc,f.proconfig,f.prosecdef,f.provolatile)
                      ORDER BY tgrelid,tgname) AS value
        FROM pg_trigger t JOIN pg_proc f ON f.oid=t.tgfoid WHERE NOT tgisinternal AND tgname LIKE 'ai_live_%'
        AND tgrelid IN ('listings'::regclass,'listing_room_details'::regclass,'ai_fact_catalogs'::regclass,'ai_listing_search_features'::regclass,'ai_fact_sources'::regclass,'external_listing_sources'::regclass,'ai_listing_fact_batches'::regclass,'ai_listing_facts'::regclass,'ai_live_input_versions'::regclass,
                       'ai_live_proof_dependencies'::regclass,'ai_query_proofs'::regclass,'ai_live_match_cohorts'::regclass)
    ), attributes AS (
        SELECT jsonb_agg(jsonb_build_array(attrelid,attnum,attname,atttypid,atttypmod,attcollation,attisdropped,xmin::text,ctid::text)
                         ORDER BY attrelid,attnum) AS value
        FROM pg_attribute WHERE attnum>0 AND attrelid IN ('listings'::regclass,'listing_room_details'::regclass,'ai_fact_catalogs'::regclass,'ai_listing_search_features'::regclass,'ai_fact_sources'::regclass,'external_listing_sources'::regclass,'ai_listing_fact_batches'::regclass,'ai_listing_facts'::regclass)
    ), constraints AS (
        SELECT c.oid,c.conrelid,c.confrelid,c.conkey,c.confkey,c.confupdtype,c.confdeltype,c.convalidated
        FROM pg_constraint c WHERE c.convalidated AND ((c.conrelid='ai_live_proof_dependencies'::regclass AND
        ((c.conname='fk_ai_live_dep_proof' AND c.confrelid='ai_query_proofs'::regclass AND c.conkey=ARRAY[1]::smallint[]
          AND c.confkey=ARRAY[1]::smallint[]) OR
         (c.conname='fk_ai_live_dep_version' AND c.confrelid='ai_live_input_versions'::regclass
          AND c.conkey=ARRAY[2,3,4]::smallint[] AND c.confkey=ARRAY[1,2,3]::smallint[]))
        AND c.confupdtype='c' AND c.confdeltype='c') OR
         (c.conrelid='ai_query_proofs'::regclass AND c.conname='fk_ai_proof_cohort'
          AND c.confrelid='ai_live_match_cohorts'::regclass AND c.conkey=ARRAY[13]::smallint[]
          AND c.confkey=ARRAY[1]::smallint[] AND c.confupdtype='c' AND c.confdeltype='n'))
    ), referential AS (
        SELECT count(*) AS n,bool_and(tgenabled='A') AS enabled,
            jsonb_agg(jsonb_build_array(tgrelid,tgname,tgtype,tgenabled,tgfoid,t.xmin::text,t.ctid::text,
                f.prosrc,f.proconfig,f.prosecdef,f.provolatile)
                      ORDER BY tgrelid,tgname) AS value
        FROM pg_trigger t JOIN pg_proc f ON f.oid=t.tgfoid WHERE tgconstraint IN (SELECT oid FROM constraints)
    ), helpers AS (
        SELECT jsonb_agg(jsonb_build_array(oid,prosrc,proconfig,prosecdef,provolatile,proparallel) ORDER BY oid) AS value
        FROM pg_proc WHERE oid IN ('ai_live_input_schema_signature()'::regprocedure,
            'ai_live_input_vector(uuid)'::regprocedure,'ai_live_input_signature(uuid)'::regprocedure,
            'ai_live_match_features(uuid)'::regprocedure)
    ), cache_check AS (
        SELECT count(*) AS n,jsonb_agg(jsonb_build_array(oid,conbin::text)) AS value
        FROM pg_constraint WHERE conrelid='ai_live_match_cohorts'::regclass
        AND conname='ck_ai_live_cohort_identity' AND contype='c' AND convalidated
    )
    SELECT CASE WHEN triggers.n=39 AND triggers.enabled AND referential.n=12 AND referential.enabled
        AND (SELECT count(*) FROM constraints)=3 AND cache_check.n=1 THEN
        encode(sha256(convert_to(jsonb_build_array(triggers.value,attributes.value,referential.value,helpers.value,cache_check.value)::text,'UTF8')),'hex') END
    FROM triggers CROSS JOIN attributes CROSS JOIN referential CROSS JOIN helpers CROSS JOIN cache_check
    $$""")
    op.execute("""UPDATE ai_query_proofs SET input_signature=NULL,input_binding=NULL,input_vector=NULL,input_status='legacy' WHERE input_signature IS NOT NULL""")


def downgrade():
    pass  # additive state is retained on binary rollback
