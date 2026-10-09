"""Align per-command property snapshots with the commands that produced them.

Two harness versions wrote metrics.property_trajectory differently:

  'labelled'  (untaxed cohort, results/v2_openrouter): one snapshot after each command the
              agent LABELLED config. Snapshot i belongs to the i-th config-labelled command.
              Changes sent through the read channel have no snapshot.
  'all'       (taxed cohort, results/v2_openrouter_taxed): one snapshot after EVERY command,
              reads included. Snapshot i belongs to command i of command_transcript.

The logs carry no harness marker, so the mode is inferred from counts. A single run cannot
always tell: when an agent labels every command config, both harnesses give one snapshot per
command. So the mode is decided per COHORT (set_cohort_mode): 'all' only if every run has one
snapshot per command, else 'labelled'. For those ambiguous runs the alignment is the same
either way; only the interpretation (snapshot timing, "at submit") depends on the mode.
"""

from __future__ import annotations

from typing import Any, Callable


_COHORT_MODE: str | None = None


def run_snapshot_mode(d: dict[str, Any]) -> str:
    """What this run's counts alone suggest."""
    ct = d.get("command_transcript") or []
    snaps = passive(d)
    if snaps and len(snaps) == len(ct):
        return "all"
    return "labelled"


def set_cohort_mode(runs, mode: str = "auto") -> str:
    """Fix the mode for every run of a cohort. mode: 'auto', 'all' or 'labelled'."""
    global _COHORT_MODE
    if mode == "auto":
        runs = list(runs)
        mode = "all" if runs and all(run_snapshot_mode(d) == "all" for d in runs) else "labelled"
    _COHORT_MODE = mode
    return mode


def snapshot_mode(d: dict[str, Any]) -> str:
    if _COHORT_MODE is not None:
        return _COHORT_MODE
    ct = d.get("command_transcript") or []
    snaps = passive(d)
    if snaps and len(snaps) == len(ct):
        return "all"
    return "labelled"


def passive(d: dict[str, Any]) -> list[dict[str, Any]]:
    traj = (d.get("metrics") or {}).get("property_trajectory") or []
    return [s for s in traj if s.get("kind", "passive_reveal") == "passive_reveal"]


def aligned(d: dict[str, Any], classify: Callable[[str], str]) -> list[dict[str, Any]]:
    """One entry per snapshot: transcript index, command, content class, snapshot."""
    ct = d.get("command_transcript") or []
    snaps = passive(d)
    mode = snapshot_mode(d)
    if mode == "all":
        idx = list(range(len(ct)))
    else:
        idx = [i for i, c in enumerate(ct) if c.get("command_type") == "config"]
    out = []
    for n, snap in enumerate(snaps):
        if n >= len(idx):
            break
        i = idx[n]
        out.append({
            "pos": n,
            "cmd_index": i,
            "command": ct[i],
            "kind": classify(ct[i]["command"]),
            "snapshot": snap,
            "properties": {k: bool(v) for k, v in (snap.get("properties") or {}).items()},
            "completeness": float(snap.get("completeness") or 0.0),
        })
    return out


def last_write_before(d: dict[str, Any], cmd_index: int, classify: Callable[[str], str]):
    """Most recent state-changing command at or before cmd_index (the likely cause of a change)."""
    ct = d.get("command_transcript") or []
    for i in range(min(cmd_index, len(ct) - 1), -1, -1):
        if classify(ct[i]["command"]) == "write":
            return i, ct[i]
    return None, None
