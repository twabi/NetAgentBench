"""Temporal analysis of replayed property trajectories (RQ3).

Consumes the per-run trajectory JSONs written by ``replay_trajectories.py`` and
computes two families of measurement, restricted to the stable subset (runs
whose replayed terminal completeness reproduced the originally logged score):

  Angle B (non-monotonicity): per-run peak vs terminal completeness, completeness
  drops, and property-level regressions (a property that is satisfied at some
  turn and unsatisfied later). Terminal-only scoring cannot see these.

  Angle C (temporal necessity): reusing the declared per-task PREREQUISITES,
  whether an upstream property is first satisfied no later than its downstream
  (in turn order), and whether any snapshot ever shows downstream true while
  upstream is false.

Outputs CSVs + a headline JSON under ``out/``.
"""

from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Optional

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
RQ2_DIR = REPO_ROOT / "experiments" / "rq2_intent_resolution"
for _p in (RQ2_DIR,):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from analyze import PREREQUISITES  # noqa: E402  (declared necessity relations)

TRAJ_DIR = HERE / "out" / "trajectories"
OUT_DIR = HERE / "out"
MIN_TURNS = 2  # runs need >=2 snapshots to have a temporal story


def load_trajectories() -> list[dict[str, Any]]:
    runs: list[dict[str, Any]] = []
    for path in sorted(TRAJ_DIR.glob("*.json")):
        data = json.load(path.open())
        if "error" in data:
            continue
        runs.append(data)
    return runs


def snapshots(run: dict[str, Any]) -> list[dict[str, Any]]:
    traj = [s for s in run.get("trajectory", []) if s.get("kind") == "passive_reveal"]
    return sorted(traj, key=lambda s: s.get("turn", 0))


def first_true_turn(snaps: list[dict[str, Any]], pid: str) -> Optional[int]:
    for s in snaps:
        if s.get("properties", {}).get(pid):
            return s.get("turn")
    return None


def monotonicity_row(run: dict[str, Any]) -> Optional[dict[str, Any]]:
    snaps = snapshots(run)
    if len(snaps) < MIN_TURNS:
        return None
    comp = [float(s.get("completeness", 0.0)) for s in snaps]
    peak = max(comp)
    terminal = comp[-1]
    drops = sum(1 for a, b in zip(comp, comp[1:]) if b < a - 1e-9)
    # property-level regressions: true at turn t, false at some later turn
    prop_ids = list(snaps[-1].get("properties", {}).keys())
    regressions = 0
    regressed_props: list[str] = []
    for pid in prop_ids:
        series = [bool(s.get("properties", {}).get(pid)) for s in snaps]
        # count true->false transitions
        flips = sum(1 for a, b in zip(series, series[1:]) if a and not b)
        if flips:
            regressions += flips
            regressed_props.append(pid)
    return {
        "run_id": run["run_id"],
        "task_id": run["task_id"],
        "n_snapshots": len(snaps),
        "start_completeness": comp[0],
        "peak_completeness": peak,
        "terminal_completeness": terminal,
        "peak_gt_terminal": peak > terminal + 1e-9,
        "completeness_drops": drops,
        "property_regressions": regressions,
        "regressed_props": ";".join(regressed_props),
        "non_monotonic": bool(drops or regressions),
    }


