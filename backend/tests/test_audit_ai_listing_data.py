import asyncio
import copy
import json
from pathlib import Path

from app.commands import audit_ai_listing_data as audit

FIXTURE = Path(__file__).parent / "fixtures/ai_listing_audit.json"


def records():
    return [audit.AuditRecord.model_validate(value) for value in json.loads(FIXTURE.read_text(encoding="utf-8"))]


def test_metrics_count_evidence_not_defaults_and_conflicts_ignore_unknown():
    values = records()
    before = copy.deepcopy(values)
    report = audit.audit_records(values)
    assert values == before
    assert report == audit.audit_records(values)
    idealista = report["sources"]["Idealista"]
    assert idealista["records"] == 2
    assert idealista["policies"]["room_capacity"]["explicit_pct"] == 50
    assert idealista["description_length"]["histogram"]["1_79"] == 2
    unknown = report["sources"]["Habitaclia"]
    assert unknown["description_present_pct"] == 0
    assert unknown["unknown_provenance_pct"] == 100
    assert unknown["policies"]["children_allowed"]["explicit_pct"] == 0
    assert unknown["policies"]["room_capacity"]["explicit_pct"] == 0
    assert unknown["geo_confirmed_pct"] is None
    assert unknown["potential_conflicting_source_records"] == 1  # default 1 vs explicit capacity 4
    assert report["potential_conflicting_canonical_listings"] == 1
    assert report["sources"]["Fotocasa"]["policies"]["pets_allowed"]["states"]["conditional"] == 1
    assert report["sources"]["Pisos"]["description_present_pct"] is None
    assert report["sources"]["Pisos"]["description_length"]["p95"] is None


def test_cli_is_repeatable_and_export_contains_only_aggregates(tmp_path, capsys):
    original = FIXTURE.read_bytes()
    output = tmp_path / "audit.json"
    assert audit.main(["--input", str(FIXTURE), "--output", str(output)]) == 0
    first = output.read_bytes()
    assert audit.main(["--input", str(FIXTURE), "--output", str(output)]) == 0
    assert output.read_bytes() == first
    assert FIXTURE.read_bytes() == original
    report = json.loads(first)
    assert report["records"] == 4
    assert audit.main(["--input", str(FIXTURE), "--format", "markdown"]) == 0
    rendered = capsys.readouterr().out
    assert "N/A" in rendered and "| Idealista |" in rendered
    for text in (first.decode(), rendered):
        assert "private@" not in text and "secret" not in text and "shared-1" not in text
        assert "Se admiten mascotas" not in text


def test_missing_description_empty_dataset_and_untrusted_source_labels():
    report = audit.audit_records(
        [
            audit.AuditRecord(
                source_name="owner@example.test",
                canonical_listing_id="id",
                normalized_payload={},
            )
        ]
    )
    assert report["sources"]["Other"]["records"] == 1
    assert "owner@" not in json.dumps(report)
    assert audit.audit_records([])["records"] == 0
    contact_only = audit.audit_records(
        [
            audit.AuditRecord(
                source_name="Flatio",
                canonical_listing_id="id",
                normalized_payload={"description": "+34 612 345 678 private@example.test"},
            )
        ]
    )
    assert contact_only["sources"]["Flatio"]["description_present_pct"] == 0


def test_cli_failures_do_not_print_input_or_overwrite_fixture(tmp_path, capsys):
    path = tmp_path / "invalid.json"
    path.write_text('[{"private":"private@example.test"}]', encoding="utf-8")
    assert audit.main(["--input", str(path)]) == 1
    assert "private@" not in capsys.readouterr().err
    before = FIXTURE.read_bytes()
    assert audit.main(["--input", str(FIXTURE), "--output", str(FIXTURE)]) == 1
    assert FIXTURE.read_bytes() == before


def test_database_reader_uses_server_enforced_readonly_and_rollback(monkeypatch):
    from sqlalchemy.dialects import postgresql
    from sqlalchemy.ext import asyncio as sa_asyncio

    events = []

    class Cursor:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            events.append("cursor_closed")

        def __aiter__(self):
            async def rows():
                yield "Flatio", "id", "active", {"description": "No pets"}

            return rows()

    class Connection:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            events.append("closed")

        async def execution_options(self, **kwargs):
            assert kwargs == {"isolation_level": "REPEATABLE READ"}
            return self

        async def begin(self):
            events.append("begin")
            return self

        async def exec_driver_sql(self, query):
            assert query == "SET TRANSACTION READ ONLY"
            events.append("readonly")

        def stream(self, query):
            assert events[-1] == "readonly"
            sql = str(query.compile(dialect=postgresql.dialect()))
            assert sql.startswith("SELECT ") and "raw_payload" not in sql
            assert query.get_execution_options()["yield_per"] == 500
            events.append("select")
            return Cursor()

        async def rollback(self):
            events.append("rollback")

    class Engine:
        def connect(self):
            return Connection()

        async def dispose(self):
            events.append("disposed")

    def create_engine(url, **kwargs):
        assert kwargs["connect_args"]["server_settings"]["default_transaction_read_only"] == "on"
        return Engine()

    monkeypatch.setattr(sa_asyncio, "create_async_engine", create_engine)
    report = asyncio.run(audit._database_report("postgresql+asyncpg://fixture", False))
    assert report["records"] == 1
    assert events == ["begin", "readonly", "select", "cursor_closed", "rollback", "closed", "disposed"]
