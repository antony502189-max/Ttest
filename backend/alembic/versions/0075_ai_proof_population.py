"""Transactional prepared-proof population identity; no eligibility cache."""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0075_ai_proof_population"
down_revision = "0074_ai_saved_searches"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("ai_proof_population",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("epoch", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("revision", sa.BigInteger(), nullable=False),
        sa.CheckConstraint("id = 1 AND revision > 0", name="ck_ai_proof_population_singleton"))
    op.execute("INSERT INTO ai_proof_population (id, revision) VALUES (1, 1)")
    # Statement triggers cover bulk/COPY, ON CONFLICT, direct SQL, deletes and
    # TRUNCATE. Set comparison suppresses no-op preparation without relying on
    # application writers. The locked counter update is transactional: snapshots
    # cannot observe a changed proof set with its previous population identity.
    op.execute("""CREATE FUNCTION ai_proof_population_changed() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE changed boolean;
    BEGIN
        IF TG_OP = 'INSERT' THEN
            changed := EXISTS (SELECT FROM new_proofs);
        ELSIF TG_OP = 'DELETE' THEN
            changed := EXISTS (SELECT FROM old_proofs);
        ELSIF TG_OP = 'UPDATE' THEN
            changed := EXISTS ((SELECT * FROM new_proofs EXCEPT SELECT * FROM old_proofs)
                UNION ALL (SELECT * FROM old_proofs EXCEPT SELECT * FROM new_proofs));
        ELSE
            changed := TRUE;
        END IF;
        IF changed THEN
            INSERT INTO ai_proof_population (id, revision) VALUES (1, 1)
            ON CONFLICT (id) DO UPDATE SET revision = ai_proof_population.revision + 1;
        END IF;
        RETURN NULL;
    END $$""")
    op.execute("CREATE TRIGGER ai_proof_population_insert AFTER INSERT ON ai_query_proofs "
               "REFERENCING NEW TABLE AS new_proofs FOR EACH STATEMENT EXECUTE FUNCTION ai_proof_population_changed()")
    op.execute("CREATE TRIGGER ai_proof_population_update AFTER UPDATE ON ai_query_proofs "
               "REFERENCING OLD TABLE AS old_proofs NEW TABLE AS new_proofs "
               "FOR EACH STATEMENT EXECUTE FUNCTION ai_proof_population_changed()")
    op.execute("CREATE TRIGGER ai_proof_population_delete AFTER DELETE ON ai_query_proofs "
               "REFERENCING OLD TABLE AS old_proofs FOR EACH STATEMENT EXECUTE FUNCTION ai_proof_population_changed()")
    op.execute("CREATE TRIGGER ai_proof_population_truncate AFTER TRUNCATE ON ai_query_proofs "
               "FOR EACH STATEMENT EXECUTE FUNCTION ai_proof_population_changed()")


def downgrade():
    # Preserve additive history on binary rollback, as in previous AI migrations.
    pass
