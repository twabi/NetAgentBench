#!/usr/bin/env python3
"""
Threshold Sensitivity Analysis — NetAgentBench (single-agent only)
===================================================================
Addresses reviewer feedback (R1, R2, R3): justifies meltdown-signal
thresholds by showing classification is stable under ±variation.

Meltdown signals (from analyze_model_behavior.py):
  1. Command Loop         — same cmd repeated loop_n+ times consecutively
  2. Destructive Spiral   — dest_win_k+ destructive cmds in window of dest_win_n
  3. Cognitive Stagnation — turns > stag_turns AND score < stag_score
  4. Diagnostic Fixation  — fix_n consecutive diagnostic-only cmds
  5. Premature Submission — termination='submitted' AND score < prem_score

Meltdown = ANY 1+ signal  (min_signals threshold also swept for sensitivity).

Usage:
    python scripts/sensitivity_analysis.py
    python scripts/sensitivity_analysis.py --data results/comparatives_all
"""

import argparse
import csv
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List

# ── Paths ───────────────────────────────────────────────────────────────────────
RESULTS_ROOT = Path(__file__).parent.parent / "results"
DEFAULT_DATA = RESULTS_ROOT / "comparatives_all"

# ── Paper tasks and model map ───────────────────────────────────────────────────
PAPER_TASKS = {
    "ccie_bgp_dual_homing_expert",
    "ccna_rip_routing_basic",
    "ccnp_multiarea_ospf_intermediate",
    "troubleshoot_bgp_route_filtering",
    "troubleshoot_ospf_adjacency_issue",
}

MODEL_MAP = {
    "openai_gpt5mini20250807":      "GPT-5-mini",
    "ollama_qwen3coder:30b":        "Qwen3-Coder",
    "ollama_llama33:70b":           "Llama-3.3",
    "ollama_qwen3codernext:latest": "Qwen3-Coder-Next",
}
MODEL_ORDER = ["GPT-5-mini", "Qwen3-Coder", "Llama-3.3", "Qwen3-Coder-Next"]


# ── Command classifier (mirrors analyze_model_behavior.py exactly) ──────────────
def _classify(cmd: str) -> str:
    c = cmd.lower()
    if any(p in c for p in ["no router", "no ip", "no network", "no interface", "shutdown"]):
        return "destructive"
    if any(p in c for p in ["show ", "ping ", "traceroute", "ip addr show",
                              "ip route get", "ip route show"]):
        return "diagnostic"
    if any(p in c for p in ["router ", "network ", "ip addr add", "interface ",
                              "vtysh", "no shutdown", "echo "]):
        return "constructive"
    return "other"


def _get_cmds(log: list) -> List[str]:
    cmds = []
    for entry in log:
        if isinstance(entry, str):
            cmds.append(entry.split(" | ", 1)[-1].strip() if " | " in entry else entry.strip())
    return cmds


# ── Single-run meltdown detector with parametric thresholds ────────────────────
def detect_meltdown(
    run: dict,
    loop_n: int = 4,            # consecutive identical commands
    dest_win_k: int = 3,        # destructive cmds in window
    dest_win_n: int = 5,        # sliding window size for destructive spiral
    stag_turns: int = 25,       # turn count for cognitive stagnation
    stag_score: float = 0.1,    # score threshold for cognitive stagnation
    fix_n: int = 10,            # consecutive diagnostic-only for fixation
    prem_score: float = 0.3,    # score threshold for premature submission
    min_signals: int = 1,       # signals needed to declare meltdown
) -> Dict:
    """Detect meltdown with configurable thresholds. Returns signals dict."""
    cmds = _get_cmds(run.get("execution_log", []) or [])
    types = [_classify(c) for c in cmds]
    signals: List[str] = []

    # 1. Command Loop
    for i in range(len(cmds) - loop_n + 1):
        if len(set(cmds[i:i + loop_n])) == 1:
            signals.append("Command Loop")
            break

    # 2. Destructive Spiral
    for i in range(len(types) - dest_win_n + 1):
        if types[i:i + dest_win_n].count("destructive") >= dest_win_k:
            signals.append("Destructive Spiral")
            break

    # 3. Cognitive Stagnation
    m_data = run.get("metrics") or {}
    turns = m_data.get("turns_to_complete") or 0
    score = (run.get("scoring") or {}).get("final_score", 0) or 0
    if turns > stag_turns and score < stag_score:
        signals.append("Cognitive Stagnation")

    # 4. Diagnostic Fixation
    for i in range(max(0, len(types) - fix_n + 1)):
        if all(t == "diagnostic" for t in types[i:i + fix_n]):
            signals.append("Diagnostic Fixation")
            break

    # 5. Premature Submission
    reason = (m_data.get("termination_reason") or "").lower()
    if reason == "submitted" and score < prem_score:
        signals.append("Premature Submission")

    return {
        "meltdown": len(signals) >= min_signals,
        "signals": signals,
        "n_signals": len(signals),
    }


