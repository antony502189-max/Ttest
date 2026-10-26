from unittest.mock import Mock

import pytest

from app.repositories.ai_fact_pipeline import FactPipeline
from app.repositories.ai_fact_snapshots import FactSnapshotReader
from app.schemas.ai_fact_bridge import BridgeMapping
from app.services.ai_offline_fact_worker import OfflineFactJobRunner


@pytest.mark.parametrize("version,retry", [(True, False), ("", False), ("fixture.v1", 1)])
def test_worker_configuration_has_no_coercion_or_implicit_retry_policy(version, retry):
    mapping = BridgeMapping(structured_fields={}, rented_unit_capacity_fields=frozenset(), text_capacity_scope=None,
                             structured_smoking_scopes={}, text_smoking_scopes={}, amenity_codes={})
    with pytest.raises(ValueError):
        OfflineFactJobRunner(Mock(spec=FactPipeline), Mock(spec=FactSnapshotReader), builder=Mock(), mapping=mapping,
                             extractor_version=version, retry_builder_failures=retry)
