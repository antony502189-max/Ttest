"""Reuse repository fixtures against an explicitly isolated, disposable audit DB."""
import importlib.util
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SOURCE = ROOT / 'backend' / 'tests' / 'integration'
assert os.environ.get('DATABASE_URL', '').endswith('/audit_payment_extra')
sys.path.insert(0, str(SOURCE))
spec = importlib.util.spec_from_file_location('audit_payment_fixture_source', SOURCE / 'conftest.py')
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)
anyio_backend = fixtures.anyio_backend
clean_database = fixtures.clean_database
client = fixtures.client
register_user = fixtures.register_user

