"""Cursor identity only; never a replacement for live evidence/eligibility."""
from sqlalchemy import func, select

from ..models.ai_fact_pipeline import AiFactPopulation


def fact_population_signature():
    """O(1) snapshot-consistent catalog generation, NULL if state is missing.

    Statement triggers cover direct SQL, COPY, upserts, remaps and TRUNCATE.
    Rollback restores both data and generation; a fresh epoch prevents cursor
    revival after singleton recreation. Restoring old catalog values also
    invalidates old cursors. No-op writes preserve the generation.

    This tracks precisely the fact-catalog dependency. All source, canonical,
    room, fact/batch and time-dependent public eligibility checks still run
    separately before count/order/seek/LIMIT and map aggregation.
    """
    state = AiFactPopulation
    return select(func.concat("fact-population.v1:", state.epoch, ":", state.revision)).where(
        state.id == 1).scalar_subquery()
