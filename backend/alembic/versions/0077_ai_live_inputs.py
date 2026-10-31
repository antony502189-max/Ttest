"""Transactional input tokens; retain full v2 verification on preparation. Explicit SQL for static compatibility inspection."""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = '0077_ai_live_inputs'
down_revision = '0076_ai_fact_population'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""LOCK TABLE listings, listing_room_details, ai_fact_catalogs, ai_listing_search_features, ai_fact_sources, external_listing_sources, ai_listing_fact_batches, ai_listing_facts IN SHARE ROW EXCLUSIVE MODE""")
    op.create_table('ai_live_input_epochs', sa.Column('id', sa.Integer(), primary_key=True), sa.Column('epoch', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')), sa.CheckConstraint('id = 1', name='ck_ai_live_epoch_singleton'))
    op.execute("""INSERT INTO ai_live_input_epochs (id) VALUES (1)""")
    op.create_table('ai_live_input_versions', sa.Column('kind', sa.String(16), primary_key=True), sa.Column('record_id', postgresql.UUID(as_uuid=True), primary_key=True), sa.Column('token', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')), sa.CheckConstraint("kind IN ('listing','external','batch')", name='ck_ai_live_input_kind'))
    op.add_column('ai_query_proofs', sa.Column('input_signature', sa.String(64), nullable=True))
    op.add_column('ai_query_proofs', sa.Column('input_binding', sa.String(64), nullable=True))
    op.add_column('ai_query_proofs', sa.Column('input_vector', postgresql.JSONB(), nullable=True))
    op.create_check_constraint('ck_ai_query_proof_inputs', 'ai_query_proofs', "(input_signature IS NULL AND input_binding IS NULL AND input_vector IS NULL) OR (input_signature IS NOT NULL AND input_binding IS NOT NULL AND input_vector IS NOT NULL AND input_signature ~ '^[0-9a-f]{64}$' AND input_binding ~ '^[0-9a-f]{64}$')")
    op.execute("""CREATE FUNCTION ai_live_listings_changed() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'INSERT' THEN
                INSERT INTO ai_live_input_versions (kind, record_id)
                SELECT 'listing', id FROM new_inputs WHERE id IS NOT NULL GROUP BY id ORDER BY id
                ON CONFLICT (kind, record_id) DO UPDATE SET token=gen_random_uuid();
            ELSIF TG_OP = 'DELETE' THEN
                INSERT INTO ai_live_input_versions (kind, record_id)
                SELECT 'listing', id FROM old_inputs WHERE id IS NOT NULL GROUP BY id ORDER BY id
                ON CONFLICT (kind, record_id) DO UPDATE SET token=gen_random_uuid();
            ELSE
                INSERT INTO ai_live_input_versions (kind, record_id)
                SELECT 'listing', changed.id FROM (
                    SELECT o.id AS id FROM old_inputs o FULL JOIN new_inputs n ON o.id=n.id
                    WHERE (to_jsonb(o) - 'views' - 'updated_at')::text IS DISTINCT FROM (to_jsonb(n) - 'views' - 'updated_at')::text
                    UNION
                    SELECT n.id AS id FROM old_inputs o FULL JOIN new_inputs n ON o.id=n.id
                    WHERE (to_jsonb(o) - 'views' - 'updated_at')::text IS DISTINCT FROM (to_jsonb(n) - 'views' - 'updated_at')::text
                ) changed WHERE changed.id IS NOT NULL ORDER BY changed.id
                ON CONFLICT (kind, record_id) DO UPDATE SET token=gen_random_uuid();
            END IF;

            RETURN NULL;
        END $$""")
    op.execute("""CREATE TRIGGER ai_live_listings_insert AFTER INSERT ON listings REFERENCING NEW TABLE AS new_inputs FOR EACH STATEMENT EXECUTE FUNCTION ai_live_listings_changed()""")
    op.execute("""ALTER TABLE listings ENABLE ALWAYS TRIGGER ai_live_listings_insert""")
    op.execute("""CREATE TRIGGER ai_live_listings_update AFTER UPDATE ON listings REFERENCING OLD TABLE AS old_inputs NEW TABLE AS new_inputs FOR EACH STATEMENT EXECUTE FUNCTION ai_live_listings_changed()""")
    op.execute("""ALTER TABLE listings ENABLE ALWAYS TRIGGER ai_live_listings_update""")
    op.execute("""CREATE TRIGGER ai_live_listings_delete AFTER DELETE ON listings REFERENCING OLD TABLE AS old_inputs FOR EACH STATEMENT EXECUTE FUNCTION ai_live_listings_changed()""")
    op.execute("""ALTER TABLE listings ENABLE ALWAYS TRIGGER ai_live_listings_delete""")
    op.execute("""CREATE FUNCTION ai_live_listing_room_details_changed() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'INSERT' THEN
                INSERT INTO ai_live_input_versions (kind, record_id)
                SELECT 'listing', listing_id FROM new_inputs WHERE listing_id IS NOT NULL GROUP BY listing_id ORDER BY listing_id
                ON CONFLICT (kind, record_id) DO UPDATE SET token=gen_random_uuid();
            ELSIF TG_OP = 'DELETE' THEN
                INSERT INTO ai_live_input_versions (kind, record_id)
                SELECT 'listing', listing_id FROM old_inputs WHERE listing_id IS NOT NULL GROUP BY listing_id ORDER BY listing_id
                ON CONFLICT (kind, record_id) DO UPDATE SET token=gen_random_uuid();
            ELSE
                INSERT INTO ai_live_input_versions (kind, record_id)
                SELECT 'listing', changed.id FROM (
                    SELECT o.listing_id AS id FROM old_inputs o FULL JOIN new_inputs n ON o.listing_id=n.listing_id
                    WHERE (to_jsonb(o))::text IS DISTINCT FROM (to_jsonb(n))::text
                    UNION
                    SELECT n.listing_id AS id FROM old_inputs o FULL JOIN new_inputs n ON o.listing_id=n.listing_id
                    WHERE (to_jsonb(o))::text IS DISTINCT FROM (to_jsonb(n))::text
                ) changed WHERE changed.id IS NOT NULL ORDER BY changed.id
                ON CONFLICT (kind, record_id) DO UPDATE SET token=gen_random_uuid();
            END IF;

            RETURN NULL;
        END $$""")
    op.execute("""CREATE TRIGGER ai_live_listing_room_details_insert AFTER INSERT ON listing_room_details REFERENCING NEW TABLE AS new_inputs FOR EACH STATEMENT EXECUTE FUNCTION ai_live_listing_room_details_changed()""")
    op.execute("""ALTER TABLE listing_room_details ENABLE ALWAYS TRIGGER ai_live_listing_room_details_insert""")
    op.execute("""CREATE TRIGGER ai_live_listing_room_details_update AFTER UPDATE ON listing_room_details REFERENCING OLD TABLE AS old_inputs NEW TABLE AS new_inputs FOR EACH STATEMENT EXECUTE FUNCTION ai_live_listing_room_details_changed()""")
    op.execute("""ALTER TABLE listing_room_details ENABLE ALWAYS TRIGGER ai_live_listing_room_details_update""")
    op.execute("""CREATE TRIGGER ai_live_listing_room_details_delete AFTER DELETE ON listing_room_details REFERENCING OLD TABLE AS old_inputs FOR EACH STATEMENT EXECUTE FUNCTION ai_live_listing_room_details_changed()""")
    op.execute("""ALTER TABLE listing_room_details ENABLE ALWAYS TRIGGER ai_live_listing_room_details_delete""")
    op.execute("""CREATE FUNCTION ai_live_ai_fact_catalogs_changed() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'INSERT' THEN
                INSERT INTO ai_live_input_versions (kind, record_id)
                SELECT 'listing', canonical_listing_id FROM new_inputs WHERE canonical_listing_id IS NOT NULL GROUP BY canonical_listing_id ORDER BY canonical_listing_id
                ON CONFLICT (kind, record_id) DO UPDATE SET token=gen_random_uuid();
            ELSIF TG_OP = 'DELETE' THEN
                INSERT INTO ai_live_input_versions (kind, record_id)
                SELECT 'listing', canonical_listing_id FROM old_inputs WHERE canonical_listing_id IS NOT NULL GROUP BY canonical_listing_id ORDER BY canonical_listing_id
                ON CONFLICT (kind, record_id) DO UPDATE SET token=gen_random_uuid();
            ELSE
                INSERT INTO ai_live_input_versions (kind, record_id)
                SELECT 'listing', changed.id FROM (
                    SELECT o.canonical_listing_id AS id FROM old_inputs o FULL JOIN new_inputs n ON o.canonical_listing_id=n.canonical_listing_id
                    WHERE (to_jsonb(o))::text IS DISTINCT FROM (to_jsonb(n))::text
                    UNION
                    SELECT n.canonical_listing_id AS id FROM old_inputs o FULL JOIN new_inputs n ON o.canonical_listing_id=n.canonical_listing_id
                    WHERE (to_jsonb(o))::text IS DISTINCT FROM (to_jsonb(n))::text
                ) changed WHERE changed.id IS NOT NULL ORDER BY changed.id
                ON CONFLICT (kind, record_id) DO UPDATE SET token=gen_random_uuid();
            END IF;

            RETURN NULL;
        END $$""")
    op.execute("""CREATE TRIGGER ai_live_ai_fact_catalogs_insert AFTER INSERT ON ai_fact_catalogs REFERENCING NEW TABLE AS new_inputs FOR EACH STATEMENT EXECUTE FUNCTION ai_live_ai_fact_catalogs_changed()""")
    op.execute("""ALTER TABLE ai_fact_catalogs ENABLE ALWAYS TRIGGER ai_live_ai_fact_catalogs_insert""")
    op.execute("""CREATE TRIGGER ai_live_ai_fact_catalogs_update AFTER UPDATE ON ai_fact_catalogs REFERENCING OLD TABLE AS old_inputs NEW TABLE AS new_inputs FOR EACH STATEMENT EXECUTE FUNCTION ai_live_ai_fact_catalogs_changed()""")
    op.execute("""ALTER TABLE ai_fact_catalogs ENABLE ALWAYS TRIGGER ai_live_ai_fact_catalogs_update""")
    op.execute("""CREATE TRIGGER ai_live_ai_fact_catalogs_delete AFTER DELETE ON ai_fact_catalogs REFERENCING OLD TABLE AS old_inputs FOR EACH STATEMENT EXECUTE FUNCTION ai_live_ai_fact_catalogs_changed()""")
    op.execute("""ALTER TABLE ai_fact_catalogs ENABLE ALWAYS TRIGGER ai_live_ai_fact_catalogs_delete""")
    op.execute("""CREATE FUNCTION ai_live_ai_listing_search_features_changed() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'INSERT' THEN
                INSERT INTO ai_live_input_versions (kind, record_id)
                SELECT 'listing', canonical_listing_id FROM new_inputs WHERE canonical_listing_id IS NOT NULL GROUP BY canonical_listing_id ORDER BY canonical_listing_id
                ON CONFLICT (kind, record_id) DO UPDATE SET token=gen_random_uuid();
            ELSIF TG_OP = 'DELETE' THEN
                INSERT INTO ai_live_input_versions (kind, record_id)
                SELECT 'listing', canonical_listing_id FROM old_inputs WHERE canonical_listing_id IS NOT NULL GROUP BY canonical_listing_id ORDER BY canonical_listing_id
                ON CONFLICT (kind, record_id) DO UPDATE SET token=gen_random_uuid();
            ELSE
                INSERT INTO ai_live_input_versions (kind, record_id)
                SELECT 'listing', changed.id FROM (
                    SELECT o.canonical_listing_id AS id FROM old_inputs o FULL JOIN new_inputs n ON o.canonical_listing_id=n.canonical_listing_id
                    WHERE (to_jsonb(o))::text IS DISTINCT FROM (to_jsonb(n))::text
                    UNION
                    SELECT n.canonical_listing_id AS id FROM old_inputs o FULL JOIN new_inputs n ON o.canonical_listing_id=n.canonical_listing_id
                    WHERE (to_jsonb(o))::text IS DISTINCT FROM (to_jsonb(n))::text
                ) changed WHERE changed.id IS NOT NULL ORDER BY changed.id
                ON CONFLICT (kind, record_id) DO UPDATE SET token=gen_random_uuid();
            END IF;

            RETURN NULL;
        END $$""")
    op.execute("""CREATE TRIGGER ai_live_ai_listing_search_features_insert AFTER INSERT ON ai_listing_search_features REFERENCING NEW TABLE AS new_inputs FOR EACH STATEMENT EXECUTE FUNCTION ai_live_ai_listing_search_features_changed()""")
    op.execute("""ALTER TABLE ai_listing_search_features ENABLE ALWAYS TRIGGER ai_live_ai_listing_search_features_insert""")
    op.execute("""CREATE TRIGGER ai_live_ai_listing_search_features_update AFTER UPDATE ON ai_listing_search_features REFERENCING OLD TABLE AS old_inputs NEW TABLE AS new_inputs FOR EACH STATEMENT EXECUTE FUNCTION ai_live_ai_listing_search_features_changed()""")
    op.execute("""ALTER TABLE ai_listing_search_features ENABLE ALWAYS TRIGGER ai_live_ai_listing_search_features_update""")
    op.execute("""CREATE TRIGGER ai_live_ai_listing_search_features_delete AFTER DELETE ON ai_listing_search_features REFERENCING OLD TABLE AS old_inputs FOR EACH STATEMENT EXECUTE FUNCTION ai_live_ai_listing_search_features_changed()""")
    op.execute("""ALTER TABLE ai_listing_search_features ENABLE ALWAYS TRIGGER ai_live_ai_listing_search_features_delete""")
    op.execute("""CREATE FUNCTION ai_live_ai_fact_sources_changed() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'INSERT' THEN
                INSERT INTO ai_live_input_versions (kind, record_id)
                SELECT 'listing', canonical_listing_id FROM new_inputs WHERE canonical_listing_id IS NOT NULL GROUP BY canonical_listing_id ORDER BY canonical_listing_id
                ON CONFLICT (kind, record_id) DO UPDATE SET token=gen_random_uuid();
            ELSIF TG_OP = 'DELETE' THEN
                INSERT INTO ai_live_input_versions (kind, record_id)
                SELECT 'listing', canonical_listing_id FROM old_inputs WHERE canonical_listing_id IS NOT NULL GROUP BY canonical_listing_id ORDER BY canonical_listing_id
                ON CONFLICT (kind, record_id) DO UPDATE SET token=gen_random_uuid();
            ELSE
                INSERT INTO ai_live_input_versions (kind, record_id)
                SELECT 'listing', changed.id FROM (
                    SELECT o.canonical_listing_id AS id FROM old_inputs o FULL JOIN new_inputs n ON o.source_record_id=n.source_record_id
                    WHERE (to_jsonb(o))::text IS DISTINCT FROM (to_jsonb(n))::text
                    UNION
                    SELECT n.canonical_listing_id AS id FROM old_inputs o FULL JOIN new_inputs n ON o.source_record_id=n.source_record_id
                    WHERE (to_jsonb(o))::text IS DISTINCT FROM (to_jsonb(n))::text
                ) changed WHERE changed.id IS NOT NULL ORDER BY changed.id
                ON CONFLICT (kind, record_id) DO UPDATE SET token=gen_random_uuid();
            END IF;

            RETURN NULL;
        END $$""")
    op.execute("""CREATE TRIGGER ai_live_ai_fact_sources_insert AFTER INSERT ON ai_fact_sources REFERENCING NEW TABLE AS new_inputs FOR EACH STATEMENT EXECUTE FUNCTION ai_live_ai_fact_sources_changed()""")
    op.execute("""ALTER TABLE ai_fact_sources ENABLE ALWAYS TRIGGER ai_live_ai_fact_sources_insert""")
    op.execute("""CREATE TRIGGER ai_live_ai_fact_sources_update AFTER UPDATE ON ai_fact_sources REFERENCING OLD TABLE AS old_inputs NEW TABLE AS new_inputs FOR EACH STATEMENT EXECUTE FUNCTION ai_live_ai_fact_sources_changed()""")
    op.execute("""ALTER TABLE ai_fact_sources ENABLE ALWAYS TRIGGER ai_live_ai_fact_sources_update""")
    op.execute("""CREATE TRIGGER ai_live_ai_fact_sources_delete AFTER DELETE ON ai_fact_sources REFERENCING OLD TABLE AS old_inputs FOR EACH STATEMENT EXECUTE FUNCTION ai_live_ai_fact_sources_changed()""")
    op.execute("""ALTER TABLE ai_fact_sources ENABLE ALWAYS TRIGGER ai_live_ai_fact_sources_delete""")
    op.execute("""CREATE FUNCTION ai_live_external_listing_sources_changed() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'INSERT' THEN
                INSERT INTO ai_live_input_versions (kind, record_id)
                SELECT 'external', id FROM new_inputs WHERE id IS NOT NULL GROUP BY id ORDER BY id
                ON CONFLICT (kind, record_id) DO UPDATE SET token=gen_random_uuid();
            ELSIF TG_OP = 'DELETE' THEN
                INSERT INTO ai_live_input_versions (kind, record_id)
                SELECT 'external', id FROM old_inputs WHERE id IS NOT NULL GROUP BY id ORDER BY id
                ON CONFLICT (kind, record_id) DO UPDATE SET token=gen_random_uuid();
            ELSE
                INSERT INTO ai_live_input_versions (kind, record_id)
                SELECT 'external', changed.id FROM (
                    SELECT o.id AS id FROM old_inputs o FULL JOIN new_inputs n ON o.id=n.id
                    WHERE (to_jsonb(o))::text IS DISTINCT FROM (to_jsonb(n))::text
                    UNION
                    SELECT n.id AS id FROM old_inputs o FULL JOIN new_inputs n ON o.id=n.id
                    WHERE (to_jsonb(o))::text IS DISTINCT FROM (to_jsonb(n))::text
                ) changed WHERE changed.id IS NOT NULL ORDER BY changed.id
                ON CONFLICT (kind, record_id) DO UPDATE SET token=gen_random_uuid();
            END IF;

            IF TG_OP = 'INSERT' THEN
                INSERT INTO ai_live_input_versions (kind, record_id)
                SELECT 'listing', canonical_listing_id FROM new_inputs GROUP BY canonical_listing_id
                ORDER BY canonical_listing_id ON CONFLICT (kind, record_id) DO UPDATE SET token=gen_random_uuid();
            ELSIF TG_OP = 'DELETE' THEN
                INSERT INTO ai_live_input_versions (kind, record_id)
                SELECT 'listing', canonical_listing_id FROM old_inputs GROUP BY canonical_listing_id
                ORDER BY canonical_listing_id ON CONFLICT (kind, record_id) DO UPDATE SET token=gen_random_uuid();
            ELSE
                INSERT INTO ai_live_input_versions (kind, record_id)
                SELECT 'listing', changed.id FROM (
                    SELECT o.canonical_listing_id AS id FROM old_inputs o FULL JOIN new_inputs n ON o.id=n.id
                    WHERE (to_jsonb(o))::text IS DISTINCT FROM (to_jsonb(n))::text
                    UNION
                    SELECT n.canonical_listing_id AS id FROM old_inputs o FULL JOIN new_inputs n ON o.id=n.id
                    WHERE (to_jsonb(o))::text IS DISTINCT FROM (to_jsonb(n))::text
                ) changed WHERE changed.id IS NOT NULL ORDER BY changed.id
                ON CONFLICT (kind, record_id) DO UPDATE SET token=gen_random_uuid();
            END IF;
            RETURN NULL;
        END $$""")
    op.execute("""CREATE TRIGGER ai_live_external_listing_sources_insert AFTER INSERT ON external_listing_sources REFERENCING NEW TABLE AS new_inputs FOR EACH STATEMENT EXECUTE FUNCTION ai_live_external_listing_sources_changed()""")
    op.execute("""ALTER TABLE external_listing_sources ENABLE ALWAYS TRIGGER ai_live_external_listing_sources_insert""")
    op.execute("""CREATE TRIGGER ai_live_external_listing_sources_update AFTER UPDATE ON external_listing_sources REFERENCING OLD TABLE AS old_inputs NEW TABLE AS new_inputs FOR EACH STATEMENT EXECUTE FUNCTION ai_live_external_listing_sources_changed()""")
    op.execute("""ALTER TABLE external_listing_sources ENABLE ALWAYS TRIGGER ai_live_external_listing_sources_update""")
    op.execute("""CREATE TRIGGER ai_live_external_listing_sources_delete AFTER DELETE ON external_listing_sources REFERENCING OLD TABLE AS old_inputs FOR EACH STATEMENT EXECUTE FUNCTION ai_live_external_listing_sources_changed()""")
    op.execute("""ALTER TABLE external_listing_sources ENABLE ALWAYS TRIGGER ai_live_external_listing_sources_delete""")
    op.execute("""CREATE FUNCTION ai_live_ai_listing_fact_batches_changed() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'INSERT' THEN
                INSERT INTO ai_live_input_versions (kind, record_id)
                SELECT 'batch', id FROM new_inputs WHERE id IS NOT NULL GROUP BY id ORDER BY id
                ON CONFLICT (kind, record_id) DO UPDATE SET token=gen_random_uuid();
            ELSIF TG_OP = 'DELETE' THEN
                INSERT INTO ai_live_input_versions (kind, record_id)
                SELECT 'batch', id FROM old_inputs WHERE id IS NOT NULL GROUP BY id ORDER BY id
                ON CONFLICT (kind, record_id) DO UPDATE SET token=gen_random_uuid();
            ELSE
                INSERT INTO ai_live_input_versions (kind, record_id)
                SELECT 'batch', changed.id FROM (
                    SELECT o.id AS id FROM old_inputs o FULL JOIN new_inputs n ON o.id=n.id
                    WHERE (to_jsonb(o))::text IS DISTINCT FROM (to_jsonb(n))::text
                    UNION
                    SELECT n.id AS id FROM old_inputs o FULL JOIN new_inputs n ON o.id=n.id
                    WHERE (to_jsonb(o))::text IS DISTINCT FROM (to_jsonb(n))::text
                ) changed WHERE changed.id IS NOT NULL ORDER BY changed.id
                ON CONFLICT (kind, record_id) DO UPDATE SET token=gen_random_uuid();
            END IF;

            RETURN NULL;
        END $$""")
    op.execute("""CREATE TRIGGER ai_live_ai_listing_fact_batches_insert AFTER INSERT ON ai_listing_fact_batches REFERENCING NEW TABLE AS new_inputs FOR EACH STATEMENT EXECUTE FUNCTION ai_live_ai_listing_fact_batches_changed()""")
    op.execute("""ALTER TABLE ai_listing_fact_batches ENABLE ALWAYS TRIGGER ai_live_ai_listing_fact_batches_insert""")
    op.execute("""CREATE TRIGGER ai_live_ai_listing_fact_batches_update AFTER UPDATE ON ai_listing_fact_batches REFERENCING OLD TABLE AS old_inputs NEW TABLE AS new_inputs FOR EACH STATEMENT EXECUTE FUNCTION ai_live_ai_listing_fact_batches_changed()""")
    op.execute("""ALTER TABLE ai_listing_fact_batches ENABLE ALWAYS TRIGGER ai_live_ai_listing_fact_batches_update""")
    op.execute("""CREATE TRIGGER ai_live_ai_listing_fact_batches_delete AFTER DELETE ON ai_listing_fact_batches REFERENCING OLD TABLE AS old_inputs FOR EACH STATEMENT EXECUTE FUNCTION ai_live_ai_listing_fact_batches_changed()""")
    op.execute("""ALTER TABLE ai_listing_fact_batches ENABLE ALWAYS TRIGGER ai_live_ai_listing_fact_batches_delete""")
    op.execute("""CREATE FUNCTION ai_live_ai_listing_facts_changed() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'INSERT' THEN
                INSERT INTO ai_live_input_versions (kind, record_id)
                SELECT 'batch', batch_id FROM new_inputs WHERE batch_id IS NOT NULL GROUP BY batch_id ORDER BY batch_id
                ON CONFLICT (kind, record_id) DO UPDATE SET token=gen_random_uuid();
            ELSIF TG_OP = 'DELETE' THEN
                INSERT INTO ai_live_input_versions (kind, record_id)
                SELECT 'batch', batch_id FROM old_inputs WHERE batch_id IS NOT NULL GROUP BY batch_id ORDER BY batch_id
                ON CONFLICT (kind, record_id) DO UPDATE SET token=gen_random_uuid();
            ELSE
                INSERT INTO ai_live_input_versions (kind, record_id)
                SELECT 'batch', changed.id FROM (
                    SELECT o.batch_id AS id FROM old_inputs o FULL JOIN new_inputs n ON o.id=n.id
                    WHERE (to_jsonb(o))::text IS DISTINCT FROM (to_jsonb(n))::text
                    UNION
                    SELECT n.batch_id AS id FROM old_inputs o FULL JOIN new_inputs n ON o.id=n.id
                    WHERE (to_jsonb(o))::text IS DISTINCT FROM (to_jsonb(n))::text
                ) changed WHERE changed.id IS NOT NULL ORDER BY changed.id
                ON CONFLICT (kind, record_id) DO UPDATE SET token=gen_random_uuid();
            END IF;

            RETURN NULL;
        END $$""")
    op.execute("""CREATE TRIGGER ai_live_ai_listing_facts_insert AFTER INSERT ON ai_listing_facts REFERENCING NEW TABLE AS new_inputs FOR EACH STATEMENT EXECUTE FUNCTION ai_live_ai_listing_facts_changed()""")
    op.execute("""ALTER TABLE ai_listing_facts ENABLE ALWAYS TRIGGER ai_live_ai_listing_facts_insert""")
    op.execute("""CREATE TRIGGER ai_live_ai_listing_facts_update AFTER UPDATE ON ai_listing_facts REFERENCING OLD TABLE AS old_inputs NEW TABLE AS new_inputs FOR EACH STATEMENT EXECUTE FUNCTION ai_live_ai_listing_facts_changed()""")
    op.execute("""ALTER TABLE ai_listing_facts ENABLE ALWAYS TRIGGER ai_live_ai_listing_facts_update""")
    op.execute("""CREATE TRIGGER ai_live_ai_listing_facts_delete AFTER DELETE ON ai_listing_facts REFERENCING OLD TABLE AS old_inputs FOR EACH STATEMENT EXECUTE FUNCTION ai_live_ai_listing_facts_changed()""")
    op.execute("""ALTER TABLE ai_listing_facts ENABLE ALWAYS TRIGGER ai_live_ai_listing_facts_delete""")
    op.execute("""INSERT INTO ai_live_input_versions (kind, record_id) SELECT 'listing', id FROM (SELECT id AS id FROM listings UNION SELECT listing_id AS id FROM listing_room_details UNION SELECT canonical_listing_id AS id FROM ai_fact_catalogs UNION SELECT canonical_listing_id AS id FROM ai_listing_search_features UNION SELECT canonical_listing_id AS id FROM ai_fact_sources) ids WHERE id IS NOT NULL""")
    op.execute("""INSERT INTO ai_live_input_versions (kind, record_id) SELECT 'external', id FROM (SELECT id AS id FROM external_listing_sources) ids WHERE id IS NOT NULL""")
    op.execute("""INSERT INTO ai_live_input_versions (kind, record_id) SELECT 'batch', id FROM (SELECT id AS id FROM ai_listing_fact_batches UNION SELECT batch_id AS id FROM ai_listing_facts) ids WHERE id IS NOT NULL""")
    op.execute("""CREATE FUNCTION ai_live_inputs_truncated() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
        INSERT INTO ai_live_input_epochs (id) VALUES (1)
        ON CONFLICT (id) DO UPDATE SET epoch=gen_random_uuid();
        RETURN NULL;
    END $$""")
    op.execute("""CREATE TRIGGER ai_live_listings_truncate AFTER TRUNCATE ON listings FOR EACH STATEMENT EXECUTE FUNCTION ai_live_inputs_truncated()""")
    op.execute("""ALTER TABLE listings ENABLE ALWAYS TRIGGER ai_live_listings_truncate""")
    op.execute("""CREATE TRIGGER ai_live_listing_room_details_truncate AFTER TRUNCATE ON listing_room_details FOR EACH STATEMENT EXECUTE FUNCTION ai_live_inputs_truncated()""")
    op.execute("""ALTER TABLE listing_room_details ENABLE ALWAYS TRIGGER ai_live_listing_room_details_truncate""")
    op.execute("""CREATE TRIGGER ai_live_ai_fact_catalogs_truncate AFTER TRUNCATE ON ai_fact_catalogs FOR EACH STATEMENT EXECUTE FUNCTION ai_live_inputs_truncated()""")
    op.execute("""ALTER TABLE ai_fact_catalogs ENABLE ALWAYS TRIGGER ai_live_ai_fact_catalogs_truncate""")
    op.execute("""CREATE TRIGGER ai_live_ai_listing_search_features_truncate AFTER TRUNCATE ON ai_listing_search_features FOR EACH STATEMENT EXECUTE FUNCTION ai_live_inputs_truncated()""")
    op.execute("""ALTER TABLE ai_listing_search_features ENABLE ALWAYS TRIGGER ai_live_ai_listing_search_features_truncate""")
    op.execute("""CREATE TRIGGER ai_live_ai_fact_sources_truncate AFTER TRUNCATE ON ai_fact_sources FOR EACH STATEMENT EXECUTE FUNCTION ai_live_inputs_truncated()""")
    op.execute("""ALTER TABLE ai_fact_sources ENABLE ALWAYS TRIGGER ai_live_ai_fact_sources_truncate""")
    op.execute("""CREATE TRIGGER ai_live_external_listing_sources_truncate AFTER TRUNCATE ON external_listing_sources FOR EACH STATEMENT EXECUTE FUNCTION ai_live_inputs_truncated()""")
    op.execute("""ALTER TABLE external_listing_sources ENABLE ALWAYS TRIGGER ai_live_external_listing_sources_truncate""")
    op.execute("""CREATE TRIGGER ai_live_ai_listing_fact_batches_truncate AFTER TRUNCATE ON ai_listing_fact_batches FOR EACH STATEMENT EXECUTE FUNCTION ai_live_inputs_truncated()""")
    op.execute("""ALTER TABLE ai_listing_fact_batches ENABLE ALWAYS TRIGGER ai_live_ai_listing_fact_batches_truncate""")
    op.execute("""CREATE TRIGGER ai_live_ai_listing_facts_truncate AFTER TRUNCATE ON ai_listing_facts FOR EACH STATEMENT EXECUTE FUNCTION ai_live_inputs_truncated()""")
    op.execute("""ALTER TABLE ai_listing_facts ENABLE ALWAYS TRIGGER ai_live_ai_listing_facts_truncate""")
    op.execute("""CREATE TRIGGER ai_live_ai_live_input_versions_truncate AFTER TRUNCATE ON ai_live_input_versions FOR EACH STATEMENT EXECUTE FUNCTION ai_live_inputs_truncated()""")
    op.execute("""ALTER TABLE ai_live_input_versions ENABLE ALWAYS TRIGGER ai_live_ai_live_input_versions_truncate""")
    op.execute("""CREATE FUNCTION ai_live_input_schema_signature() RETURNS text
    LANGUAGE sql STABLE PARALLEL SAFE AS $$
    WITH triggers AS (
        SELECT count(*) AS n, bool_and(tgenabled='A') AS enabled,
            jsonb_agg(jsonb_build_array(tgrelid,tgname,tgtype,tgenabled,tgfoid,xmin::text,ctid::text)
                      ORDER BY tgrelid,tgname) AS value
        FROM pg_trigger WHERE NOT tgisinternal AND tgname LIKE 'ai_live_%'
        AND tgrelid IN ('listings'::regclass,'listing_room_details'::regclass,'ai_fact_catalogs'::regclass,'ai_listing_search_features'::regclass,'ai_fact_sources'::regclass,'external_listing_sources'::regclass,'ai_listing_fact_batches'::regclass,'ai_listing_facts'::regclass,'ai_live_input_versions'::regclass)
    ), attributes AS (
        SELECT jsonb_agg(jsonb_build_array(attrelid,attnum,attname,atttypid,atttypmod,attcollation,attisdropped,xmin::text,ctid::text)
                         ORDER BY attrelid,attnum) AS value
        FROM pg_attribute WHERE attnum>0 AND attrelid IN ('listings'::regclass,'listing_room_details'::regclass,'ai_fact_catalogs'::regclass,'ai_listing_search_features'::regclass,'ai_fact_sources'::regclass,'external_listing_sources'::regclass,'ai_listing_fact_batches'::regclass,'ai_listing_facts'::regclass)
    )
    SELECT CASE WHEN triggers.n=33 AND triggers.enabled THEN
        encode(sha256(convert_to(jsonb_build_array(triggers.value,attributes.value)::text,'UTF8')),'hex') END
    FROM triggers CROSS JOIN attributes
    $$""")
    op.execute("""CREATE FUNCTION ai_live_input_vector(target uuid) RETURNS jsonb
    LANGUAGE sql STABLE PARALLEL SAFE AS $$
    WITH authority_ids AS (
        SELECT id FROM external_listing_sources WHERE canonical_listing_id=target
        UNION SELECT source_record_id FROM ai_fact_sources WHERE canonical_listing_id=target
    ), batch_ids AS (
        SELECT DISTINCT batch_id AS id FROM ai_fact_sources
        WHERE canonical_listing_id=target AND batch_id IS NOT NULL
    ), authority AS (
        SELECT coalesce(jsonb_agg(jsonb_build_array(ids.id, v.token) ORDER BY ids.id), '[]'::jsonb) AS value,
               coalesce(bool_and(v.token IS NOT NULL), true) AS valid
        FROM authority_ids ids LEFT JOIN ai_live_input_versions v ON v.kind='external' AND v.record_id=ids.id
    ), batches AS (
        SELECT coalesce(jsonb_agg(jsonb_build_array(ids.id, v.token) ORDER BY ids.id), '[]'::jsonb) AS value,
               coalesce(bool_and(v.token IS NOT NULL), true) AS valid
        FROM batch_ids ids LEFT JOIN ai_live_input_versions v ON v.kind='batch' AND v.record_id=ids.id
    )
    SELECT CASE WHEN authority.valid AND batches.valid AND schema.value IS NOT NULL THEN
        jsonb_build_object('contract', 'live-inputs.v1', 'schema', schema.value,
            'epoch', e.epoch, 'listing', v.token, 'authority', authority.value, 'batches', batches.value) END
    FROM ai_live_input_epochs e CROSS JOIN ai_live_input_versions v CROSS JOIN authority CROSS JOIN batches
    CROSS JOIN (SELECT ai_live_input_schema_signature() AS value OFFSET 0) schema
    WHERE e.id=1 AND v.kind='listing' AND v.record_id=target
    $$""")
    op.execute("""CREATE FUNCTION ai_live_input_signature(target uuid) RETURNS text
    LANGUAGE sql STABLE PARALLEL SAFE AS $$
    SELECT encode(sha256(convert_to(ai_live_input_vector(target)::text,'UTF8')),'hex')
    $$""")


def downgrade():
    pass  # additive state is retained on binary rollback
