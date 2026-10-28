"""Summarize retained attempts without turning errors into latency successes."""
from __future__ import annotations

import argparse
import ast
import json
import math
from collections import Counter
from pathlib import Path


def percentile(values, q):
    ordered=sorted(values)
    return ordered[min(len(ordered)-1,math.ceil(q*len(ordered))-1)] if ordered else None


def summarize(root):
    result={"scales":[],"latency_note":"Completion/error durations include pool waiting. Error-containing scenarios fail; censored SQL samples are not successful query latencies."}
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
                data["load"].append(summary)
        path=root/f"cancellation-{size}.json"
        if path.exists():
            data["cancellation"]=json.loads(path.read_text(encoding="utf-8"))
        result["scales"].append(data)
    resources=root/"resources.jsonl"
    if resources.exists():
        samples=[json.loads(line.lstrip("\ufeff")) for line in resources.read_text(encoding="utf-8").splitlines() if line.strip()]
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
    for scale in result["scales"]:
        print(json.dumps({"size":scale["dataset"]["listings"],"load_scenarios":len(scale["load"]),
            "completed":scale["completed"],"passes":sum(c["pass"] for c in scale["load"]),
            "failures":sum(c["failures"] for c in scale["load"]),
            "attempts":sum(c["samples"] for c in scale["load"])}))


if __name__=="__main__":
    main()
