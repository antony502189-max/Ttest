"""Immutable v1 experiment specification; a new experiment needs a new version.

These are not configurable production prices or an authorization to spend.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class SmokeSpec:
    version: str = "ai-closed-ui-experiment.v1"
    corpus_sha256: str = "7b722ab6caa0bf3377a0ace8fcddecf6daa7f7cb9bcebec515ab0cac9997d288"
    case_ids: tuple[str, ...] = ("ru-balcony", "es-monthly", "en-negation")
    baseline_attempts: int = 51
    reserve_micro_usd: int = 11060
    max_micro_usd: int = 750000

    @property
    def attempt_fence(self):
        return self.baseline_attempts + len(self.case_ids)


SPEC = SmokeSpec()
CASE_IDS, CORPUS_SHA256 = SPEC.case_ids, SPEC.corpus_sha256
