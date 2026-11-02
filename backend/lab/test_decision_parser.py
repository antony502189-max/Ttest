import unittest
from unittest.mock import AsyncMock
from uuid import uuid4

from app.schemas.ai_search_intent import Criteria, SearchIntent, apply_patch
from app.services.ai_deepseek_intent import ProviderFailure
from lab.decision_parser import LocalDecisionParser


class DecisionComposition(unittest.IsolatedAsyncioTestCase):
    async def test_typed_chain_preserves_hard_and_server_identity(self):
        redis = AsyncMock()
        redis.getdel.return_value = None
        parser = LocalDecisionParser(redis)
        current = SearchIntent(schema_version="ai-search.v1", taxonomy_version="rental.v1",
                               session_id=uuid4(), version=0, criteria=Criteria())
        for text in ("с маленькой собакой", "до 600 евро в месяц", "желательно с балконом"):
            patch = await parser.parse(text, current)
            self.assertEqual(patch.session_id, current.session_id)
            self.assertEqual(patch.expected_version, current.version)
            current = apply_patch(current, patch)
        self.assertEqual(current.criteria.pets.strength, "hard")
        self.assertEqual(current.criteria.budget.strength, "hard")
        self.assertEqual(current.criteria.balcony.strength, "soft")
        for text, code in (("уточнить бюджет", "INTENT_CLARIFICATION_REQUIRED"),
                           ("ничего не менять", "INTENT_NO_CHANGE"),
                           ("рядом с хорошими людьми", "INTENT_UNSUPPORTED")):
            with self.assertRaisesRegex(ProviderFailure, code):
                await parser.parse(text, current)
        self.assertEqual(current.version, 3)
        self.assertEqual(redis.incr.await_count, 6)
