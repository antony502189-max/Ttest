"""Summarize retained attempts without turning errors into latency successes."""
from __future__ import annotations

import argparse
import ast
import json
import math
from collections import Counter
from datetime import datetime, timedelta
from itertools import pairwise
from pathlib import Path


def percentile(values, q):
    ordered=sorted(values)
    return ordered[min(len(ordered)-1,math.ceil(q*len(ordered))-1)] if ordered else None


def normalize_dataset(dataset):
    size = dataset["listings"]
    counts = dataset["counts_including_template"]
    if type(size) is not int or size < 1:
        raise ValueError("invalid dataset size")
    # The original retained metadata predates the explicit profile fields.
    # Infer only from exact whole-dataset counts, never assume baseline.
    sources = dataset.get("source_records_per_listing")
    if sources is None:
        sources, remainder = divmod(counts["external_listing_sources"], size + 1)
        if remainder:
            raise ValueError("invalid dataset source counts")
    observations = dataset.get("observations_per_listing")
    if observations is None:
        observations, remainder = divmod(counts["ai_listing_facts"], size + 1)
        if remainder:
            raise ValueError("invalid dataset observation counts")
    if type(sources) is not int or sources not in {2, 10} or type(observations) is not int or observations != 20:
        raise ValueError("invalid dataset profile")
    for field, multiplier in (("external_listing_sources", sources), ("ai_listing_facts", observations)):
        if type(counts[field]) is not int or counts[field] != (size + 1) * multiplier:
            raise ValueError(f"invalid dataset count: {field}")
    dataset.update(source_records_per_listing=sources, observations_per_listing=observations)
    return dataset


def resource_series(root):
    samples, events, invalid = [], [], 0
    path = root / "resources.jsonl"
    for line in path.read_text(encoding="utf-8-sig").splitlines() if path.exists() else []:
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            timestamp = datetime.fromisoformat(row["at"])
            if timestamp.tzinfo is None:
                raise ValueError("missing timezone")
            if "db" in row:
                cpu = float(row["db"]["CPUPerc"].removesuffix("%"))
                memory = float(row["db"]["MemPerc"].removesuffix("%"))
                if not math.isfinite(cpu) or cpu < 0 or not math.isfinite(memory) or not 0 <= memory <= 100:
                    raise ValueError("invalid resource percentages")
                samples.append(row)
            else:
                events.append(row)
        except (ValueError, TypeError, KeyError, AttributeError):
            invalid += 1
    starts = [row for row in events if row.get("kind") == "monitor-start"]
    stops = [row for row in events if row.get("kind") == "monitor-stop"]
    errors = sum(row.get("kind") == "monitor-error" for row in events)
    interval = starts[-1].get("interval_seconds", 5) if starts else 5
    if not isinstance(interval, (float, int)) or not math.isfinite(interval) or interval <= 0:
        interval, invalid = 5, invalid + 1
    timeline = ([starts[0]] if starts else []) + samples + ([stops[-1]] if stops else [])
    durations = [(datetime.fromisoformat(b["at"]) - datetime.fromisoformat(a["at"])).total_seconds()
                 for a, b in pairwise(timeline)]
    gaps = sum(duration > 2.5 * interval for duration in durations)
    invalid += sum(duration < 0 for duration in durations)
    profiles = {row["profile"] for row in samples + events if row.get("profile")}
    containers = {row["container"] for row in samples + events if row.get("container")}
    status = ("degraded" if errors or invalid or gaps or len(profiles) > 1 or len(containers) > 1 or
              any(row.get("status") == "failed" for row in stops) else
              "missing" if not samples else "unknown" if not starts else
              "complete" if stops and stops[-1].get("status") == "stopped" else "degraded")
    return samples, {"status": status, "samples": len(samples), "errors": errors,
                     "invalid_records": invalid, "gaps": gaps, "profiles": sorted(profiles)}