def temporal_necessity_rows(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_task: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for run in runs:
        by_task[run["task_id"]].append(run)
    rows: list[dict[str, Any]] = []
    for task_id, edges in PREREQUISITES.items():
        task_runs = by_task.get(task_id, [])
        for up, down in edges:
            n_both = 0
            up_before_down = 0
            simultaneous = 0
            snapshot_violations = 0  # down true while up false, any snapshot
            runs_with_violation = 0
            for run in task_runs:
                snaps = snapshots(run)
                if not snaps:
                    continue
                # snapshot-level: down true & up false
                viol = sum(
                    1
                    for s in snaps
                    if s.get("properties", {}).get(down)
                    and not s.get("properties", {}).get(up)
                )
                snapshot_violations += viol
                runs_with_violation += int(viol > 0)
                tu = first_true_turn(snaps, up)
                td = first_true_turn(snaps, down)
                if tu is not None and td is not None:
                    n_both += 1
                    if tu < td:
                        up_before_down += 1
                    elif tu == td:
                        simultaneous += 1
            rows.append(
                {
                    "task_id": task_id,
                    "upstream": up,
                    "downstream": down,
                    "n_runs": len(task_runs),
                    "n_both_satisfied": n_both,
                    "up_before_down": up_before_down,
                    "up_simultaneous_down": simultaneous,
                    "up_after_down": n_both - up_before_down - simultaneous,
                    "runs_with_snapshot_violation": runs_with_violation,
                    "snapshot_violations": snapshot_violations,
                }
            )
    return rows


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def main() -> None:
    all_runs = load_trajectories()
    stable = [r for r in all_runs if r.get("stable")]

    mono_all = [row for r in stable if (row := monotonicity_row(r))]
    write_csv(
        OUT_DIR / "monotonicity_stable.csv",
        mono_all,
        [
            "run_id",
            "task_id",
            "n_snapshots",
            "start_completeness",
            "peak_completeness",
            "terminal_completeness",
            "peak_gt_terminal",
            "completeness_drops",
            "property_regressions",
            "regressed_props",
            "non_monotonic",
        ],
    )

    necessity = temporal_necessity_rows(stable)
    write_csv(
        OUT_DIR / "temporal_necessity_stable.csv",
        necessity,
        [
            "task_id",
            "upstream",
            "downstream",
            "n_runs",
            "n_both_satisfied",
            "up_before_down",
            "up_simultaneous_down",
            "up_after_down",
            "runs_with_snapshot_violation",
            "snapshot_violations",
        ],
    )

    n_nonmono = sum(1 for r in mono_all if r["non_monotonic"])
    n_peak_gt = sum(1 for r in mono_all if r["peak_gt_terminal"])
    total_edges = len(necessity)
    edges_clean = sum(
        1 for r in necessity if r["up_after_down"] == 0 and r["snapshot_violations"] == 0
    )
    both_edges = sum(r["n_both_satisfied"] for r in necessity)
    up_before = sum(r["up_before_down"] for r in necessity)
    up_simul = sum(r["up_simultaneous_down"] for r in necessity)
    up_after = sum(r["up_after_down"] for r in necessity)

    headline = {
        "n_trajectories_ok": len(all_runs),
        "n_stable": len(stable),
        "n_stable_with_temporal": len(mono_all),
        "non_monotonic_runs": n_nonmono,
        "peak_gt_terminal_runs": n_peak_gt,
        "temporal_necessity_edges": total_edges,
        "edges_no_ordering_or_snapshot_violation": edges_clean,
        "pairs_both_satisfied": both_edges,
        "up_before_down": up_before,
        "up_simultaneous_down": up_simul,
        "up_after_down": up_after,
    }
    (OUT_DIR / "rq3_headline.json").write_text(json.dumps(headline, indent=2))
    print(json.dumps(headline, indent=2))

    print("\n== non-monotonic stable runs (n_commands>=2) ==")
    for r in mono_all:
        if r["non_monotonic"]:
            print(
                f"  {r['task_id']:34s} {r['run_id'][:52]:52s} "
                f"peak={r['peak_completeness']:.2f} term={r['terminal_completeness']:.2f} "
                f"drops={r['completeness_drops']} regs={r['property_regressions']} "
                f"[{r['regressed_props']}]"
            )

    print("\n== temporal necessity (stable) ==")
    for r in necessity:
        print(
            f"  {r['task_id'][:24]:24s} {r['upstream'][:22]:22s} -> {r['downstream'][:22]:22s} "
            f"both={r['n_both_satisfied']:2d} up<down={r['up_before_down']:2d} "
            f"up=down={r['up_simultaneous_down']:2d} up>down={r['up_after_down']:2d} "
            f"snap_viol={r['snapshot_violations']:2d}"
        )


if __name__ == "__main__":
    main()
