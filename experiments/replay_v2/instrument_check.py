"""Instrument check for v2 tasks: baseline all-false, staged partials match, reference all-true.

For each stage: apply steps, then poll the property vector until it equals the expected
vector (or the stage timeout passes), then re-evaluate twice more to confirm it is stable.

Usage:
  python instrument_check.py [--task TASK_ID] [--scenario reference] [--timeout 150]
Writes out/instrument_check.json and prints a table.
"""

from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path

from labtool import Lab, load_task
from solutions_v2 import SCENARIOS

HERE = Path(__file__).resolve().parent
TASKS = HERE.parents[1] / "tasks" / "multi_turn_v2"
OUT = HERE / "out"


def fmt(vec: dict, props: list[str]) -> str:
    return "".join("T" if vec.get(p) else "." for p in props)


def check_fault(lab: Lab, timeout: float) -> bool:
    fv = lab.task.fault_verification or []
    if not fv:
        return True
    waited = lab.wait_for(lambda: all(lab.evaluate(fv).values()), timeout)
    return waited >= 0


def run_scenario(task_id: str, scenario: str, stage_timeout: float, settle: float) -> dict:
    task = load_task(TASKS / f"{task_id}.json")
    props = [p.id for p in task.intent.properties]
    stages = SCENARIOS[task_id][scenario]
    v1_props = load_task(TASKS.parent / "multi_turn" / f"{task_id}.json").intent.properties
    v1_ids = [p.id for p in v1_props]
    rows = []
    with Lab(task) as lab:
        for node, cmd, code, out in lab.preconfigure():
            if code != 0:
                print(f"      preconfig {node} exit {code}: {(out or '')[:400]}", flush=True)
        fault_ok = check_fault(lab, timeout=90)
        # Baseline must be judged on a settled network, not an empty one.
        time.sleep(settle)
        print(f"  [{task_id} / {scenario}] fault_verification={fault_ok}", flush=True)
        for i, stage in enumerate(stages):
            for node, cmd, code, out in lab.apply(stage["steps"]):
                if code != 0:
                    print(f"      apply {node} exit {code}: {(out or '')[:400]}", flush=True)
            expect = stage["expect"]
            last = {}

            witnesses = stage.get("witness", [])

            def witnessed() -> bool:
                return all(re.search(pat, lab.run(node, cmd)[0], re.M) for node, cmd, pat in witnesses)

            def matches():
                nonlocal last
                last = lab.evaluate()
                return last == expect and witnessed()

            waited = lab.wait_for(matches, stage_timeout, interval=5) if i else (0.0 if matches() else -1.0)
            stable = waited >= 0 and all(lab.evaluate() == expect for _ in range(2))
            v1 = lab.evaluate(v1_props)
            observations = {r.property_id: r.observation_raw for r in lab.evaluate_detail()}
            rows.append({
                "observations": observations,
                "stage": stage["name"], "expected": fmt(expect, props), "observed": fmt(last, props),
                "match": waited >= 0, "stable": stable, "seconds_to_match": round(waited, 1),
                "v1_observed": fmt(v1, v1_ids), "v1_completeness": round(sum(v1.values()) / len(v1), 3),
            })
            print(f"  [{task_id} / {scenario}] {stage['name'][:60]:60s} exp={fmt(expect, props)} "
                  f"obs={fmt(last, props)} {'OK' if stable else 'MISMATCH'} ({waited:.0f}s)  "
                  f"v1={fmt(v1, v1_ids)}", flush=True)
            if not (waited >= 0):
                for r in lab.evaluate_detail():
                    if r.satisfied != expect[r.property_id]:
                        print(f"      {r.property_id}: got {r.satisfied}; output:\n"
                              + "\n".join("        " + l for l in (r.observation_raw or "").splitlines()[:25]))
    return {"task_id": task_id, "scenario": scenario, "properties": props,
            "fault_verification_passed": fault_ok, "stages": rows,
            "passed": fault_ok and all(r["stable"] for r in rows)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task")
    ap.add_argument("--scenario")
    ap.add_argument("--timeout", type=float, default=150.0)
    ap.add_argument("--settle", type=float, default=50.0,
                    help="seconds to let the preconfigured baseline converge before judging it")
    ap.add_argument("--infra", choices=["netns", "containerlab"], default="netns")
    args = ap.parse_args()
    import labtool
    labtool.INFRA = args.infra
    OUT.mkdir(exist_ok=True)
    results = []
    for task_id, scen in SCENARIOS.items():
        if args.task and task_id != args.task:
            continue
        for name in scen:
            if args.scenario and name != args.scenario:
                continue
            settle = args.settle if load_task(TASKS / f"{task_id}.json").preconfiguration else 5.0
            results.append(run_scenario(task_id, name, args.timeout, settle))
    path = OUT / (f"instrument_check_{args.task}.json" if args.task else "instrument_check.json")
    path.write_text(json.dumps(results, indent=2))
    print("\nSUMMARY")
    for r in results:
        print(f"  {r['task_id']:36s} {r['scenario']:10s} fault_ok={r['fault_verification_passed']} "
              f"{'PASS' if r['passed'] else 'FAIL'}")


if __name__ == "__main__":
    main()
