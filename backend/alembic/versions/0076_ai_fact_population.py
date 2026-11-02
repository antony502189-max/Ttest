"""Transactional fact-catalog identity for constant-size cursor reads."""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0076_ai_fact_population"
down_revision = "0075_ai_proof_population"
branch_labels = None
depends_on = None


def upgrade():
    # Install the identity and all writers atomically, including for populated
    # catalogs. No backfill/scan is necessary: this is a generation, not a sum.
    op.execute("LOCK TABLE ai_fact_catalogs IN SHARE ROW EXCLUSIVE MODE")
    op.create_table("ai_fact_population",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("epoch", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("revision", sa.BigInteger(), nullable=False),
        sa.CheckConstraint("id = 1 AND revision > 0", name="ck_ai_fact_population_singleton"))
    op.execute("INSERT INTO ai_fact_population (id, revision) VALUES (1, 1)")
    op.execute("""CREATE FUNCTION ai_fact_population_changed() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE changed boolean;
    BEGIN
        IF TG_OP = 'INSERT' THEN
            changed := EXISTS (SELECT FROM new_catalogs);
        ELSIF TG_OP = 'DELETE' THEN
            changed := EXISTS (SELECT FROM old_catalogs);
        ELSIF TG_OP = 'UPDATE' THEN
            changed := EXISTS ((SELECT * FROM new_catalogs EXCEPT SELECT * FROM old_catalogs)
                UNION ALL (SELECT * FROM old_catalogs EXCEPT SELECT * FROM new_catalogs));
        ELSE
            changed := TRUE;
        END IF;
        IF changed THEN
            INSERT INTO ai_fact_population (id, revision) VALUES (1, 1)
            ON CONFLICT (id) DO UPDATE SET revision = ai_fact_population.revision + 1;
        END IF;
        RETURN NULL;
    END $$""")
    op.execute("CREATE TRIGGER ai_fact_population_insert AFTER INSERT ON ai_fact_catalogs "
               "REFERENCING NEW TABLE AS new_catalogs FOR EACH STATEMENT EXECUTE FUNCTION ai_fact_population_changed()")
    op.execute("CREATE TRIGGER ai_fact_population_update AFTER UPDATE ON ai_fact_catalogs "
               "REFERENCING OLD TABLE AS old_catalogs NEW TABLE AS new_catalogs "
               "FOR EACH STATEMENT EXECUTE FUNCTION ai_fact_population_changed()")
    op.execute("CREATE TRIGGER ai_fact_population_delete AFTER DELETE ON ai_fact_catalogs "
               "REFERENCING OLD TABLE AS old_catalogs FOR EACH STATEMENT EXECUTE FUNCTION ai_fact_population_changed()")
    op.execute("CREATE TRIGGER ai_fact_population_truncate AFTER TRUNCATE ON ai_fact_catalogs "
               "FOR EACH STATEMENT EXECUTE FUNCTION ai_fact_population_changed()")


def downgrade():
    # Additive state remains available to older binaries, which still read the
    # original catalog. Do not destroy data on binary rollback.
    pass