def measurement_complete(size, cases, cancellation):
    expected = {(count, concurrency, zoom) for count in {min(300, size), min(10000, size), size}
                for concurrency in (50, 100, 200) for zoom in (8, 13)}
    found = set()
    for case in cases:
        key = (case["candidates"], case["concurrency"], case["zoom"])
        attempts = case["results"]
        requested = case.get("requested_samples", case["samples"])
        failed_wave = (size >= 500000 and case.get("stopped_after_failed_wave") is True and
                       len(attempts) >= min(case["concurrency"], requested) and all(not r["ok"] for r in attempts))
        if (key in found or case["total"] != size or not attempts or case["samples"] != len(attempts) or
                requested < 1 or len(attempts) > requested or (len(attempts) != requested and not failed_wave) or
                case["failures"] != sum(not r["ok"] for r in attempts)):
            return False
        found.add(key)
    return (found == expected and cancellation.get("remaining_active") == 0 and
            cancellation.get("pool_reusable") is True and cancellation.get("tasks", 0) > 0)


def summarize(root):
    result={"scales":[],"latency_note":"Completion/error durations include pool waiting. Error-containing scenarios fail; censored SQL samples are not successful query latencies."}
    resource_samples, result["monitoring"] = resource_series(root)
    result["warnings"] = []
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
        dataset=normalize_dataset(json.loads(dataset_path.read_text(encoding="utf-8")))
        if dataset["listings"] != size:
            raise ValueError("dataset size disagrees with filename")
        dataset["settings"]=[ast.literal_eval(v) if isinstance(v,str) else v for v in dataset["settings"]]
        data={"dataset":dataset,"baseline":[],"load":[],"completed":False}
        raw_cases = []
        path=root/f"baseline-{size}.json"
        if path.exists():
            data["baseline"]=json.loads(path.read_text(encoding="utf-8"))
        path=root/f"load-{size}.json"
        if path.exists():
            raw_cases = json.loads(path.read_text(encoding="utf-8"))
            for case in raw_cases:
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
        data["completed"] = measurement_complete(size, raw_cases, data.get("cancellation", {}))
        data["dataset_complete"] = True
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
    result["completed_scales"] = [scale["dataset"]["listings"] for scale in result["scales"] if scale["completed"]]
    stop_path = root / "experiment-stop.json"
    if stop_path.exists():
        result["termination"] = json.loads(stop_path.read_text(encoding="utf-8-sig"))
        declared = result["termination"].get("completed_scales")
        if declared is not None and declared != result["completed_scales"]:
            result["warnings"].append("Stop marker completed_scales disagree with validated measurement files")
    result["status"] = ("INCONSISTENT" if result["warnings"] else
                        "COMPLETE" if result["completed_scales"] == [100000, 500000, 1000000] else "INCOMPLETE")
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
        "**Статус:** " + result["status"] + "; завершённые измерения: " +
            (", ".join(f"{size:,}" for size in result["completed_scales"]) or "нет") + ".", "",
        "Остановка: " + str(result.get("termination", {}).get("reason", "не зарегистрирована")) + ".", "",
        "Диагностика: " + ("; ".join(result["warnings"]) or "противоречий stop-marker не найдено") + ".", "",
        "Мониторинг ресурсов: " + json.dumps(result["monitoring"], ensure_ascii=False) + ".", "",
        "**Версия:** точная ревизия и source hashes находятся в runner*.json; при отсутствии этих метаданных версия не установлена. Исторический архив 2026-10-28 относится к исходному OR SQL и не характеризует скорость исправленной версии.", "",
        "**Решение по производительности:** " + ("критерии не выполнены." if any(not c["pass"] for s in result["scales"] for c in s["load"]) else "данных для решения пока недостаточно."), "",
        "## Что измерялось", "",
        "Настоящий repository-путь `_map_intent`: SQL, проверка proof и построение маркеров/кластеров. HTTP, авторизация сессии, TLS и внешний rate gate исключены. Рабочие базы и реальные провайдеры не использовались.", "",
        "\n\n".join(f"Набор {scale['dataset']['listings']:,}: "
            f"{scale['dataset']['source_records_per_listing']} записей источника на объявление; "
            f"{scale['dataset']['observations_per_listing']} наблюдений суммарно, без умножения на число источников. "
            f"Профиль: {'fanout' if scale['dataset']['source_records_per_listing'] == 10 else 'baseline'}."
            for scale in result["scales"]) or "Наборы данных отсутствуют.", "",
        "Версии DB из dataset: " + "; ".join(f"{scale['dataset']['listings']:,}: {scale['dataset'].get('version', 'неизвестна')}; {scale['dataset'].get('postgis', 'неизвестна')}" for scale in result["scales"]) + ". Лимиты протокола: DB 8 CPU/8 GiB, driver 2 CPU/2 GiB, пул30; настройки DB сохранены в dataset JSON.", "",
        "Тайм-аут SQL — 5 секунд (в приложении по умолчанию 60 секунд), ожидание пула — 30 секунд. Тайм-ауты означают провал, не успешный ответ за 5 секунд. Цифры ниже — время возврата результата **или ошибки**, включая очередь; при ошибках это не p95/p99 успешно выполненного SQL. Успешные p95/p99 отдельно сохранены в summary.json, при отсутствии успехов они null.", "",
        "## Масштабы", "", "| Объявлений | Записей источников | Наблюдений | Размер DB, GiB | Сценариев | Ошибок / попыток | Завершён |", "|---:|---:|---:|---:|---:|---:|:---:|"]
    for scale in result["scales"]:
        d=scale["dataset"]
        counts=d["counts_including_template"]
        lines.append(f"| {d['listings']:,} | {counts['external_listing_sources']-d['source_records_per_listing']:,} | {counts['ai_listing_facts']-d['observations_per_listing']:,} | {d['size_bytes']/1024**3:.2f} | {len(scale['load'])} | {sum(c['failures'] for c in scale['load'])} / {sum(c['samples'] for c in scale['load'])} | {'да' if scale['completed'] else 'нет'} |")
    lines += ["", "\n\n".join(f"Набор {scale['dataset']['listings']:,}: вычтен один вынесенный за viewport шаблон "
            f"({scale['dataset']['source_records_per_listing']} источников / {scale['dataset']['observations_per_listing']} наблюдений)."
            for scale in result["scales"]), "Размер DB включает шаблон, индексы и все таблицы миграций.", "",
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
        "1. **Выбор authority-источников масштабировался с общим каталогом.** " + control_description + " После остановки нагрузки выбор ID текущих и ранее известных источников исправлен на индексируемый UNION с сохранением remap/delete fail-closed семантики. Сначала он использовался только для подготовки fixture; теперь внесён в приложение. Совместимость v2 digest и число посещённых источников проверяются отдельно небольшими регрессиями. Скорость под нагрузкой после изменения не измерялась.", "",
        "2. **Повторная дорогая проверка.** На zoom ≥13 при более чем 300 совпадениях сначала выполняется probe на 301 строку, затем агрегат. В отдельных планах сам signature также вычисляется повторно при join. После изменения доступа к источникам проверить число фактических выполнений и возможность однократного вычисления на уже ограниченных кандидатах. Не переносить проверки после LIMIT/агрегации: это нарушит корректность и приватность.", "",
        "3. **Очередь тяжёлых запросов.** Лимит пула 30 не ограничивает число ожидающих клиентских операций. Нужен отдельный измеренный admission/concurrency budget для карты, своевременная отмена старого viewport и ограниченная очередь. Простое увеличение пула создаст больше конкурентной работы с тем же дорогим SQL. Быстрые отказы не должны считаться выполнением SLO успешного поиска.", "",
        "4. **Повторные измерения — только после отдельного согласования с владельцем.** Широкие viewport всё равно пересчитывают proof для каждого кандидата. Если бюджет остаётся недостижим, рассмотреть атомарно инвалидируемые версии/проекции и агрегаты на пути записи; обязательны все изменения источников, canonical/room data, фактов, batch и remap/delete. Замена текущих проверок на TTL или доверие старому proof без такого контракта небезопасна.", "",
        "5. **Отдельный эффект подготовки:** per-row триггер версии каталога сериализует массовые вставки через одну строку. Для синтетического наполнения он временно отключался и восстанавливался в finally с продвижением версии. Измеритель отказывается работать с отключённым триггером. Это не изменение production и не измерение реального импортера.", "",
        "## Отмена запросов", "", "| Каталог | Отменено операций | Освобождение, мс | Активных SQL после отмены | Пул работает |", "|---:|---:|---:|---:|:---:|"]
    for scale in result["scales"]:
        if "cancellation" in scale:
            c=scale['cancellation']
            elapsed = f"{c['elapsed_ms']:.1f}" if isinstance(c.get('elapsed_ms'), (int, float)) else "нет данных"
            lines.append(f"| {scale['dataset']['listings']:,} | {c.get('tasks', 'нет данных')} | {elapsed} | {c.get('remaining_active', 'нет данных')} | {'да' if c.get('pool_reusable') is True else 'нет'} |")
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
