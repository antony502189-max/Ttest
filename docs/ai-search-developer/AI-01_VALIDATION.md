# AI-01 — Offline validation and requirement coverage

Дата: 2026-10-26. Среда: local Windows checkout от `main` 1292c680; только docs и synthetic examples. Контракты **PROPOSED**, не приняты автоматически. Никаких application/runtime changes. Final SHA/PR/CI привязаны к GitHub PR, содержащему этот отчёт; отдельно проверяются после push.

## Покрытие

| Requirements ТЗ | Артефакт | Проверка / предел доказательства |
| --- | --- | --- |
| §1,4,5 provenance/taxonomy/unknown/defaults | ADR §1–2, ListingFact examples, M03–M13/M22–23/F01–04 | Synthetic spans/hash/UUID проверены; resolver/DB ещё отсутствуют |
| §2,5,7 exact compatibility, capacity, periods | ADR §3, M01–M24 | 24 ожидаемых сценария для будущих matcher tests; SQL tests ещё не выполнялись |
| §2,6 follow-up, strict patch, CAS | ADR §4, P01–P10, patch sequence | Offline replay примеров сохраняет неназванные критерии; Pydantic runtime ещё отсутствует |
| §6 3/200, Madrid, idempotency, failure recovery | ADR §6, Q01–Q12, madrid_days | Реальные IANA midnight/DST вычисления локально; races/crash recovery пока спецификация |
| §7 TOP/filter-before-count/cursor | ADR §5, R01–R05 | Сопоставлено с main source anchors; production plans/performance не проверялись |
| §8 auth-only saved searches/rematch/dedup | ADR §7, S01–S04 | Учтён existing matcher ignoring AI fields; runtime/outbox race tests впереди |
| §3,4,10 privacy/one Send/10s/gates | ADR §7–8, X01–X02 | Политика описана; providers/live staging/privacy review/SLO не измерены |
| §9,11 delivery/dependencies | Next actions, README_AI01 | Main+payment #372 сохранён; #373 не перенесён; status/gates явно указаны |

## Воспроизводимая проверка примеров

Фактический результат локального запуска: **PASS** — JSON duplicate-key/shape checks, evidence spans/content hash/UUID, 3 последовательных patch examples, Adeje/Arona INE, 3 Madrid day/reset fixtures (23/25/24h), 67 локальных ссылок. Scenario inventory: **61** спецификационный сценарий (24 matching, 10 patch, 12 quota, 5 ranking, 4 facts, 4 saved-search, 1 privacy, 1 UX). Эти 61 сценарий **не запускались как business tests**: соответствующего runtime ещё нет. `git diff --check` passed после staging; scope только docs.

Из корня репозитория выполнить следующий Python 3.12+ блок (stdlib; на Windows нужен установленный IANA `tzdata`, уже доступный в использованном Python environment). Это проверка **документационных артефактов**, не runtime validator/schema и не тест будущего matcher/ledger. `assert` запускать без `python -O`.

