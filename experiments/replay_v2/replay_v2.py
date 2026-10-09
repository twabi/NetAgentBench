"""Replay-vs-replay determinism with corrected (v2) properties and a fixed wait.

What changed from experiments/replay_determinism/replay_trajectories.py:
  * No target-seeking. The old script polled until the score equalled the ORIGINAL
    logged score and stopped there. Here every replay waits the same fixed time
    (the task's declared convergence budget by default) and evaluates once.
  * Replays are compared with each other, not with the original live run, because the
    evaluator (the property set) has changed. Each logged command sequence is replayed
    N times on fresh topologies; a run is "stable" if all N terminal property VECTORS
    are identical (stricter than equal completeness).
  * The original (v1) properties are also evaluated on the same terminal state, so the
    old and new scores for the same final network can be compared directly.
  * Runs with no logged configuration commands (e.g. agent-server timeouts) are listed
    as skipped with their termination reason, not scored.

Only tasks whose topology and description are unchanged in v2 can be replayed
(RIP and BGP dual-homing). The OSPF v2 tasks need new agent runs.

Usage (on the benchmark server, real substrate):
  poetry run python experiments/replay_v2/replay_v2.py --repeats 3
Usage (network-namespace lab, no Docker Hub needed):
  python experiments/replay_v2/replay_v2.py --infra netns --repeats 3
"""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
for p in (HERE, REPO / "src", REPO / "experiments" / "replay_determinism",
          REPO / "experiments" / "rq2_intent_resolution"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from parse_log import load_full_sequence, original_completeness  # noqa: E402
from analyze import is_single_agent_run  # noqa: E402

from benchmark.evaluator.property import PropertyEvaluator  # noqa: E402
from benchmark.models.task import TaskDefinition  # noqa: E402
from benchmark.session.models import CommandType  # noqa: E402
from benchmark.session.session import InteractiveSession  # noqa: E402

logger = logging.getLogger("replay_v2")

RUNS_DIR = REPO / "results" / "comparatives_all" / "runs"
V1_DIR = REPO / "tasks" / "multi_turn"
V2_DIR = REPO / "tasks" / "multi_turn_v2"
# Historical logs match v2 topology only for RIP and BGP dual-homing.
# The sweep directory also contains the three tasks whose topology or checks changed.
HISTORICAL = ("ccna_rip_routing_basic", "ccie_bgp_dual_homing_expert")
REPLAYABLE = HISTORICAL + (
    "troubleshoot_ospf_adjacency_issue",
    "ccnp_multiarea_ospf_intermediate",
    "troubleshoot_bgp_route_filtering",
)


def load_task(path: Path) -> TaskDefinition:
    return TaskDefinition(**json.loads(path.read_text()))


def discover(runs_dir: Path, tasks: set[str], only: Optional[str]) -> list[dict[str, Any]]:
    rows = []
    for path in sorted(runs_dir.glob("*/*.json")):
        data = json.loads(path.read_text())
        if not is_single_agent_run(data):
            continue
        task_id = str(data.get("task_id") or path.parent.name)
        if task_id not in tasks:
            continue
        run_id = str(data.get("run_id") or path.stem)
        if only and run_id != only:
            continue
        rows.append({"run_id": run_id, "task_id": task_id, "data": data})
    return rows


def vec(results) -> dict[str, bool]:
    return {r.property_id: bool(r.satisfied) for r in results}


def completeness(v: dict[str, bool]) -> float:
    return sum(v.values()) / len(v) if v else 0.0


def original_v2_vector(data: dict[str, Any]) -> dict[str, bool]:
    """Terminal property vector recorded on the live session."""
    return {
        str(p["property_id"]): bool(p.get("satisfied"))
        for p in (data.get("property_results") or [])
        if p.get("property_id")
    }


def _vector_key(vector: Optional[dict[str, bool]]) -> Optional[str]:
    if not isinstance(vector, dict):
        return None
    return json.dumps(vector, sort_keys=True)


def summarize_replays(
    replays: list[dict[str, Any]],
    repeats: int,
    original_vector: dict[str, bool],
) -> dict[str, Any]:
    """Stability of the v2 vector, and whether that stable vector is the live one.

    A replay that stored a v2 vector counts even when the v1 checker raised.
    """
    ok = [rp for rp in replays if "error" not in rp and isinstance(rp.get("v2_vector"), dict)]
    v2s = [_vector_key(rp["v2_vector"]) for rp in ok]
    v1s = [_vector_key(rp.get("v1_vector")) for rp in ok]
    v1s = [key for key in v1s if key is not None]
    stable_v2 = len(ok) == repeats and len(set(v2s)) == 1
    stable_vector = ok[0]["v2_vector"] if stable_v2 else None
    return {
        "n_replays_ok": len(ok),
        "stable_v2_vector": stable_v2,
        "stable_v1_vector": len(v1s) == repeats and len(set(v1s)) == 1,
        "matches_original_v2": stable_v2 and _vector_key(stable_vector) == _vector_key(original_vector),
        "v2_completeness": [rp.get("v2_completeness") for rp in ok],
        "v1_completeness": [rp.get("v1_completeness") for rp in ok],
        "v2_vector": stable_vector if stable_v2 else (ok[0]["v2_vector"] if ok else None),
        "original_v2_vector": original_vector,
    }


def score_terminal(evaluator, infrastructure, topology_id, task_v2, task_v1) -> dict[str, Any]:
    """Score v2 first. A v1 checker error is recorded and does not drop v2."""
    v2 = vec(evaluator.evaluate_all_properties(
        infrastructure, topology_id, task_v2.intent.properties))
    record: dict[str, Any] = {
        "v2_vector": v2,
        "v2_completeness": completeness(v2),
        "v1_vector": None,
        "v1_completeness": None,
    }
    try:
        v1 = vec(evaluator.evaluate_all_properties(
            infrastructure, topology_id, task_v1.intent.properties))
    except Exception as exc:  # noqa: BLE001
        record["v1_error"] = str(exc)
        return record
    record["v1_vector"] = v1
    record["v1_completeness"] = completeness(v1)
    return record


def replay_once(task_v2: TaskDefinition, task_v1: TaskDefinition, hat_a, wait_s: float,
                infrastructure=None) -> dict[str, Any]:
    session = InteractiveSession(
        task=task_v2,
        infrastructure=infrastructure,
        turn_limit=max(100, len(hat_a) + 10),
        time_limit=3600.0,
        convergence_timeout=int(task_v2.convergence.timeout_seconds),
        log_property_snapshots=True,
    )
    started = time.time()
    ctx = session.start()
    try:
        exec_log = []
        for node, command in hat_a:
            t0 = round(time.time() - started, 2)
            res = session.exec_command(node, command, CommandType.CONFIG)
            exec_log.append({
                "node": node, "exit_code": res.exit_code, "success": res.success,
                "t_start_s": t0, "execution_time_s": round(res.execution_time or 0.0, 2),
                "stdout": (res.stdout or "")[:OUTPUT_CAP], "stderr": (res.stderr or "")[:OUTPUT_CAP],
            })
        session.submit()
        time.sleep(wait_s)  # fixed, identical for every replay; no early stop
        scored = score_terminal(
            PropertyEvaluator(), session.infrastructure, ctx.topology_id, task_v2, task_v1)
        return {
            **scored,
            "trajectory": list(ctx.property_trajectory),
            "command_results": exec_log,
            "elapsed_s": round(time.time() - started, 1),
            "container_logs": container_logs(ctx.topology_id) if infrastructure is None else None,
        }
    finally:
        session.teardown()


OUTPUT_CAP = 2000  # chars of stdout/stderr kept per replayed command
LOG_TAIL = 300  # lines of `docker logs` kept per container


def container_logs(topology_id: str) -> dict[str, str]:
    """Tail of each lab container's log, captured before teardown (diagnostics only)."""
    try:
        names = subprocess.run(
            ["docker", "ps", "-a", "--filter", f"name=clab-{topology_id}-", "--format", "{{.Names}}"],
            capture_output=True, text=True, timeout=30).stdout.split()
        logs = {}
        for name in names:
            out = subprocess.run(["docker", "logs", "--timestamps", "--tail", str(LOG_TAIL), name],
                                 capture_output=True, text=True, timeout=30)
            logs[name] = out.stdout + out.stderr
        return logs
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--runs-dir", type=Path, default=RUNS_DIR)
    ap.add_argument("--out-dir", type=Path, default=HERE / "out" / "replay_v2")
    ap.add_argument("--tasks", default=",".join(HISTORICAL))
    ap.add_argument("--only", default=None, help="single run_id")
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--wait", type=float, default=None,
                    help="fixed post-submit wait in seconds (default: task convergence.timeout_seconds)")
    ap.add_argument("--infra", choices=["containerlab", "netns"], default="containerlab")
    ap.add_argument("--resume", action="store_true", help="skip runs that already have a result file")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    for noisy in ("benchmark", "httpx"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    infrastructure = None
    if args.infra == "netns":
        from netns_lab import NetnsProvider, patch_command_executor
        infrastructure = NetnsProvider()
        patch_command_executor(infrastructure)

    tasks = {t.strip() for t in args.tasks.split(",") if t.strip()}
    bad = tasks - set(REPLAYABLE)
    if bad:
        raise SystemExit(f"not replayable under v2 (topology changed): {sorted(bad)}")
    rows = discover(args.runs_dir, tasks, args.only)
    logger.info("Discovered %d single-agent runs", len(rows))
    args.out_dir.mkdir(parents=True, exist_ok=True)

    summary = []
    for i, row in enumerate(rows, 1):
        out = args.out_dir / f"{row['run_id']}.json"
        if args.resume and out.exists():
            summary.append({k: v for k, v in json.loads(out.read_text()).items() if k != "replays"})
            continue
        data = row["data"]
        hat_a = load_full_sequence(data)
        task_v1 = load_task(V1_DIR / f"{row['task_id']}.json")
        task_v2 = load_task(V2_DIR / f"{row['task_id']}.json")
        wait_s = float(args.wait if args.wait is not None else task_v2.convergence.timeout_seconds)
        original_vector = original_v2_vector(data)
        base = {
            "run_id": row["run_id"], "task_id": row["task_id"], "n_commands": len(hat_a),
            "original_v1_completeness": original_completeness(data),
            "original_v2_vector": original_vector,
            "termination_reason": (data.get("metrics") or {}).get("termination_reason"),
            "wait_s": wait_s, "infra": args.infra,
        }
        if not hat_a:
            rec = {**base, "skipped": "no logged commands"}
            logger.info("[%d/%d] %s skipped (%s)", i, len(rows), row["run_id"], base["termination_reason"])
        else:
            replays = []
            for r in range(args.repeats):
                try:
                    replays.append(replay_once(task_v2, task_v1, hat_a, wait_s, infrastructure))
                except Exception as exc:  # noqa: BLE001
                    replays.append({"error": str(exc), "traceback": traceback.format_exc()})
                rp = replays[-1]
                logger.info("[%d/%d] %s rep %d/%d: v2=%s v1=%s", i, len(rows), row["run_id"], r + 1,
                            args.repeats, rp.get("v2_completeness", "ERR"), rp.get("v1_completeness", "ERR"))
            rec = {
                **base,
                **summarize_replays(replays, args.repeats, original_vector),
                "replays": replays,
            }
        out.write_text(json.dumps(rec, indent=2))
        summary.append({k: v for k, v in rec.items() if k != "replays"})

    scored = [s for s in summary if "skipped" not in s]
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repeats": args.repeats, "infra": args.infra,
        "n_runs": len(summary), "n_scored": len(scored),
        "n_skipped": len(summary) - len(scored),
        "n_stable_v2_vector": sum(1 for s in scored if s.get("stable_v2_vector")),
        "n_matches_original_v2": sum(1 for s in scored if s.get("matches_original_v2")),
        "runs": summary,
    }
    (args.out_dir / "summary.json").write_text(json.dumps(payload, indent=2))
    logger.info(
        "stable v2 vector: %d / %d scored; matches original: %d; %d skipped",
        payload["n_stable_v2_vector"], len(scored),
        payload["n_matches_original_v2"], payload["n_skipped"],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
