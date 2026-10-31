"""Acceptance recomputes raw evidence and requires both completeness and SLO."""
import importlib.util
import json
from pathlib import Path

import pytest
from test_ai_map_toolchain import complete


def gate():
    path = Path(__file__).parents[2] / 'scripts/check-ai-map-capacity.py'
    spec = importlib.util.spec_from_file_location('capacity_acceptance', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize('damage', ['none', 'wrong_sha', 'missing_scale', 'forged_summary', 'raw_failure'])
def test_capacity_acceptance_checks_current_raw_evidence(tmp_path, damage):
    if damage == 'forged_summary':
        (tmp_path / 'summary.json').write_text(json.dumps({'protocol_complete': True, 'slo_passed': True}))
    else:
        for size in (100000, 500000, 1000000): complete(tmp_path, size)
        if damage == 'missing_scale': (tmp_path / 'load-1000000.json').unlink()
        if damage == 'raw_failure':
            path = tmp_path / 'load-100000.json'
            cases = json.loads(path.read_text())
            cases[0]['results'][0]['ok'] = False
            path.write_text(json.dumps(cases))
    sha = 'c' * 40 if damage == 'wrong_sha' else 'b' * 40
    if damage == 'none':
        assert gate().accept(tmp_path, sha)['slo_passed'] is True
    else:
        with pytest.raises(ValueError): gate().accept(tmp_path, sha)


def test_completed_protocol_without_successful_slo_is_not_acceptance(tmp_path, monkeypatch):
    module = gate()
    # Protocol completion is intentionally independent of measured success.
    # This distinction must remain true even if the summarizer's CLI exits 0.
    class Summary:
        @staticmethod
        def summarize(_):
            return {'provenance': {'code_revision': 'b' * 40}, 'protocol_complete': True, 'slo_passed': False}
    monkeypatch.setattr(module.importlib.util, 'module_from_spec', lambda _: Summary)
    monkeypatch.setattr(module.importlib.util, 'spec_from_file_location', lambda *_: type('Spec', (), {
        'loader': type('Loader', (), {'exec_module': lambda *_: None})()})())
    with pytest.raises(ValueError, match='SLOs must pass'): module.accept(tmp_path, 'b' * 40)
