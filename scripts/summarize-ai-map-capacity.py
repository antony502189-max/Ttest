"""Summarize retained attempts without turning errors into latency successes."""
from __future__ import annotations

import argparse
import ast
import json
import math
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path


def percentile(values, q):
    ordered=sorted(values)
    return ordered[min(len(ordered)-1,math.ceil(q*len(ordered))-1)] if ordered else None


def summarize(root):
    result={"scales":[],"latency_note":"Completion/error durations include pool waiting. Error-containing scenarios fail; censored SQL samples are not successful query latencies."}
    resource_samples=[]
    resources=root/"resources.jsonl"
    if resources.exists():
        resource_samples=[json.loads(line.lstrip("\ufeff")) for line in resources.read_text(encoding="utf-8").splitlines() if line.strip()]
    completions={}
    progress=root/"progress.jsonl"
    if progress.exists():
        for line in progress.read_text(encoding="utf-8").splitlines():
            item=json.loads(line)
            if item["kind"]=="load":
                completions[(item["total"],item["candidates"],item["zoom"],item["concurrency"])]=datetime.fromisoformat(item["at"])
    for size in (100000,500000,1000000):
        dataset_path=root/f"dataset-{size}.json"
        if not dataset_path.exists():
            continue
        dataset=json.loads(dataset_path.read_text(encoding="utf-8"))
        dataset["settings"]=[ast.literal_eval(v) if isinstance(v,str) else v for v in dataset["settings"]]
        data={"dataset":dataset,"baseline":[],"load":[],"completed":(root/f"cancellation-{size}.json").exists()}
        path=root/f"baseline-{size}.json"
        if path.exists():
            data["baseline"]=json.loads(path.read_text(encoding="utf-8"))
        path=root/f"load-{size}.json"
        if path.exists():
            for case in json.loads(path.read_text(encoding="utf-8")):
                attempts=case["results"]
                successful=[r["ms"] for r in attempts if r["ok"]]
                errors=Counter(r.get("sqlstate") or r.get("error") for r in attempts if not r["ok"])
                summary={k:v for k,v in case.items() if k!="results"}
                summary.update(error_kinds=dict(errors),successful_p95_ms=percentile(successful,.95),
                    successful_p99_ms=percentile(successful,.99),
                    pool_p95_ms=percentile([r["pool_ms"] for r in attempts if "pool_ms" in r],.95))
                end=completions.get((size,case["candidates"],case["zoom"],case["concurrency"]))
                if end:
                    window=[s for s in resource_samples if end-timedelta(seconds=case["seconds"])<=datetime.fromisoformat(s["at"])<=end]
                    summary["resource_samples"]=len(window)
                    if window:
                        summary["peak_db_cpu_percent"]=max(float(s["db"]["CPUPerc"].rstrip("%")) for s in window)
                        summary["peak_db_memory_percent_of_8GiB"]=max(float(s["db"]["MemPerc"].rstrip("%")) for s in window)
                data["load"].append(summary)
        path=root/f"cancellation-{size}.json"
        if path.exists():
            data["cancellation"]=json.loads(path.read_text(encoding="utf-8"))
        result["scales"].append(data)
    if resource_samples:
        samples=resource_samples
        result["resources"]={"samples":len(samples),"peak_db_cpu_percent":max(float(s["db"]["CPUPerc"].rstrip("%")) for s in samples),
            "peak_db_memory_percent_of_8GiB":max(float(s["db"]["MemPerc"].rstrip("%")) for s in samples),
            "first":samples[0],"last":samples[-1]}
    plans=[]
    for path in root.glob("plan-*.json"):
        content=json.loads(path.read_text(encoding="utf-8"))
        if isinstance(content,list):
            plan=content[0]
            plans.append({"file":path.name,"actual_execution_ms":plan.get("Execution Time"),
                "actual_planning_ms":plan.get("Planning Time"),
                "shared_hits":plan.get("Plan",{}).get("Shared Hit Blocks"),
                "shared_reads":plan.get("Plan",{}).get("Shared Read Blocks")})
        else:
            plans.append({"file":path.name,"analyze_error":content.get("analyze_error",content.get("error")),
                "has_estimated_plan":bool(content.get("estimated_plan_without_execution"))})
    result["plans"]=plans
    return result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("root",type=Path)
    args=parser.parse_args()
    result=summarize(args.root)
    (args.root/"summary.json").write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding="utf-8")
    control_description="Фактический контрольный план малого набора сохраняется отдельно от больших estimated-only планов."
    control_path=args.root/"plan-1000-300-z8-0.json"
    if control_path.exists():
        control=json.loads(control_path.read_text(encoding="utf-8"))
        if isinstance(control,list):
            def authorities(node):
                found=[node] if node.get("Relation Name")=="external_listing_sources" else []
                return found+[item for child in node.get("Plans",[]) for item in authorities(child)]
            nodes=authorities(control[0]["Plan"])
            if nodes:
                node=max(nodes,key=lambda n:n.get("Actual Loops",0))
                control_description=(f"В фактическом плане контрольного набора на 1000 объявлений и 300 кандидатов "
                    f"`{node.get('Index Name',node['Node Type'])}` просматривался {node.get('Actual Loops')} раз: "
                    f"по {node.get('Actual Rows')} строки результата и {node.get('Rows Removed by Filter')} отброшенных строк. "
                    f"Этот узел дал {node.get('Shared Hit Blocks')} shared-hit обращений, весь запрос — "
                    f"{control[0]['Plan'].get('Shared Hit Blocks')}. Execution Time: {control[0].get('Execution Time')} мс. "
                    "Это обращения к страницам в памяти, не число физических чтений с диска.")
    lines=["# R-01: синтетическая нагрузка AI-карты", "",
        "Критерии: p95 ≤ 500 мс, p99 ≤ 1000 мс; 50/100/200 одновременных запросов; 100 000/500 000/1 000 000 объявлений.", "",
        "**Статус:** " + ("все три основных масштаба завершены." if len(result["scales"])==3 and all(s["completed"] for s in result["scales"]) else "промежуточные результаты; не все масштабы завершены."), "",
        "**Решение по производительности:** " + ("критерии не выполнены." if any(not c["pass"] for s in result["scales"] for c in s["load"]) else "данных для решения пока недостаточно."), "",
        "## Что измерялось", "",
        "Настоящий repository-путь `_map_intent`: SQL, проверка proof и построение маркеров/кластеров. HTTP, авторизация сессии, TLS и внешний rate gate исключены. Рабочие базы и реальные провайдеры не использовались.", "",
        "10 синтетических провайдеров; на объявление — две записи источника, суммарно 20 типизированных наблюдений с evidence и 20 совместимых resolved features. Это не 20 фильтров и не 20 наблюдений на каждый из десяти источников. Данные минимальные, все активные и совместимые; география — плотная детерминированная сетка. Это стресс-профиль, а не распределение реального каталога.", "",
        "PostgreSQL 16.4 / PostGIS 3.4.3; DB: 8 CPU, 8 GiB RAM, shared_buffers 1 GiB, work_mem 4 MiB; driver: 2 CPU, 2 GiB. Пул — максимум 30 соединений, клиентских операций — 50/100/200. Полные версии, ограничения и хеши исходников сохранены в JSON.", "",
        "Тайм-аут SQL — 5 секунд (в приложении по умолчанию 60 секунд), ожидание пула — 30 секунд. Тайм-ауты означают провал, не успешный ответ за 5 секунд. Цифры ниже — время возврата результата **или ошибки**, включая очередь; при ошибках это не p95/p99 успешно выполненного SQL. Успешные p95/p99 отдельно сохранены в summary.json, при отсутствии успехов они null.", "",
        "## Масштабы", "", "| Объявлений | Записей источников | Наблюдений | Размер DB, GiB | Сценариев | Ошибок / попыток | Завершён |", "|---:|---:|---:|---:|---:|---:|:---:|"]
    for scale in result["scales"]:
        d=scale["dataset"]
        counts=d["counts_including_template"]
        lines.append(f"| {d['listings']:,} | {counts['external_listing_sources']-2:,} | {counts['ai_listing_facts']-20:,} | {d['size_bytes']/1024**3:.2f} | {len(scale['load'])} | {sum(c['failures'] for c in scale['load'])} / {sum(c['samples'] for c in scale['load'])} | {'да' if scale['completed'] else 'нет'} |")
    lines += ["", "Из количества строк вычтен один вынесенный за viewport шаблон (2 источника / 20 наблюдений); размер DB включает шаблон, индексы и все таблицы миграций.", "",
        "## Параллельная нагрузка", "",
        "Диапазоны ниже объединяют viewport на 300 / 10 000 / весь каталог и zoom 8/13; каждый отдельный сценарий сохранён в JSON. На 100 тысячах — 200 попыток на сценарий. На 500 тысячах и миллионе полностью неуспешная первая волна останавливает сценарий; фактическое число попыток сохранено. Это достаточное основание отклонить бюджет, но не оценка успешного p99 и не длительный soak-тест.", "",
        "| Каталог | Одновременно | Ошибок / попыток | p95 возврата результата/ошибки, с | p99 возврата результата/ошибки, с | p95 до SQL карты: pool + SET, с (макс.) |", "|---:|---:|---:|---:|---:|---:|"]
    for scale in result["scales"]:
        for concurrency in (50,100,200):
            cases=[c for c in scale["load"] if c["concurrency"]==concurrency]
            if not cases:
                continue
            p95=[c['p95_ms']/1000 for c in cases]
            p99=[c['p99_ms']/1000 for c in cases]
            pools=[c['pool_p95_ms']/1000 for c in cases if c['pool_p95_ms'] is not None]
            pool_label=f"{max(pools):.2f}" if pools else "нет данных"
            lines.append(f"| {scale['dataset']['listings']:,} | {concurrency} | {sum(c['failures'] for c in cases)} / {sum(c['samples'] for c in cases)} | {min(p95):.2f}–{max(p95):.2f} | {min(p99):.2f}–{max(p99):.2f} | {pool_label} |")
    lines += ["", "`pool_ms` включает получение соединения и round trip SET TRANSACTION; это не чистый таймер очереди. `query_ms` включает repository SQL/DTO и завершение ошибочной транзакции; серверное время отдельно видно только в фактическом EXPLAIN.", "", "## Узкие места и рекомендации", "",
        "1. **Выбор authority-источников масштабируется с общим каталогом.** " + control_description + " Рекомендуется индексируемое объединение ID текущих и ранее известных источников с сохранением remap/delete fail-closed семантики. Эквивалентный UNION используется только для подготовки fixture, равенство digest проверяется; приложение этим экспериментом не оптимизировано.", "",
        "2. **Повторная дорогая проверка.** На zoom ≥13 при более чем 300 совпадениях сначала выполняется probe на 301 строку, затем агрегат. В отдельных планах сам signature также вычисляется повторно при join. После изменения доступа к источникам проверить число фактических выполнений и возможность однократного вычисления на уже ограниченных кандидатах. Не переносить проверки после LIMIT/агрегации: это нарушит корректность и приватность.", "",
        "3. **Очередь тяжёлых запросов.** Лимит пула 30 не ограничивает число ожидающих клиентских операций. Нужен отдельный измеренный admission/concurrency budget для карты, своевременная отмена старого viewport и ограниченная очередь. Простое увеличение пула создаст больше конкурентной работы с тем же дорогим SQL. Быстрые отказы не должны считаться выполнением SLO успешного поиска.", "",
        "4. **После первого SQL-исправления повторить всю матрицу.** Широкие viewport всё равно пересчитывают proof для каждого кандидата. Если бюджет остаётся недостижим, рассмотреть атомарно инвалидируемые версии/проекции и агрегаты на пути записи; обязательны все изменения источников, canonical/room data, фактов, batch и remap/delete. Замена текущих проверок на TTL или доверие старому proof без такого контракта небезопасна.", "",
        "5. **Отдельный эффект подготовки:** per-row триггер версии каталога сериализует массовые вставки через одну строку. Для синтетического наполнения он временно отключался и восстанавливался в finally с продвижением версии. Измеритель отказывается работать с отключённым триггером. Это не изменение production и не измерение реального импортера.", "",
        "## Отмена запросов", "", "| Каталог | Отменено операций | Освобождение, мс | Активных SQL после отмены | Пул работает |", "|---:|---:|---:|---:|:---:|"]
    for scale in result["scales"]:
        if "cancellation" in scale:
            c=scale['cancellation']
            lines.append(f"| {scale['dataset']['listings']:,} | {c['tasks']} | {c['elapsed_ms']:.1f} | {c['remaining_active']} | {'да' if c['pool_reusable'] else 'нет'} |")
    lines += ["", "## Границы вывода", "",
        "Это closed-loop repository-тест в Docker/WSL на одной машине, не end-to-end HTTP-сертификация и не нагрузка production. Подготовка и VACUUM прогревают кэш: результаты не обозначаются OS-cold. На ошибочных/прерванных EXPLAIN сохранён явно estimated-only план, без выдуманного фактического времени. В каждом JSON указан точный source hash и версия зависимостей. 200 попыток дают лишь предварительный хвост; меньшая полностью неуспешная волна доказывает провал, но не точный p99 успешной работы.", "",
        "Исходные планы, попытки, счётчики, параметры DB, resource samples и проверки digest сохранены в evidence. Подробный воспроизводимый протокол: [MAP_CAPACITY_PROTOCOL.md](MAP_CAPACITY_PROTOCOL.md). R-01 остаётся блокирующим публичную активацию до исправления и повторного успешного измерения; отключённый фундамент может рассматриваться отдельно."]
    (args.root/"REPORT_RU.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    for scale in result["scales"]:
        print(json.dumps({"size":scale["dataset"]["listings"],"load_scenarios":len(scale["load"]),
            "completed":scale["completed"],"passes":sum(c["pass"] for c in scale["load"]),
            "failures":sum(c["failures"] for c in scale["load"]),
            "attempts":sum(c["samples"] for c in scale["load"])}))


if __name__=="__main__":
    main()