```python
import copy
import hashlib
import json
import re
from collections import Counter
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID
from zoneinfo import ZoneInfo

root = Path.cwd()
folder = root / 'docs/ai-search-developer'

def unique_object(pairs):
    result = {}
    for key, value in pairs:
        assert key not in result, f'duplicate JSON key: {key}'
        result[key] = value
    return result

def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=unique_object)

examples = read_json(folder / 'contracts/dto-examples-v1.json')
scenarios = read_json(folder / 'contracts/acceptance-v1.json')
assert examples['synthetic'] is scenarios['synthetic'] is True
assert examples['schema_version'] == scenarios['schema_version'] == 'ai-search.v1'
cases = scenarios['cases']
assert len(cases) == len({case['id'] for case in cases})
assert all(set(case) == {'id', 'area', 'given', 'expected', 'invariant'} for case in cases)
assert all(all(isinstance(v, str) and v for v in case.values()) for case in cases)
negative = {'incompatible', 'unresolved', 'conflict', 'invalid_patch', 'clarification'}
assert sum(case['expected'] in negative for case in cases) >= 12

snapshot = examples['sanitized_snapshot']['description']
for fact in examples['listing_facts']:
    for key in ('fact_id', 'source_record_id', 'canonical_listing_id'):
        UUID(fact[key])
    assert fact['source_record_id'] == examples['sanitized_snapshot']['source_record_id']
    assert fact['schema_version'] == 'ai-search.v1'
    assert fact['content_hash'] == hashlib.sha256(snapshot.encode()).hexdigest()
    assert datetime.fromisoformat(fact['observed_at']).tzinfo is not None
    for span in fact['evidence']:
        assert snapshot[span['start']:span['end']] == span['quote']
    if fact['key'] == 'capacity_total':
        assert fact['status'] == 'explicit_allow'
        assert fact['typed_value'] == {'kind': 'quantity', 'value': 3, 'unit': 'persons'}
    if fact['key'] == 'pets':
        assert fact['status'] == 'conditional'
        assert fact['qualifiers']['approval_required'] is True

intent = copy.deepcopy(examples['intent'])
UUID(intent['session_id'])
for example in examples['patch_sequence']:
    patch = example['patch']
    assert patch['session_id'] == intent['session_id']
    assert patch['expected_version'] == intent['version']
    assert set(patch['set']).isdisjoint(patch['remove'])
    assert len(patch['remove']) == len(set(patch['remove']))
    before = copy.deepcopy(intent['criteria'])
    for key in patch['remove']:
        intent['criteria'].pop(key, None)
    intent['criteria'].update(patch['set'])
    intent['version'] += 1
    assert intent['version'] == example['expected_version']
    for key in example['preserved']:
        assert intent['criteria'][key] == before[key]
assert 'balcony' not in intent['criteria']
assert Decimal(intent['criteria']['budget']['value']['amount']) == Decimal('700.00')
assert intent['criteria']['geography']['value']['municipality_code'] == '38001'
assert intent['criteria']['pets'] == examples['intent']['criteria']['pets']
municipalities = read_json(root / 'backend/app/data/spain-municipalities.json')['municipalities']
assert municipalities['38001'] == 'Adeje' and municipalities['38006'] == 'Arona'

madrid = ZoneInfo('Europe/Madrid')
for example in scenarios['madrid_days']:
    day = date.fromisoformat(example['date'])
    start = datetime.combine(day, time.min, madrid).astimezone(UTC)
    end = datetime.combine(day + timedelta(days=1), time.min, madrid).astimezone(UTC)
    assert start.isoformat() == example['start_utc']
    assert end.isoformat() == example['next_reset_utc']
    assert (end - start).total_seconds() / 3600 == example['hours']
    assert (end - timedelta(microseconds=1)).astimezone(madrid).date() == day
    assert end.astimezone(madrid).date() == day + timedelta(days=1)

links = 0
for path in [root / 'docs/index.md', *folder.rglob('*.md')]:
    for target in re.findall(r'\]\(([^)]+)\)', path.read_text(encoding='utf-8')):
        if '://' in target or target.startswith('#'):
            continue
        target_path = target.split('#', 1)[0]
        assert (path.parent / target_path).resolve().exists(), (path, target)
        links += 1
print('PASS: JSON, evidence/hash/UUID, 3 patch examples, INE geography, 3 Madrid days, local links')
print('Scenario inventory (NOT executed business tests):', dict(Counter(c['area'] for c in cases)))
print('Local links checked:', links)
```

Дополнительно: `git diff --check` и staged path scope — только `docs/`. Полный backend/frontend/PostGIS/Playwright suite не запускался: application code не менялся. Примеры не подтверждают отсутствие runtime регрессий и не заменяют final-SHA проверки будущих кодовых PR.

## Ограничения и rollback

Нет production DB access, реальных coverage/source-health процентов, измерения 10s, тестирования внешних accounts/retention. Providers, crawling, миграции, merge, deploy не выполнялись. Rollback: revert docs PR; никаких DB/data/provider побочных эффектов. Контрактные предложения ожидают human review; AI-07/08 implementation следует после принятия общего vocabulary/DTO.
