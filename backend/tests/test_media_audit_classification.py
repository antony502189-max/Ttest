from app.commands.audit_media import classify_asset


def test_media_audit_only_confirms_deleted_unreferenced_existing_objects():
    assert classify_asset(referenced=False, object_exists=True, pending=False, deleted=True) == "ORPHAN_CONFIRMED"
    assert classify_asset(referenced=True, object_exists=True, pending=False, deleted=True) == "LIVE_REFERENCED"
    assert classify_asset(referenced=True, object_exists=False, pending=True, deleted=True) == "DB_REFERENCE_MISSING_OBJECT"
    assert classify_asset(referenced=False, object_exists=True, pending=True, deleted=True) == "PENDING_DELETE"
    assert classify_asset(referenced=False, object_exists=True, pending=False, deleted=False) == "UNKNOWN"