# ── Data loader (single-agent runs from comparatives_all) ──────────────────────
def load_single_runs(data_dir: Path) -> List[dict]:
    runs = []
    runs_dir = data_dir / "runs"
    for path in runs_dir.glob("**/*_single_*.json"):
        try:
            d = json.loads(path.read_text())
        except Exception:
            continue
        task = d.get("task_id", "")
        if task not in PAPER_TASKS:
            continue
        testee = d.get("testee_id", "")
        model = next((v for k, v in MODEL_MAP.items() if k in testee), None)
        if model is None:
            continue
        d["_model"] = model
        runs.append(d)
    return runs


# ── Helpers ────────────────────────────────────────────────────────────────────
def classify_all(runs: List[dict], **kwargs) -> List[bool]:
    return [detect_meltdown(r, **kwargs)["meltdown"] for r in runs]


def reclass_rate(base: List[bool], variant: List[bool]) -> float:
    return sum(1 for b, v in zip(base, variant) if b != v) / len(base)


# ── Main ───────────────────────────────────────────────────────────────────────
def main(data_dir: Path) -> None:
    print(f"Loading single-agent runs from {data_dir} ...")
    runs = load_single_runs(data_dir)
    if not runs:
        print("ERROR: No single-agent runs found. Check path.")
        return

    n = len(runs)
    print(f"Loaded {n} single-agent runs.\n")

    # Baseline classification
    baseline = classify_all(runs)
    n_melt = sum(baseline)
    print(f"Baseline meltdown rate: {n_melt/n:.1%} ({n_melt}/{n})\n")

    # ── Threshold sweep ────────────────────────────────────────────────────────
    variants = [
        # loop_n: consecutive identical command threshold
        ("loop_n=3 (−1)",         {"loop_n": 3}),
        ("loop_n=4 (base)",       {"loop_n": 4}),
        ("loop_n=5 (+1)",         {"loop_n": 5}),

        # Destructive spiral window count
        ("dest_win_k=2 (−1)",     {"dest_win_k": 2}),
        ("dest_win_k=3 (base)",   {"dest_win_k": 3}),
        ("dest_win_k=4 (+1)",     {"dest_win_k": 4}),

        # Premature submission score threshold
        ("prem_score=0.20 (−10%)",{"prem_score": 0.20}),
        ("prem_score=0.30 (base)",{"prem_score": 0.30}),
        ("prem_score=0.40 (+10%)",{"prem_score": 0.40}),

        # Cognitive stagnation turn count
        ("stag_turns=20 (−5)",    {"stag_turns": 20}),
        ("stag_turns=25 (base)",  {"stag_turns": 25}),
        ("stag_turns=30 (+5)",    {"stag_turns": 30}),

        # Diagnostic fixation window
        ("fix_n=8 (−2)",          {"fix_n": 8}),
        ("fix_n=10 (base)",       {"fix_n": 10}),
        ("fix_n=12 (+2)",         {"fix_n": 12}),

        # min_signals: signals required to call meltdown (1 = any signal)
        ("min_signals=1 (base)",  {"min_signals": 1}),
        ("min_signals=2 (+1)",    {"min_signals": 2}),
    ]

    results = []
    print(f"{'Variant':<30} {'Rate':>6}  {'Changed':>9}  {'Reclassif%':>12}")
    print("-" * 64)
    for label, kwargs in variants:
        variant = classify_all(runs, **kwargs)
        reclass = reclass_rate(baseline, variant)
        rate = sum(variant) / n
        changed = sum(1 for b, v in zip(baseline, variant) if b != v)
        marker = "  ◀ BASELINE" if reclass == 0.0 and kwargs == {} or label.endswith("(base)") else ""
        print(f"  {label:<28} {rate:>5.1%}   {changed:>5}/{n}    {reclass:>9.1%}{marker}")
        results.append({
            "variant": label,
            "meltdown_rate_pct": round(rate * 100, 1),
            "changed": changed,
            "reclassification_pct": round(reclass * 100, 1),
        })

    # ── Per-model breakdown ────────────────────────────────────────────────────
    print(f"\n{'Model':<22} {'N':>4}  {'Melt':>8}  {'Rate':>6}  {'μ Score':>8}  {'σ Score':>8}")
    print("-" * 65)
    by_model = defaultdict(list)
    for r in runs:
        by_model[r["_model"]].append(r)

    model_rows = []
    for model in MODEL_ORDER:
        mrs = by_model.get(model, [])
        if not mrs:
            continue
        melts = [detect_meltdown(r)["meltdown"] for r in mrs]
        n_m = len(mrs)
        n_melt_m = sum(melts)
        scores = [(r.get("scoring") or {}).get("final_score", 0) or 0 for r in mrs]
        mu = statistics.mean(scores)
        sigma = statistics.stdev(scores) if n_m > 1 else 0.0
        ci = 1.96 * sigma / (n_m ** 0.5)
        print(f"  {model:<20} {n_m:>4}  {n_melt_m:>5}/{n_m}  {n_melt_m/n_m:>5.1%}   {mu:>7.3f}   {sigma:>7.3f}")
        model_rows.append({
            "model": model, "n": n_m, "meltdown_n": n_melt_m,
            "meltdown_rate_pct": round(n_melt_m / n_m * 100, 1),
            "score_mean": round(mu, 3), "score_std": round(sigma, 3),
            "ci_95": round(ci, 3),
        })

    # ── Signal frequency breakdown ─────────────────────────────────────────────
    print("\n── Signal frequency (baseline thresholds) ──────────────────────────")
    sig_counter: Counter = Counter()
    for r in runs:
        sigs = detect_meltdown(r)["signals"]
        sig_counter.update(sigs)
    for sig, count in sig_counter.most_common():
        print(f"  {sig:<28}  {count:>3}  ({count/n:.1%})")

    # ── Sample-size justification ──────────────────────────────────────────────
    print("\n── Sample-size (95% CI half-width on mean score) ───────────────────")
    print(f"{'Model':<22} {'N':>4}  {'μ':>6}  {'σ':>6}  {'CV':>6}  {'±95% CI':>9}")
    for row in model_rows:
        cv = row["score_std"] / row["score_mean"] if row["score_mean"] else float("inf")
        print(f"  {row['model']:<20} {row['n']:>4}  {row['score_mean']:>6.3f}  "
              f"{row['score_std']:>6.3f}  {cv:>6.2f}   ±{row['ci_95']:>6.3f}")

    # ── Compute estimate ───────────────────────────────────────────────────────
    print(f"\n── Compute estimate ─────────────────────────────────────────────────")
    upper = n * 1800 / 3600
    print(f"  Single-agent runs: {n}")
    print(f"  Max wall-clock/run: 1800 s (30 min)")
    print(f"  Upper-bound total:  {upper:.0f} compute-hours")

    # ── Write outputs ──────────────────────────────────────────────────────────
    out_dir = data_dir / "sensitivity"
    out_dir.mkdir(exist_ok=True)

    csv_path = out_dir / "sensitivity_table.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        writer.writeheader()
        writer.writerows(results)

    md_lines = [
        "# NetAgentBench — Meltdown Threshold Sensitivity (Single-Agent Runs)",
        "",
        f"**N = {n} single-agent runs** (comparatives\\_all, single pattern, 4 models × 5 tasks).",
        "",
        "## Threshold Sweep",
        "",
        "Each row varies one threshold by ±1 unit. *Reclassification %* is the fraction of",
        "runs that flip meltdown classification vs. the baseline configuration.",
        "",
        "| Variant | Meltdown rate | Changed | Reclassif. |",
        "|---------|:------------:|:-------:|:----------:|",
    ]
    for row in results:
        is_base = "(base)" in row["variant"]
        tag = " **←**" if is_base else ""
        md_lines.append(
            f"| {row['variant']}{tag} "
            f"| {row['meltdown_rate_pct']:.1f}% "
            f"| {row['changed']}/{n} "
            f"| {row['reclassification_pct']:.1f}% |"
        )

    md_lines += [
        "",
        "## Per-Model Results (Baseline Thresholds)",
        "",
        "| Model | N | Meltdown | Rate | Score μ | Score σ | 95% CI ± |",
        "|-------|--:|:--------:|-----:|--------:|--------:|--------:|",
    ]
    for row in model_rows:
        md_lines.append(
            f"| {row['model']} | {row['n']} | {row['meltdown_n']}/{row['n']} "
            f"| {row['meltdown_rate_pct']:.1f}% | {row['score_mean']:.3f} "
            f"| {row['score_std']:.3f} | ±{row['ci_95']:.3f} |"
        )

    md_lines += [
        "",
        "## Signal Frequency",
        "",
        "| Signal | Count | Rate |",
        "|--------|------:|-----:|",
    ]
    for sig, count in sig_counter.most_common():
        md_lines.append(f"| {sig} | {count} | {count/n:.1%} |")

    md_lines += [
        "",
        "## Sample-Size Justification",
        "",
        "| Model | N | μ | σ | CV | 95% CI ± |",
        "|-------|--:|--:|--:|---:|--------:|",
    ]
    for row in model_rows:
        cv = row["score_std"] / row["score_mean"] if row["score_mean"] else float("inf")
        md_lines.append(
            f"| {row['model']} | {row['n']} | {row['score_mean']:.3f} "
            f"| {row['score_std']:.3f} | {cv:.2f} | ±{row['ci_95']:.3f} |"
        )

    md_lines += [
        "",
        "## Compute Estimate",
        "",
        f"- Single-agent runs analysed: **{n}**",
        f"- Max wall-clock per run: **1,800 s (30 min)**",
        f"- Upper-bound total compute: **{upper:.0f} hours**",
        "- Each run: live Containerlab topology (Docker + FRRouting), isolated per run",
        "- Sessions: Feb 17–22 2026 (4 comparative sessions)",
    ]

    md_path = out_dir / "sensitivity_report.md"
    md_path.write_text("\n".join(md_lines))

    print(f"\n✅  Report: {md_path}")
    print(f"✅  CSV:    {csv_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default=str(DEFAULT_DATA),
                        help="Path to comparatives_all session directory")
    args = parser.parse_args()
    main(Path(args.data))
