"""Summarize replay_v2 results: stability, old (v1) vs new (v2) scores, and property order.

Reads out/replay_v2/*.json and writes out/replay_v2_report.md and out/replay_v2_runs.csv.
"""

from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
IN = HERE / "out" / "replay_v2"
OUT_MD = HERE / "out" / "replay_v2_report.md"
OUT_CSV = HERE / "out" / "replay_v2_runs.csv"

# declared prerequisite pairs (upstream must hold for downstream to be possible)
EDGES = {
    "ccna_rip_routing_basic": [("rip_enabled", "r4_loopback_via_rip"),
                               ("r4_loopback_via_rip", "loopback_reachability")],
    "ccie_bgp_dual_homing_expert": [("ebgp_isp1_established", "outbound_filtering"),
                                    ("ebgp_isp1_established", "primary_path_preference"),
                                    ("ebgp_isp2_established", "as_path_prepending")],
}


def model_of(run_id: str) -> str:
    m = re.match(r"(?:ollama|openai)_(.+?)_single", run_id)
    return m.group(1) if m else run_id


def first_true(traj: list[dict], pid: str):
    for snap in traj:
        if snap["properties"].get(pid):
            return snap["turn"]
    return None


def main() -> None:
    recs = [json.loads(p.read_text()) for p in sorted(IN.glob("*.json")) if p.name != "summary.json"]
    rows, order = [], defaultdict(lambda: {"both": 0, "before": 0, "same": 0, "after": 0})
    for r in recs:
        row = {"task": r["task_id"], "model": model_of(r["run_id"]), "run_id": r["run_id"],
               "n_commands": r["n_commands"], "orig_v1": r.get("original_v1_completeness")}
        if "skipped" in r:
            row.update(status=f"skipped ({r.get('termination_reason')})")
            rows.append(row)
            continue
        v1, v2 = r["v1_completeness"], r["v2_completeness"]
        row.update(status="scored", replays=len(v2), stable_v2=r["stable_v2_vector"],
                   stable_v1=r["stable_v1_vector"], v1_replay=v1[0] if v1 else None,
                   v2_replay=v2[0] if v2 else None,
                   v2_unsatisfied=";".join(k for k, v in (r.get("v2_vector") or {}).items() if not v))
        rows.append(row)
        for rp in r["replays"]:
            if "trajectory" not in rp:
                continue
            for up, down in EDGES.get(r["task_id"], []):
                a, b = first_true(rp["trajectory"], up), first_true(rp["trajectory"], down)
                if a is None or b is None:
                    continue
                key = (r["task_id"], up, down)
                order[key]["both"] += 1
                order[key]["before" if a < b else "same" if a == b else "after"] += 1

    with OUT_CSV.open("w", newline="") as fh:
        cols = ["task", "model", "run_id", "status", "n_commands", "orig_v1", "v1_replay", "v2_replay",
                "stable_v2", "stable_v1", "replays", "v2_unsatisfied"]
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

    md = ["# Replay v2 report\n"]
    scored = [r for r in rows if r["status"] == "scored"]
    md.append(f"Runs: {len(rows)}; scored: {len(scored)}; skipped: {len(rows) - len(scored)}\n")
    md.append("## Stability (identical v2 property vector across all replays, fixed wait)\n")
    md.append("| task | scored | stable (v2 vector) | stable (v1 vector) |\n|---|---|---|---|")
    for task in sorted({r["task"] for r in scored}):
        t = [r for r in scored if r["task"] == task]
        md.append(f"| {task} | {len(t)} | {sum(r['stable_v2'] for r in t)} | {sum(r['stable_v1'] for r in t)} |")
    md.append("\n## Same final state, old vs new checks\n")
    md.append("| task | model | cmds | original v1 (live) | v1 on replay | v2 on replay | v2 unmet |\n|---|---|---|---|---|---|---|")
    for r in sorted(scored, key=lambda r: (r["task"], r["model"])):
        md.append(f"| {r['task'][:14]} | {r['model']} | {r['n_commands']} | {r['orig_v1']:.2f} | "
                  f"{r['v1_replay']:.2f} | {r['v2_replay']:.2f} | {r['v2_unsatisfied'] or '-'} |")
    md.append("\n## Skipped runs\n")
    for r in rows:
        if r["status"] != "scored":
            md.append(f"- {r['task'][:14]} {r['model']}: {r['status']}")
    md.append("\n## Prerequisite order in per-turn snapshots (all replays)\n")
    md.append("| task | upstream -> downstream | both true | before | same turn | after |\n|---|---|---|---|---|---|")
    for (task, up, down), c in sorted(order.items()):
        md.append(f"| {task[:14]} | {up} -> {down} | {c['both']} | {c['before']} | {c['same']} | {c['after']} |")
    OUT_MD.write_text("\n".join(md) + "\n")
    print(OUT_MD.read_text())


if __name__ == "__main__":
    main()
