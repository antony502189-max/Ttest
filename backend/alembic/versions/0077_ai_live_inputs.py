"""Transactional input tokens; retain full v2 verification on preparation."""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0077_ai_live_inputs"
down_revision = "0076_ai_fact_population"
branch_labels = None
depends_on = None

# Keys come directly from the changed records, never from a possibly stale
# relationship lookup in a trigger. Fact changes touch their old/new batch;
# authority changes touch their own identity, including after a remap/delete.
INPUTS = (
    ("listings", "id", "listing", "id", ("views", "updated_at")),
    ("listing_room_details", "listing_id", "listing", "listing_id", ()),
    ("ai_fact_catalogs", "canonical_listing_id", "listing", "canonical_listing_id", ()),
    ("ai_listing_search_features", "canonical_listing_id", "listing", "canonical_listing_id", ()),
    ("ai_fact_sources", "source_record_id", "listing", "canonical_listing_id", ()),
    ("external_listing_sources", "id", "external", "id", ()),
    ("ai_listing_fact_batches", "id", "batch", "id", ()),
    ("ai_listing_facts", "id", "batch", "batch_id", ()),
)


def upgrade():
    op.execute("LOCK TABLE " + ", ".join(row[0] for row in INPUTS) + " IN SHARE ROW EXCLUSIVE MODE")
    op.create_table("ai_live_input_epochs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("epoch", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.CheckConstraint("id = 1", name="ck_ai_live_epoch_singleton"))
    op.execute("INSERT INTO ai_live_input_epochs (id) VALUES (1)")
    op.create_table("ai_live_input_versions",
        sa.Column("kind", sa.String(16), primary_key=True),
        sa.Column("record_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("token", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.CheckConstraint("kind IN ('listing','external','batch')", name="ck_ai_live_input_kind"))
    op.add_column("ai_query_proofs", sa.Column("input_signature", sa.String(64), nullable=True))
    op.add_column("ai_query_proofs", sa.Column("input_binding", sa.String(64), nullable=True))
    op.add_column("ai_query_proofs", sa.Column("input_vector", postgresql.JSONB(), nullable=True))
    op.create_check_constraint("ck_ai_query_proof_inputs", "ai_query_proofs",
        "(input_signature IS NULL AND input_binding IS NULL AND input_vector IS NULL) OR "
        "(input_signature IS NOT NULL AND input_binding IS NOT NULL AND input_vector IS NOT NULL AND "
        "input_signature ~ '^[0-9a-f]{64}$' AND input_binding ~ '^[0-9a-f]{64}$')")

    for table, pk, kind, key, ignored in INPUTS:
        # A full join also covers PK changes. JSON comparison happens on the
        # write path only; views/updated_at retain the original v2 exception.
        old, new = "to_jsonb(o)", "to_jsonb(n)"
        for field in ignored:
            old += f" - '{field}'"
            new += f" - '{field}'"
        membership = ""
        if table == "external_listing_sources":
            # New/deleted/remapped authority membership changes the canonical
            # token too. Existing/former owners also depend on the external ID.
            membership = f"""
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
                    WHERE ({old})::text IS DISTINCT FROM ({new})::text
                    UNION
                    SELECT n.canonical_listing_id AS id FROM old_inputs o FULL JOIN new_inputs n ON o.id=n.id
                    WHERE ({old})::text IS DISTINCT FROM ({new})::text
                ) changed WHERE changed.id IS NOT NULL ORDER BY changed.id
                ON CONFLICT (kind, record_id) DO UPDATE SET token=gen_random_uuid();
            END IF;"""
        op.execute(f"""CREATE FUNCTION ai_live_{table}_changed() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'INSERT' THEN
                INSERT INTO ai_live_input_versions (kind, record_id)
                SELECT '{kind}', {key} FROM new_inputs WHERE {key} IS NOT NULL GROUP BY {key} ORDER BY {key}
                ON CONFLICT (kind, record_id) DO UPDATE SET token=gen_random_uuid();
            ELSIF TG_OP = 'DELETE' THEN
                INSERT INTO ai_live_input_versions (kind, record_id)
                SELECT '{kind}', {key} FROM old_inputs WHERE {key} IS NOT NULL GROUP BY {key} ORDER BY {key}
                ON CONFLICT (kind, record_id) DO UPDATE SET token=gen_random_uuid();
            ELSE
                INSERT INTO ai_live_input_versions (kind, record_id)
                SELECT '{kind}', changed.id FROM (
                    SELECT o.{key} AS id FROM old_inputs o FULL JOIN new_inputs n ON o.{pk}=n.{pk}
                    WHERE ({old})::text IS DISTINCT FROM ({new})::text
                    UNION
                    SELECT n.{key} AS id FROM old_inputs o FULL JOIN new_inputs n ON o.{pk}=n.{pk}
                    WHERE ({old})::text IS DISTINCT FROM ({new})::text
                ) changed WHERE changed.id IS NOT NULL ORDER BY changed.id
                ON CONFLICT (kind, record_id) DO UPDATE SET token=gen_random_uuid();
            END IF;
            {membership}
            RETURN NULL;
        END $$""")
        for event, refs in (("INSERT", "NEW TABLE AS new_inputs"),
                            ("UPDATE", "OLD TABLE AS old_inputs NEW TABLE AS new_inputs"),
                            ("DELETE", "OLD TABLE AS old_inputs")):
            op.execute(f"CREATE TRIGGER ai_live_{table}_{event.lower()} AFTER {event} ON {table} "
                       f"REFERENCING {refs} FOR EACH STATEMENT EXECUTE FUNCTION ai_live_{table}_changed()")
            op.execute(f"ALTER TABLE {table} ENABLE ALWAYS TRIGGER ai_live_{table}_{event.lower()}")

    # Backfill versions only, not proofs or source facts. Installation locks
    # prevent an unobserved writer between this seed and trigger activation.
    for kind in ("listing", "external", "batch"):
        selects = [f"SELECT {key} AS id FROM {table}" for table, _, item_kind, key, _ in INPUTS if item_kind == kind]
        op.execute("INSERT INTO ai_live_input_versions (kind, record_id) "
                   f"SELECT '{kind}', id FROM (" + " UNION ".join(selects) + ") ids WHERE id IS NOT NULL")

    op.execute("""CREATE FUNCTION ai_live_inputs_truncated() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
        INSERT INTO ai_live_input_epochs (id) VALUES (1)
        ON CONFLICT (id) DO UPDATE SET epoch=gen_random_uuid();
        RETURN NULL;
    END $$""")
    for table in [row[0] for row in INPUTS] + ["ai_live_input_versions"]:
        op.execute(f"CREATE TRIGGER ai_live_{table}_truncate AFTER TRUNCATE ON {table} "
                   "FOR EACH STATEMENT EXECUTE FUNCTION ai_live_inputs_truncated()")
        op.execute(f"ALTER TABLE {table} ENABLE ALWAYS TRIGGER ai_live_{table}_truncate")

    tables = ",".join(f"'{row[0]}'::regclass" for row in INPUTS)
    op.execute(f"""CREATE FUNCTION ai_live_input_schema_signature() RETURNS text
    LANGUAGE sql STABLE PARALLEL SAFE AS $$
    WITH triggers AS (
        SELECT count(*) AS n, bool_and(tgenabled='A') AS enabled,
            jsonb_agg(jsonb_build_array(tgrelid,tgname,tgtype,tgenabled,tgfoid,xmin::text,ctid::text)
                      ORDER BY tgrelid,tgname) AS value
        FROM pg_trigger WHERE NOT tgisinternal AND tgname LIKE 'ai_live_%'
        AND tgrelid IN ({tables},'ai_live_input_versions'::regclass)
    ), attributes AS (
        SELECT jsonb_agg(jsonb_build_array(attrelid,attnum,attname,atttypid,atttypmod,attcollation,attisdropped,xmin::text,ctid::text)
                         ORDER BY attrelid,attnum) AS value
        FROM pg_attribute WHERE attnum>0 AND attrelid IN ({tables})
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
    pass  # expand-only; old binaries continue checking the full v2 digest
