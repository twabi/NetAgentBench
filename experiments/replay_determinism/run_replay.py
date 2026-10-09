"""Replay stored hat{A} traces through InteractiveSession.

Isolated experiment: does not modify src/, scripts/, or results/comparatives_all.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from parse_log import completeness_agrees, load_hat_a, original_completeness, original_satisfied

from benchmark.evaluator.property import PropertyEvaluator
from benchmark.models.task import TaskDefinition
from benchmark.scoring.metrics import ScoringCalculator
from benchmark.session.models import CommandType
from benchmark.session.session import InteractiveSession

logger = logging.getLogger("replay_determinism")


def load_json(path: Path) -> dict[str, Any]:
    with path.open() as handle:
        return json.load(handle)


def load_task(path: Path) -> TaskDefinition:
    return TaskDefinition(**load_json(path))


def pre_eval_wait_seconds(task: TaskDefinition) -> float:
    timeout = 10
    if task.convergence and task.convergence.timeout_seconds:
        timeout = int(task.convergence.timeout_seconds)
    return float(min(timeout, 30))


def replay_once(
    task: TaskDefinition,
    hat_a: list[tuple[str, str]],
    turn_limit: int,
    time_limit: float,
) -> dict[str, Any]:
    session = InteractiveSession(
        task=task,
        turn_limit=turn_limit,
        time_limit=time_limit,
        convergence_timeout=30,
        log_property_snapshots=False,
    )
    started = time.time()
    context = session.start()
    command_outcomes: list[dict[str, Any]] = []
    try:
        for node, command in hat_a:
            result = session.exec_command(node, command, CommandType.CONFIG)
            command_outcomes.append(
                {
                    "node": node,
                    "success": bool(result.success),
                    "exit_code": result.exit_code,
                }
            )
        session.submit()
        wait = pre_eval_wait_seconds(task)
        logger.info("Waiting %.0fs for convergence before evaluation", wait)
        time.sleep(wait)
        property_results = PropertyEvaluator().evaluate_all_properties(
            infrastructure=session.infrastructure,
            topology_id=context.topology_id,
            properties=task.intent.properties,
        )
        completeness = ScoringCalculator().compute_completeness(property_results)
        return {
            "completeness": completeness,
            "satisfied": sorted(p.property_id for p in property_results if p.satisfied),
            "n_commands": len(hat_a),
            "n_command_ok": sum(1 for row in command_outcomes if row["success"]),
            "elapsed_s": round(time.time() - started, 2),
            "command_outcomes": command_outcomes,
            "properties": [
                {"id": p.property_id, "satisfied": p.satisfied}
                for p in property_results
            ],
        }
    finally:
        session.teardown()


def summarize_trace(trace_id: str, original_c: float, original_sat: list[str], repeats: list[dict[str, Any]]) -> dict[str, Any]:
    ok = [row for row in repeats if "completeness" in row and "error" not in row]
    scores = [float(row["completeness"]) for row in ok]
    return {
        "id": trace_id,
        "original_completeness": original_c,
        "original_satisfied": original_sat,
        "n_repeats_ok": len(ok),
        "n_repeats_failed": len(repeats) - len(ok),
        "replay_completeness": scores,
        "agrees_with_original": completeness_agrees(original_c, scores) if scores else False,
        "replays_agree_with_each_other": (
            max(scores) - min(scores) <= 1e-9 if len(scores) >= 2 else False
        ),
        "repeats": repeats,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replay stored hat{A} traces")
    parser.add_argument("--repo", type=Path, default=REPO_ROOT)
    parser.add_argument("--traces", type=Path, default=HERE / "traces.json")
    parser.add_argument("--out", type=Path, default=HERE / "out" / "replay_results.json")
    parser.add_argument("--repeats", type=int, default=None)
    parser.add_argument("--only", type=str, default=None, help="Replay a single traces.json id")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--turn-limit", type=int, default=100)
    parser.add_argument("--time-limit", type=float, default=1800.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    repo = args.repo.resolve()
    spec = load_json(args.traces)
    repeats = args.repeats if args.repeats is not None else int(spec.get("repeats", 3))
    selected = spec["traces"]
    if args.only:
        selected = [row for row in selected if row["id"] == args.only]
        if not selected:
            logger.error("No trace id %s in %s", args.only, args.traces)
            return 2

    report: dict[str, Any] = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "repeats": repeats,
        "dry_run": bool(args.dry_run),
        "traces": [],
    }

    for trace in selected:
        run_path = repo / trace["run_json"]
        task_path = repo / trace["task_json"]
        result = load_json(run_path)
        hat_a = load_hat_a(result)
        original_c = original_completeness(result)
        original_sat = original_satisfied(result)
        logger.info(
            "Trace %s task=%s hatA=%d original_C=%s",
            trace["id"],
            trace["task_id"],
            len(hat_a),
            original_c,
        )
        if args.dry_run:
            report["traces"].append(
                {
                    "id": trace["id"],
                    "role": trace.get("role"),
                    "task_id": trace["task_id"],
                    "n_hat_a": len(hat_a),
                    "original_completeness": original_c,
                    "original_satisfied": original_sat,
                    "hat_a_preview": [
                        {"node": node, "command": command[:120]}
                        for node, command in hat_a[:3]
                    ],
                }
            )
            continue

        task = load_task(task_path)
        turn_limit = max(args.turn_limit, len(hat_a) + 10)
        repeat_rows: list[dict[str, Any]] = []
        for i in range(1, repeats + 1):
            logger.info("Replay %s repeat %d/%d", trace["id"], i, repeats)
            try:
                row = replay_once(
                    task=task,
                    hat_a=hat_a,
                    turn_limit=turn_limit,
                    time_limit=args.time_limit,
                )
                row["repeat"] = i
                logger.info(
                    "  C=%.4f satisfied=%s ok_cmds=%d/%d elapsed=%.1fs",
                    row["completeness"],
                    row["satisfied"],
                    row["n_command_ok"],
                    row["n_commands"],
                    row["elapsed_s"],
                )
            except Exception as exc:
                logger.exception("Replay %s repeat %d failed", trace["id"], i)
                row = {
                    "repeat": i,
                    "error": str(exc),
                    "traceback": traceback.format_exc(),
                }
            repeat_rows.append(row)

        summary = summarize_trace(trace["id"], float(original_c or 0.0), original_sat, repeat_rows)
        summary["role"] = trace.get("role")
        summary["task_id"] = trace["task_id"]
        summary["n_hat_a"] = len(hat_a)
        report["traces"].append(summary)

    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2))
    logger.info("Wrote %s", args.out)
    if not args.dry_run:
        print("REPLAY COMPLETE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
