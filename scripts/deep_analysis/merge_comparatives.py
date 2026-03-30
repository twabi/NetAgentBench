#!/usr/bin/env python3
"""
Merge all comparative study run JSONs into a single comparatives_all directory.

Copies runs from each comparative_study_* session into:
    results/comparatives_all/runs/<task_id>/<filename>.json

Deduplicates by run_id. Creates a combined session_info.json.
"""

import json
import shutil
from datetime import datetime
from pathlib import Path

RESULTS_DIR = Path(__file__).resolve().parent.parent.parent / "results"
COMP_STUDY_DIR = RESULTS_DIR / "comparative_study"
OUTPUT_DIR = RESULTS_DIR / "comparatives_all"


def merge(force: bool = False) -> Path:
    """Merge all comparative study runs into comparatives_all/.

    Returns the output directory path.
    """
    if OUTPUT_DIR.exists() and not force:
        n = sum(1 for _ in (OUTPUT_DIR / "runs").rglob("*.json")) if (OUTPUT_DIR / "runs").exists() else 0
        print(f"comparatives_all already exists with {n} run files. Use force=True to re-merge.")
        return OUTPUT_DIR

    session_dirs = sorted(COMP_STUDY_DIR.glob("comparative_study_*"))
    if not session_dirs:
        raise FileNotFoundError(f"No comparative_study_* folders found in {COMP_STUDY_DIR}")

    print(f"Found {len(session_dirs)} comparative study sessions:")
    for sd in session_dirs:
        print(f"  {sd.name}")

    runs_out = OUTPUT_DIR / "runs"
    runs_out.mkdir(parents=True, exist_ok=True)

    seen_run_ids: dict[str, str] = {}
    copied, skipped_dup = 0, 0
    source_sessions = []

    for sd in session_dirs:
        runs_dir = sd / "runs"
        if not runs_dir.exists():
            continue

        session_info_path = sd / "session_info.json"
        if session_info_path.exists():
            with open(session_info_path) as f:
                source_sessions.append(json.load(f))

        for json_file in runs_dir.rglob("*.json"):
            if json_file.name == "session_info.json":
                continue

            try:
                with open(json_file) as f:
                    data = json.load(f)
            except Exception:
                continue

            run_id = data.get("run_id", "")
            if not run_id:
                continue

            if run_id in seen_run_ids:
                skipped_dup += 1
                continue

            task_id = data.get("task_id", "unknown")
            task_dir = runs_out / task_id
            task_dir.mkdir(exist_ok=True)

            dest = task_dir / json_file.name
            shutil.copy2(json_file, dest)
            seen_run_ids[run_id] = str(dest)
            copied += 1

    combined_info = {
        "session_name": "comparatives_all",
        "study_type": "merged_comparative",
        "created_at": datetime.now().isoformat(),
        "source_sessions": [s.get("session_name", "unknown") for s in source_sessions],
        "total_runs": copied,
        "duplicates_skipped": skipped_dup,
        "tasks": sorted(set(d.name for d in runs_out.iterdir() if d.is_dir())),
    }
    with open(OUTPUT_DIR / "session_info.json", "w") as f:
        json.dump(combined_info, f, indent=2)

    print(f"\nMerge complete: {copied} runs copied, {skipped_dup} duplicates skipped")
    print(f"Output: {OUTPUT_DIR}")
    return OUTPUT_DIR


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Merge comparative study runs")
    parser.add_argument("--force", action="store_true", help="Re-merge even if output exists")
    args = parser.parse_args()
    merge(force=args.force)
