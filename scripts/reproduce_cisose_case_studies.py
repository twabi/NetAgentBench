#!/usr/bin/env python3
"""Regenerate cisose_paper tables from archived run JSON.

Usage (from repo root):
  python3 scripts/reproduce_cisose_case_studies.py
  python3 scripts/reproduce_cisose_case_studies.py --aggregate

With --aggregate, prints pattern-level means for the cisose aggregate table: meltdown
rate (detect_meltdowns), mean final score, mean coordination_ratio from turn_waste,
mean H_router on constructive-plus-destructive commands only (paper Definition of
router entropy), and mean protocol_reset_count from coherence_analysis.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))

from scripts.analyze_model_behavior import classify_command, detect_meltdowns  # noqa: E402
from scripts.deep_analysis.coherence_analysis import analyze_run as coherence_run  # noqa: E402
from scripts.deep_analysis.run_loader import (  # noqa: E402
    DEFAULT_SESSION,
    enrich_run,
    extract_execution_commands,
    load_and_enrich,
)
from scripts.deep_analysis.turn_waste import analyze_run as waste_run  # noqa: E402

RUNS = {
    "Case A": _REPO
    / "results/comparatives_all/runs/ccnp_multiarea_ospf_intermediate"
    / "ollama_qwen3coder:30b_multi_concurrent_mt_20260225_085322_7f26bc39.json",
    "Case B": _REPO
    / "results/comparatives_all/runs/ccnp_multiarea_ospf_intermediate"
    / "openai_gpt5mini20250807_multi_group_chat_mt_20260225_063624_422a860a.json",
    "Case C": _REPO
    / "results/comparatives_all/runs/ccnp_multiarea_ospf_intermediate"
    / "openai_gpt5mini20250807_multi_sequential_mt_20260219_211947_2e47c2da.json",
}


def router_entropy_config_only(pairs: list[tuple[str, str]]) -> float:
    rc: Counter[str] = Counter()
    for r, cmd in pairs:
        if classify_command(cmd) in ("constructive", "destructive"):
            rc[r] += 1
    tot = sum(rc.values())
    if tot == 0:
        return 0.0
    return -sum((c / tot) * math.log2(c / tot) for c in rc.values() if c)


def typed_sigma_union(pairs: list[tuple[str, str]]) -> dict[str, int]:
    c = d = dg = o = 0
    for _, cmd in pairs:
        t = classify_command(cmd)
        if t == "constructive":
            c += 1
        elif t == "destructive":
            d += 1
        elif t == "diagnostic":
            dg += 1
        else:
            o += 1
    return {
        "constructive": c,
        "destructive": d,
        "diagnostic": dg,
        "other": o,
        "typed_union": c + d + dg,
    }


def aggregate_table_metrics() -> None:
    """Print means aligned with the cisose_paper aggregate results table."""
    patterns = ["single", "sequential", "debate", "group_chat", "concurrent"]
    by_pat: dict[str, list] = {}
    for run in load_and_enrich(DEFAULT_SESSION):
        p = run.get("_pattern")
        if p in patterns:
            by_pat.setdefault(p, []).append(run)

    print("Pattern-level aggregates (load_and_enrich session:", DEFAULT_SESSION.name, ")")
    print("Columns: N, meltdown%, mean_score, mean_sigma_C, mean_H_router_config_only, mean_resets")
    for pat in patterns:
        rs = by_pat.get(pat, [])
        n = len(rs)
        if n == 0:
            continue
        melts = scores = sigc = ents = resets = 0.0
        for run in rs:
            pairs = extract_execution_commands(run.get("execution_log") or [])
            melts += 1.0 if detect_meltdowns(run)["meltdown_detected"] else 0.0
            scores += float(run.get("scoring", {}).get("final_score") or 0.0)
            sigc += float(waste_run(run)["coordination_ratio"])
            ents += router_entropy_config_only(pairs)
            resets += float(coherence_run(run)["protocol_reset_count"])
        print(
            f"  {pat:12} N={n}  melt={100 * melts / n:.1f}%  "
            f"score={scores / n:.3f}  sigC={sigc / n:.3f}  "
            f"Hcfg={ents / n:.3f}  rst={resets / n:.3f}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--aggregate",
        action="store_true",
        help="Print pattern-level Table~aggregate metrics and exit.",
    )
    args = parser.parse_args()
    if args.aggregate:
        aggregate_table_metrics()
        return

    for label, path in RUNS.items():
        run = json.loads(path.read_text())
        run = enrich_run(run)
        pairs = extract_execution_commands(run.get("execution_log") or [])
        t = typed_sigma_union(pairs)
        coh = coherence_run(run)
        tw = waste_run(run)
        md = detect_meltdowns(run)
        m = run.get("metrics") or {}
        score = run.get("scoring", {}).get("final_score", 0.0)
        print("=" * 72)
        print(label, run["run_id"])
        print("  path:", path.relative_to(_REPO))
        print("  final_score:", score)
        print("  turns_to_complete:", m.get("turns_to_complete"))
        print("  len(reasoning_trace):", len(run.get("reasoning_trace") or []))
        print("  |execution_log|:", len(pairs))
        print("  classify_command:", t)
        print("  protocol_reset_count:", coh["protocol_reset_count"])
        print("  H_router (config-only):", round(router_entropy_config_only(pairs), 4))
        print("  H_router (coherence all cmds):", round(coh["router_entropy"], 4))
        print("  turn_waste sigma_C:", round(tw["coordination_ratio"], 4))
        print("  turn_waste WR:", round(tw["waste_ratio"], 4))
        print("  meltdown:", md["meltdown_detected"], md["signals"])


if __name__ == "__main__":
    main()


"""

\textbf{Reproducibility (case studies).} The three CCNP case-study rows in Table~\ref{tab:cases} reference concrete artifacts in~\cite{Dataset2026} under \texttt{run\_id}: Case~A \texttt{ollama\_qwen3coder:30b\_multi\_concurrent\_mt\_20260225\_085322\_7f26bc39}; Case~B \texttt{openai\_gpt5mini20250807\_multi\_group\_chat\_mt\_20260225\_063624\_422a860a}; Case~C \texttt{openai\_gpt5mini20250807\_multi\_sequential\_mt\_20260219\_211947\_2e47c2da}. Counts in Table~\ref{tab:cases} were recomputed from those JSON logs (February~2026 export): command typing uses the released \texttt{classify\_command} helper in the NetAgentBench analysis tooling~\cite{NetAgentBench2026}; $\sigC$ and $\WR$ match \texttt{turn\_waste.py} on \texttt{reasoning\_trace}; protocol-reset counts and router-target entropy on the full \texttt{execution\_log} match \texttt{coherence\_analysis.py}. The $\Hrouter$ column applies Definition~\ref{def:router-entropy} (entropy of $\Sigma_{\mathrm{config}}$-only targets). Case~B lists $m_{\mathrm{role}}=82$ role steps in \texttt{reasoning\_trace} (the harness also reports $m=5$ executor turns until submission). A one-command regeneration script, \texttt{scripts/reproduce\_cisose\_case\_studies.py}, ships with the NetAgentBench code artifact~\cite{NetAgentBench2026}.


"""