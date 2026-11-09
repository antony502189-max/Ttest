"""Host timer: read only the immutable pilot cohort from existing production imports.

Run as the existing pilot operator. No crawling, discovery, provider IO or reseeding.
Receipts stay in memory; source timestamps come from the importer, never the timer.
"""
import json
import subprocess
from pathlib import Path

ROOT = Path('/srv/112233-ai-site-pilot-20261108')
BACKEND = 'ttest-ai-site-pilot-20261108-backend-1'
PRIMARY = 'ttest-production-postgres-1'


def run(argv, payload=None):
    result = subprocess.run(argv, input=payload, text=True, encoding='utf-8',
                            capture_output=True, timeout=90, check=False)
    if result.returncode:
        # Do not log payloads, URLs, configuration or subprocess tracebacks.
        raise RuntimeError('PILOT_REFRESH_SUBPROCESS_FAILED: ' + argv[0])
    return result.stdout


def main():
    directory = ROOT / 'catalog-refresh'
    purpose = run(['docker','inspect',BACKEND,'--format',
                   '{{index .Config.Labels "es.ttest.purpose"}}']).strip()
    if purpose != 'ai-site-pilot-20261108' or not (ROOT/'owner-purpose').read_text().startswith('ai-site-pilot-20261108;'):
        raise RuntimeError('PILOT_REFRESH_OWNER_MISMATCH')
    exporter = (directory / 'export_public.py').read_text()
    updater = (directory / 'refresh.py').read_text()
    sql = run(['docker','exec','-i',BACKEND,'python','-c',exporter,
               '--cohort','/demo-input/catalog.json','--sql-only'])
    receipt = run(['docker','exec','-i',PRIMARY,'sh','-c',
                   'exec psql -X -qAt -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"'], sql)
    # Validate syntax before sending only this bounded, whitelisted receipt onward.
    value = json.loads(receipt)
    if not isinstance(value.get('records'), list) or not 1 <= len(value['records']) <= 20:
        raise RuntimeError('PILOT_REFRESH_EMPTY_OR_UNBOUNDED')
    print(run(['docker','exec','-i',BACKEND,'python','-c',updater,'-'], receipt).strip())


if __name__ == '__main__':
    main()
