import hashlib
from uuid import uuid4

from app.services.auth import verification_code_hash


def test_verification_code_hash_is_keyed_deterministic_and_user_bound():
    code = "123456"
    first_user = uuid4()
    second_user = uuid4()

    first = verification_code_hash(first_user, code)

    assert first == verification_code_hash(first_user, code)
    assert first != verification_code_hash(second_user, code)
    assert first != verification_code_hash(first_user, "654321")
    assert first != hashlib.sha256(code.encode()).hexdigest()
    assert len(first) == 64
