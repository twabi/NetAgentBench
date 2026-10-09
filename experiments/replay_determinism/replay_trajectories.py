"""Replay stored hat{A} traces with per-turn property snapshots (RQ3 temporal).

Isolated experiment: does not modify src/, scripts/, or results/comparatives_all.

Enables ``log_property_snapshots`` so ``InteractiveSession`` records a
``passive_reveal`` snapshot after every config command, yielding a real
C(H_t) trajectory on live substrate state. Because complex traces do not
reproduce deterministically (convergence / epsilon-event variance), each run
is flagged ``stable`` only when the replayed terminal completeness reproduces
the originally logged completeness; downstream temporal claims are restricted
to that stable subset.

Cohort selection reuses the RQ2 single-agent selector so the 70-run cohort
matches the paper exactly.
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
RQ2_DIR = REPO_ROOT / "experiments" / "rq2_intent_resolution"
for _p in (HERE, RQ2_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from parse_log import load_hat_a, original_completeness, original_satisfied  # noqa: E402
from analyze import is_single_agent_run  # noqa: E402  (RQ2 cohort selector)
from wait_eval import (  # noqa: E402
    DEFAULT_INTERVAL_SECONDS,
    DEFAULT_MIN_WAIT_SECONDS,
    TOL,
    poll_until,
    pre_eval_wait_seconds,
)
from replay_policy import session_convergence_timeout, should_skip_existing  # noqa: E402

from benchmark.evaluator.property import PropertyEvaluator  # noqa: E402
from benchmark.models.task import TaskDefinition  # noqa: E402
from benchmark.scoring.metrics import ScoringCalculator  # noqa: E402
from benchmark.session.models import CommandType  # noqa: E402
from benchmark.session.session import InteractiveSession  # noqa: E402

logger = logging.getLogger("replay_trajectories")

RUNS_DIR = REPO_ROOT / "results" / "comparatives_all" / "runs"
TASKS_DIR = REPO_ROOT / "tasks" / "multi_turn"


def load_json(path: Path) -> dict[str, Any]:
    with path.open() as handle:
        return json.load(handle)


def load_task(task_id: str) -> TaskDefinition:
    return TaskDefinition(**load_json(TASKS_DIR / f"{task_id}.json"))


def discover_runs(
    only: Optional[str] = None,
    tasks: Optional[set[str]] = None,
    limit: Optional[int] = None,
) -> list[dict[str, Any]]:
    """Enumerate the single-agent cohort, matching the RQ2 selector."""
    rows: list[dict[str, Any]] = []
    for path in sorted(RUNS_DIR.glob("*/*.json")):
        data = load_json(path)
        if not is_single_agent_run(data):
            continue
        task_id = str(data.get("task_id") or path.parent.name)
        if tasks and task_id not in tasks:
            continue
        run_id = str(data.get("run_id") or path.stem)
        if only and run_id != only:
            continue
        rows.append(
            {"path": path, "run_id": run_id, "task_id": task_id, "data": data}
        )
    if limit is not None:
        rows = rows[:limit]
    return rows


def replay_one(
    task: TaskDefinition,
    hat_a: list[tuple[str, str]],
    turn_limit: int,
    time_limit: float,
    original_c: Optional[float] = None,
    min_wait: float = DEFAULT_MIN_WAIT_SECONDS,
    plateau_rounds: int = 3,
) -> dict[str, Any]:
    session = InteractiveSession(
        task=task,
        turn_limit=turn_limit,
        time_limit=time_limit,
        convergence_timeout=session_convergence_timeout(
            task.convergence.timeout_seconds if task.convergence else None,
            min_wait=min_wait,
        ),
        log_property_snapshots=True,
    )
    started = time.time()
    context = session.start()
    try:
        for node, command in hat_a:
            session.exec_command(node, command, CommandType.CONFIG)
        session.submit()
        timeout_s = (
            task.convergence.timeout_seconds if task.convergence else None
        )
        interval_s = (
            float(task.convergence.check_interval_seconds)
            if task.convergence and task.convergence.check_interval_seconds
            else DEFAULT_INTERVAL_SECONDS
        )
        max_wait = pre_eval_wait_seconds(timeout_s, min_wait=min_wait)
        logger.info(
            "Polling up to %.0fs (interval %.0fs) for terminal completeness",
            max_wait,
            interval_s,
        )
        holder: dict[str, Any] = {"results": None}

        def _evaluate() -> float:
            holder["results"] = PropertyEvaluator().evaluate_all_properties(
                infrastructure=session.infrastructure,
                topology_id=context.topology_id,
                properties=task.intent.properties,
            )
            score = ScoringCalculator().compute_completeness(holder["results"])
            logger.info("  C=%.4f", score)
            return score

        terminal_c, waited = poll_until(
            evaluate=_evaluate,
            target=original_c,
            max_wait=max_wait,
            interval=interval_s,
            plateau_rounds=plateau_rounds,
        )
        prop_results = holder["results"]
        return {
            "terminal_completeness": terminal_c,
            "terminal_satisfied": sorted(
                p.property_id for p in prop_results if p.satisfied
            ),
            "convergence_wait_s": round(waited, 2),
            # per-turn passive_reveal snapshots: {turn, kind, properties, completeness}
            "trajectory": list(context.property_trajectory),
            "n_commands": len(hat_a),
            "elapsed_s": round(time.time() - started, 2),
        }
    finally:
        session.teardown()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out-dir", type=Path, default=HERE / "out" / "trajectories"
    )
    parser.add_argument(
        "--summary",
        type=Path,
        default=HERE / "out" / "trajectory_replay_summary.json",
    )
    parser.add_argument("--only", type=str, default=None, help="Single run_id")
    parser.add_argument(
        "--tasks", type=str, default=None, help="Comma-separated task_ids"
    )
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--turn-limit", type=int, default=100)
    parser.add_argument("--time-limit", type=float, default=1800.0)
    parser.add_argument(
        "--min-wait",
        type=float,
        default=DEFAULT_MIN_WAIT_SECONDS,
        help="Floor for post-submit convergence wait (seconds)",
    )
    parser.add_argument(
        "--rerun-unstable",
        action="store_true",
        help="Re-execute saved replays that errored or did not match original completeness",
    )
    parser.add_argument(
        "--plateau-rounds",
        type=int,
        default=3,
        help="Stop polling after this many unchanged non-matching scores (0 disables)",
    )
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    task_filter = (
        {t.strip() for t in args.tasks.split(",") if t.strip()}
        if args.tasks
        else None
    )
    runs = discover_runs(only=args.only, tasks=task_filter, limit=args.limit)
    logger.info("Discovered %d single-agent runs to replay", len(runs))

    if args.dry_run:
        for row in runs:
            hat_a = load_hat_a(row["data"])
            logger.info(
                "  %s task=%s hatA=%d original_C=%s",
                row["run_id"],
                row["task_id"],
                len(hat_a),
                original_completeness(row["data"]),
            )
        return 0

    args.out_dir.mkdir(parents=True, exist_ok=True)
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    summary_rows: list[dict[str, Any]] = []

    def write_summary() -> None:
        existing_rows: list[dict[str, Any]] = []
        if args.summary.exists():
            try:
                previous = load_json(args.summary)
                existing_rows = list(previous.get("runs") or [])
            except json.JSONDecodeError:
                existing_rows = []
        by_id = {str(r.get("run_id")): r for r in existing_rows}
        for row in summary_rows:
            by_id[str(row["run_id"])] = row
        merged = list(by_id.values())
        n_ok = sum(1 for r in merged if "error" not in r)
        n_stable = sum(1 for r in merged if r.get("stable"))
        payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "n_runs": len(merged),
            "n_replayed_ok": n_ok,
            "n_stable": n_stable,
            "reproduction_rate": (n_stable / n_ok) if n_ok else 0.0,
            "runs": merged,
        }
        args.summary.write_text(json.dumps(payload, indent=2))

    for idx, row in enumerate(runs, start=1):
        out_path = args.out_dir / f"{row['run_id']}.json"
        if out_path.exists():
            existing = load_json(out_path)
            if should_skip_existing(existing, rerun_unstable=args.rerun_unstable):
                logger.info(
                    "[%d/%d] Skip %s (already replayed, stable=%s)",
                    idx,
                    len(runs),
                    row["run_id"],
                    existing.get("stable"),
                )
                summary_rows.append(
                    {k: v for k, v in existing.items() if k != "trajectory"}
                )
                write_summary()
                continue

        data = row["data"]
        hat_a = load_hat_a(data)
        original_c = original_completeness(data)
        task = load_task(row["task_id"])
        turn_limit = max(args.turn_limit, len(hat_a) + 10)
        logger.info(
            "[%d/%d] Replay %s task=%s hatA=%d original_C=%s",
            idx,
            len(runs),
            row["run_id"],
            row["task_id"],
            len(hat_a),
            original_c,
        )
        try:
            result = replay_one(
                task,
                hat_a,
                turn_limit,
                args.time_limit,
                original_c=original_c,
                min_wait=args.min_wait,
                plateau_rounds=args.plateau_rounds,
            )
            terminal_c = float(result["terminal_completeness"])
            stable = (
                original_c is not None
                and abs(terminal_c - float(original_c)) <= TOL
            )
            record = {
                "run_id": row["run_id"],
                "task_id": row["task_id"],
                "original_completeness": original_c,
                "original_satisfied": original_satisfied(data),
                "replay_terminal_completeness": terminal_c,
                "replay_terminal_satisfied": result["terminal_satisfied"],
                "stable": bool(stable),
                "convergence_wait_s": result["convergence_wait_s"],
                "n_commands": result["n_commands"],
                "elapsed_s": result["elapsed_s"],
                "trajectory": result["trajectory"],
            }
            logger.info(
                "  -> replay_C=%.4f original_C=%s stable=%s wait=%.0fs snapshots=%d",
                terminal_c,
                original_c,
                stable,
                result["convergence_wait_s"],
                len(result["trajectory"]),
            )
        except Exception as exc:  # noqa: BLE001 - record and continue batch
            logger.exception("Replay failed for %s", row["run_id"])
            record = {
                "run_id": row["run_id"],
                "task_id": row["task_id"],
                "original_completeness": original_c,
                "error": str(exc),
                "traceback": traceback.format_exc(),
                "stable": False,
            }

        out_path.write_text(json.dumps(record, indent=2))
        summary_rows.append(
            {k: v for k, v in record.items() if k != "trajectory"}
        )
        write_summary()

    n_ok = sum(1 for r in summary_rows if "error" not in r)
    n_stable = sum(1 for r in summary_rows if r.get("stable"))
    logger.info(
        "Wrote %s (%d runs, %d stable / %d ok)",
        args.summary,
        len(summary_rows),
        n_stable,
        n_ok,
    )
    print("TRAJECTORY REPLAY COMPLETE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
