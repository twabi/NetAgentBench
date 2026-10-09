"""Process-level analysis of the v2 OpenRouter sweep: how runs reach their end state.

The end score saturates (most runs finish at C = 1.0), so this script measures the path:
cost, methodology, how network state evolved, and which configuration was left behind.

Every command is re-classified by CONTENT (does it change routing/forwarding state?),
because the agent-supplied read/config label is unreliable: agents send state changes
through the read channel (no turn counted, no snapshot, not replayed) and label pure
`show` commands as config.

Outputs (default: experiments/replay_v2/out/process_analysis/):
  per_run_process.csv     one row per run, all metrics
  by_task_model.csv       medians and ranges per task x model
  spread_equal_score.csv  max/min cost ratio among runs that reached C = 1.0, per task
  drops.csv               every property regression in the per-command snapshots + cause
  label_fidelity.csv      commands whose agent label disagrees with their content
  lag_by_property.csv     per property, successful runs where it was true right after the last
                          change, true by submission (taxed cohort: snapshots follow the final
                          reads), or true only after the convergence wait
  designs.csv             configuration choices of successful runs (no golden configuration)
  fig_equal_score_cost.pdf, fig_trajectory_cases.pdf, fig_convergence_lag.pdf,
  fig_process_fingerprint.pdf  (+ .png)

Snapshots are aligned to commands by snapshots.py, which handles both harness policies:
'labelled' (untaxed: one snapshot ~2 s after each config-labelled command) and 'all' (taxed:
one snapshot right after every command). The policy is detected per cohort.

Usage:
  python experiments/replay_v2/analyze_process.py [--runs-dir DIR] [--out-dir DIR] [--paper-dir DIR]
                                                 [--snapshot-mode auto|all|labelled]
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import statistics as st
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.ticker import LogLocator, NullFormatter, FuncFormatter  # noqa: E402

import sys as _sys  # noqa: E402
_sys.path.insert(0, str(Path(__file__).resolve().parent))
from snapshots import aligned, last_write_before, set_cohort_mode, snapshot_mode  # noqa: E402

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
RUNS_DIR = REPO / "results" / "v2_openrouter" / "runs"
TASKS_DIR = REPO / "tasks" / "multi_turn_v2"
OUT_DIR = HERE / "out" / "process_analysis"

TASKS = [
    ("ccna_rip_routing_basic", "RIP"),
    ("troubleshoot_ospf_adjacency_issue", "OSPF adjacency TS"),
    ("ccnp_multiarea_ospf_intermediate", "Multi-area OSPF"),
    ("ccie_bgp_dual_homing_expert", "BGP dual-homing"),
    ("troubleshoot_bgp_route_filtering", "BGP filtering TS"),
]
TASK_LABEL = dict(TASKS)
TROUBLESHOOT = {"troubleshoot_ospf_adjacency_issue", "troubleshoot_bgp_route_filtering"}

# Okabe-Ito hues as in analyze_v2_sweep.py; markers are the second cue (CVD floor pair).
MODELS = [
    ("qwen/qwen3.8-flash", "Qwen3.8 Flash", "#E69F00", "o"),
    ("google/gemini-3.1-flash-lite", "Gemini 3.1 Flash Lite", "#56B4E9", "s"),
    ("openai/gpt-6-luna", "GPT-6 Luna", "#009E73", "^"),
    ("z-ai/glm-5.3", "GLM 5.3", "#CC79A7", "D"),
]
M_LABEL = {m: l for m, l, _, _ in MODELS}
M_COLOR = {m: c for m, _, c, _ in MODELS}
M_MARK = {m: k for m, _, _, k in MODELS}
INK, MUTED, GRID = "#1f1f1e", "#6b6b68", "#e4e4e1"

# Palettes used when --models overrides the built-in cohort (Okabe-Ito hues, distinct markers).
MODEL_PALETTE = ["#E69F00", "#56B4E9", "#009E73", "#CC79A7", "#0072B2", "#D55E00"]
MODEL_MARKERS_CYCLE = ["o", "s", "^", "D", "v", "P"]

# ----------------------------------------------------------------------------- classify
_CLEAR = re.compile(r"\bclear (ip )?(bgp|ospf)", re.I)
_SHELL_MUT = re.compile(
    r"\bip (addr|address|link|route) (add|del|replace|set|flush)|sysctl -w|\bkill\b|service frr|frr-reload", re.I)
_VTYSH_ARG = re.compile(r"-c\s+(['\"])(.*?)\1")
_NAV = re.compile(
    r"^(conf(igure)?( terminal| t)?|end|exit|exit-address-family|do .*|.*\?|write( memory)?|show .*|"
    r"router \w+( \d+)?|interface \S+|address-family .*|route-map \S+ (permit|deny) \d+|key chain \S+|"
    r"key \d+|(no )?debug .*|log .*|terminal .*|list)$", re.I)
# entering these contexts creates an object even with no further statements
_CREATES = re.compile(r"^(route-map \S+ (permit|deny) \d+|key chain \S+)", re.I)


def vtysh_lines(cmd: str) -> list[str]:
    return [m.group(2).strip() for m in _VTYSH_ARG.finditer(cmd)]


def config_lines(cmd: str) -> list[str]:
    """Configuration statements that change state (navigation and reads removed)."""
    lines = vtysh_lines(cmd)
    if not any(re.match(r"conf(igure)?( terminal| t)?$", l, re.I) for l in lines):
        return []
    if any(l.endswith("?") for l in lines):
        # a help query: the partial statements before '?' are not applied
        return [l for l in lines if _CREATES.match(l)]
    return [l for l in lines if not _NAV.match(l) or _CREATES.match(l)]


def classify(cmd: str) -> str:
    """'write' changes routing/forwarding state; 'persist' only saves config; else 'read'."""
    if _CLEAR.search(cmd) or _SHELL_MUT.search(cmd) or config_lines(cmd):
        return "write"
    if re.search(r"\bwrite( memory)?\b|copy run", cmd, re.I):
        return "persist"
    return "read"


def disruptive_kinds(cmd: str) -> list[str]:
    """Actions that tear down live protocol state even when the end state is correct."""
    kinds = []
    # hard resets only: 'soft' refreshes re-send routes without tearing the session down
    if any("soft" not in m.group(0) for m in re.finditer(r"clear (ip )?(bgp|ospf)[^'\";|&]*", cmd, re.I)):
        kinds.append("hard session/process reset")
    if re.search(r"ip ospf network (point-to-point|broadcast|non-broadcast)", cmd, re.I):
        kinds.append("OSPF network-type change")
    # removing a whole process or peer (not 'no network ...', which is ordinary reconfiguration)
    if re.search(r"-c\s+['\"]no (router \w+|neighbor \S+ remote-as)\b", cmd, re.I):
        kinds.append("removal of protocol process or peer")
    if re.search(r"-c\s+['\"]shutdown['\"]|link set \S+ down", cmd, re.I):
        kinds.append("interface shutdown")
    return kinds


# ----------------------------------------------------------------------------- load
def model_of(d: dict[str, Any]) -> str:
    return str(d.get("model_version", "")).split(":", 1)[-1]


def load_runs(runs_dir: Path) -> list[dict[str, Any]]:
    runs = []
    for path in sorted(runs_dir.glob("*/*.json")):
        d = json.loads(path.read_text())
        if d.get("task_id") not in TASK_LABEL or model_of(d) not in M_LABEL:
            continue
        runs.append(d)
    return runs


def task_properties(tasks_dir: Path) -> dict[str, list[str]]:
    out = {}
    for tid, _ in TASKS:
        p = tasks_dir / f"{tid}.json"
        if p.exists():
            out[tid] = [x["id"] for x in json.loads(p.read_text())["intent"]["properties"]]
    return out


# ----------------------------------------------------------------------------- metrics
_VERIFY_WORDS = re.compile(r"\b(verify|verif\w*|confirm\w*|check\w*|validat\w*)\b", re.I)


def run_metrics(d: dict[str, Any]) -> dict[str, Any]:
    m = d.get("metrics") or {}
    ct = d.get("command_transcript") or []
    al = aligned(d, classify)
    mode = snapshot_mode(d)
    kinds = [classify(c["command"]) for c in ct]
    seq = "".join({"write": "W", "persist": "p", "read": "r"}[k] for k in kinds)
    w_idx = [i for i, k in enumerate(kinds) if k == "write"]
    writes = [ct[i] for i in w_idx]
    comp = [a["completeness"] for a in al]
    goal_pos = next((a["cmd_index"] + 1 for a in al if a["completeness"] >= 1 - 1e-9), None)
    wsn = [a for a in al if a["kind"] == "write"]
    post_write_C = wsn[-1]["completeness"] if wsn else None

    drops, returned = [], 0
    for a, b in zip(al, al[1:]):
        for k, v in a["properties"].items():
            if v and not b["properties"].get(k):
                later = any(x["properties"].get(k) for x in al if x["pos"] > b["pos"])
                returned += later
                drops.append((k, b["cmd_index"] + 1, later))
    # a state-changing command whose snapshot shows the same vector as the previous snapshot
    prev_of = {a["pos"]: (al[a["pos"] - 1]["properties"] if a["pos"] > 0 else {}) for a in al}
    unchanged = sum(1 for a in wsn if a["properties"] == prev_of[a["pos"]] and a["pos"] > 0)

    disrupt = Counter(k for c in writes for k in disruptive_kinds(c["command"]))
    thoughts = [s["content"] for s in d.get("reasoning_trace") or [] if s.get("step") == "thought"]
    terminal = d["scoring"]["completeness"]
    return {
        "run_id": d["run_id"], "task_id": d["task_id"], "model": model_of(d),
        "C": terminal, "complete": terminal >= 1 - 1e-9,
        "termination": m.get("termination_reason"),
        # cost
        "writes": len(w_idx), "reads": kinds.count("read"), "persist": kinds.count("persist"),
        "commands": len(ct), "turns": int(m.get("turns_to_complete") or 0), "failed_commands": sum(not c.get("success", True) for c in ct),
        "wall_time_s": round(float(m.get("time_to_complete") or 0.0), 1),
        "tokens": int((m.get("token_usage") or {}).get("total_tokens") or 0),
        "config_lines": sum(len(config_lines(c["command"])) for c in writes),
        "nodes_written": len({c["node"] for c in writes}),
        # methodology
        "recon_reads": w_idx[0] if w_idx else len(ct),
        "verify_reads": (len(ct) - 1 - w_idx[-1]) if w_idx else 0,
        "read_write_switches": sum(1 for a, b in zip(seq, seq[1:]) if (a == "W") != (b == "W")),
        "lines_per_write": round(sum(len(config_lines(c["command"])) for c in writes) / len(writes), 2) if writes else 0,
        "disruptive_ops": sum(disrupt.values()),
        "disruptive_detail": ";".join(f"{k}:{v}" for k, v in disrupt.items()),
        "sequence": seq,
        # label fidelity (agent label vs content)
        "hidden_writes": sum(1 for c, k in zip(ct, kinds) if c["command_type"] == "read" and k == "write"),
        "phantom_writes": sum(1 for c, k in zip(ct, kinds) if c["command_type"] == "config" and k == "read"),
        # state evolution. 'labelled' runs: a snapshot ~2 s after each config-labelled command.
        # 'all' runs (taxed harness): a snapshot immediately after every command, reads included.
        "snapshot_mode": mode,
        "snapshots": len(al),
        "goal_seen_at_command": goal_pos,
        "post_last_write_C": round(post_write_C, 3) if post_write_C is not None else None,
        "at_submit_C": round(comp[-1], 3) if comp else None,
        "lag_to_terminal": round(terminal - comp[-1], 3) if comp else None,
        "unconverged_at_submit": (mode == "all" and bool(comp) and comp[-1] < terminal - 1e-9),
        "unchanged_snapshot_share": round(unchanged / max(len(wsn) - 1, 1), 2) if len(wsn) > 1 else 0,
        "regressions": len(drops), "regressions_recovered": returned,
        "mean_snapshot_C": round(sum(comp) / len(comp), 3) if comp else 0,
        # reasoning
        "thoughts": len(thoughts),
        "words_per_thought": round(sum(len(t.split()) for t in thoughts) / len(thoughts), 1) if thoughts else 0,
        "verify_thought_share": round(sum(bool(_VERIFY_WORDS.search(t)) for t in thoughts) / len(thoughts), 2)
        if thoughts else 0,
        "_drops": drops,
    }


def drop_rows(d: dict[str, Any]) -> list[dict[str, Any]]:
    """Every property that was true at one snapshot and false at the next.

    The cause is the most recent state-changing command at or before the snapshot where the
    loss was first seen (in 'all' mode that snapshot may follow a read: the loss surfaced
    while the agent was looking)."""
    al = aligned(d, classify)
    rows = []
    for a, b in zip(al, al[1:]):
        for k, v in a["properties"].items():
            if v and not b["properties"].get(k):
                wi, cmd = last_write_before(d, b["cmd_index"], classify)
                cmd = cmd or {"node": "?", "command": "?"}
                cause = disruptive_kinds(cmd["command"])
                rows.append({
                    "run_id": d["run_id"], "task_id": d["task_id"], "model": model_of(d),
                    "snapshot_mode": snapshot_mode(d),
                    "property": k, "seen_at_command": b["cmd_index"] + 1,
                    "seen_after": b["kind"], "cause_command": (wi + 1) if wi is not None else None,
                    "node": cmd["node"],
                    # the loss showed up after a read: the network moved while the agent looked
                    "cause": (";".join(cause) or "other change") if b["kind"] == "write"
                    else "surfaced during a read (last change: " + (";".join(cause) or "other change") + ")",
                    "recovered_in_snapshots": any(x["properties"].get(k) for x in al if x["pos"] > b["pos"]),
                    "terminal_C": d["scoring"]["completeness"], "command": cmd["command"][:300],
                })
    return rows


def label_rows(d: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for c in d.get("command_transcript") or []:
        k = classify(c["command"])
        if (c["command_type"] == "read" and k == "write") or (c["command_type"] == "config" and k == "read"):
            out.append({"run_id": d["run_id"], "task_id": d["task_id"], "model": model_of(d),
                        "agent_label": c["command_type"], "content_class": k, "node": c["node"],
                        "command": c["command"][:300]})
    return out


def design_row(d: dict[str, Any]) -> dict[str, Any]:
    writes = " || ".join(c["command"] for c in d.get("command_transcript") or [] if classify(c["command"]) == "write")
    t = d["task_id"]
    row = {"run_id": d["run_id"], "task_id": t, "model": model_of(d), "C": d["scoring"]["completeness"]}
    if t == "ccna_rip_routing_basic":
        row["rip_auth"] = "md5" if re.search(r"authentication mode md5", writes) else (
            "text" if re.search(r"authentication (mode text|string)", writes) else "none")
        row["rip_networks"] = "summary 10.0.0.0/8" if "network 10.0.0.0/8" in writes else "per-prefix"
    elif t in ("troubleshoot_ospf_adjacency_issue", "ccnp_multiarea_ospf_intermediate"):
        row["ospf_style"] = ("interface 'ip ospf area'" if re.search(r"ip ospf area \d", writes)
                             else "network statements")
        row["p2p_network_type"] = bool(re.search(r"ip ospf network point-to-point", writes))
        row["process_reset"] = bool(re.search(r"clear ip ospf", writes))
    elif t == "ccie_bgp_dual_homing_expert":
        row["local_pref"] = ",".join(sorted(set(re.findall(r"local-preference (\d+)", writes))))
        pre = re.findall(r"as-path prepend ((?:\d+ ?)+)", writes)
        row["prepend_count"] = ",".join(sorted({str(len(p.split())) for p in pre}))
        row["timers"] = ",".join(sorted(set(re.findall(r"timers (\d+ \d+)", writes))))
        row["ibgp_between_edges"] = bool(re.search(r"neighbor 10\.\S+ remote-as 65100", writes))
        row["clear_bgp_commands"] = len(re.findall(r"clear (ip )?bgp", writes))  # hard and soft
    elif t == "troubleshoot_bgp_route_filtering":
        swapped = "route-map FILTER-OUT out" in writes
        withdrew = bool(re.search(r"no network 10\.", writes))
        row["fix"] = ("apply FILTER-OUT + withdraw internal networks" if swapped and withdrew
                      else "apply FILTER-OUT" if swapped else "other")
    row["config_lines"] = sum(len(config_lines(c["command"])) for c in d.get("command_transcript") or []
                              if classify(c["command"]) == "write")
    return row


# ----------------------------------------------------------------------------- stats helpers
def med(xs):
    xs = [x for x in xs if x is not None]
    return st.median(xs) if xs else None


def gmean(xs):
    xs = [x for x in xs if x and x > 0]
    return math.exp(sum(math.log(x) for x in xs) / len(xs)) if xs else None


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("")
        return
    cols = [k for k in rows[0] if not k.startswith("_")]
    for r in rows[1:]:
        cols += [k for k in r if k not in cols and not k.startswith("_")]
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)



def write_snapshots(d: dict[str, Any]) -> list[dict[str, Any]]:
    """Snapshots that directly follow a state-changing command (both harness versions)."""
    return [a["snapshot"] for a in aligned(d, classify) if a["kind"] == "write"]


# ----------------------------------------------------------------------------- figures
def style(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(MUTED)
        ax.spines[s].set_linewidth(0.6)
    ax.tick_params(colors=MUTED, labelsize=7, width=0.6, length=2.5)
    ax.grid(axis="x", color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)


def model_legend(fig, y=1.0):
    handles = [Line2D([], [], marker=M_MARK[m], color=M_COLOR[m], linestyle="", markersize=6, label=l)
               for m, l, _, _ in MODELS]
    handles.append(Line2D([], [], marker="o", markerfacecolor="white", markeredgecolor=MUTED,
                          linestyle="", markersize=6, label="run ended below C = 1.0"))
    fig.legend(handles=handles, loc="upper center", ncol=5, frameon=False, fontsize=7,
               bbox_to_anchor=(0.5, y), labelcolor=INK)


def fig_equal_score_cost(rows, path):
    metrics = [("writes", "state-changing commands", False), ("reads", "read-only commands", False),
               ("wall_time_s", "wall time (s, log)", True), ("tokens", "tokens (log)", True)]
    fig, axes = plt.subplots(len(TASKS), len(metrics), figsize=(7.2, 7.4), sharey=True)
    for i, (tid, tlabel) in enumerate(TASKS):
        for j, (key, xlabel, log) in enumerate(metrics):
            ax = axes[i][j]
            style(ax)
            for yi, (mid, _, color, mk) in enumerate(MODELS):
                mine = sorted([r for r in rows if r["task_id"] == tid and r["model"] == mid], key=lambda r: r["run_id"])
                for k, r in enumerate(mine):
                    # small vertical offset per repeat so identical values stay visible
                    ax.plot(r[key] if not log else max(r[key], 1), yi + (k - 1) * 0.2, marker=mk, linestyle="",
                            markersize=5.5, markeredgewidth=1.0, color=color,
                            markerfacecolor=color if r["complete"] else "white", alpha=0.9)
            if log:
                ax.set_xscale("log")
                vals = [max(r[key], 1) for r in rows if r["task_id"] == tid]
                decades = math.log10(max(vals) / min(vals)) if vals else 0
                subs = (1.0,) if decades > 1.3 else (1.0, 2.0, 5.0)
                ax.xaxis.set_major_locator(LogLocator(base=10, subs=subs))
                ax.xaxis.set_minor_formatter(NullFormatter())
                ax.xaxis.set_major_formatter(FuncFormatter(
                    lambda v, _: f"{v / 1000:g}k" if v >= 1000 else f"{v:g}"))
            ax.set_yticks(range(len(MODELS)))
            ax.set_yticklabels([l for _, l, _, _ in MODELS], fontsize=7, color=INK)
            ax.set_ylim(-0.6, len(MODELS) - 0.4)
            ax.invert_yaxis()
            if i == len(TASKS) - 1:
                ax.set_xlabel(xlabel, fontsize=7, color=INK)
            if j == 0:
                ax.set_title(tlabel, fontsize=8, color=INK, loc="left", x=-0.95, fontweight="bold")
            ok = [r[key] for r in rows if r["task_id"] == tid and r["complete"] and r[key] > 0]
            if len(ok) > 1:
                ax.text(0.98, 0.04, f"{max(ok) / min(ok):.0f}×", transform=ax.transAxes, ha="right",
                        va="bottom", fontsize=6.5, color=MUTED)
    model_legend(fig, 1.005)
    fig.text(0.99, 0.003, "number in each panel = max/min among runs that reached C = 1.0",
             ha="right", fontsize=6, color=MUTED)
    fig.tight_layout(rect=(0, 0.01, 1, 0.965))
    save(fig, path)


def fig_trajectory_cases(runs, path, tasks=("ccnp_multiarea_ospf_intermediate", "ccie_bgp_dual_homing_expert"),
                         mode="labelled"):
    """'labelled': x = state-changing command, one snapshot each (~2 s after it).
    'all': x = command number (reads included), one snapshot after every command; ticks on the
    x-axis baseline mark the state-changing commands."""
    fig, axes = plt.subplots(len(tasks), len(MODELS), figsize=(7.2, 3.9), sharey=True)
    styles = ["-", "--", ":"]
    for i, tid in enumerate(tasks):
        for j, (mid, mlabel, color, mk) in enumerate(MODELS):
            ax = axes[i][j]
            style(ax)
            ax.grid(axis="y", color=GRID, linewidth=0.6)
            mine = sorted([d for d in runs if d["task_id"] == tid and model_of(d) == mid], key=lambda d: d["run_id"])
            for k, d in enumerate(mine):
                if mode == "all":
                    al = aligned(d, classify)
                    traj = [a["snapshot"] for a in al]
                    xs = [a["cmd_index"] + 1 for a in al]
                    for a in al:
                        if a["kind"] == "write":
                            ax.plot(a["cmd_index"] + 1, -0.035 + 0.012 * k, marker="|", color=color,
                                    markersize=3.5, markeredgewidth=0.8, alpha=0.8, clip_on=False)
                else:
                    traj = write_snapshots(d)
                    xs = list(range(1, len(traj) + 1))
                if not traj:
                    continue
                ys = [s["completeness"] for s in traj]
                ax.step(xs, ys, where="post", color=color, linewidth=1.4, linestyle=styles[k % 3], alpha=0.95)
                for x, (a, b) in zip(xs[1:], zip(traj, traj[1:])):
                    if any(v and not b["properties"].get(p) for p, v in a["properties"].items()):
                        ax.plot(x, b["completeness"], marker="x", color=INK, markersize=5,
                                markeredgewidth=1.1, zorder=5)
                term = d["scoring"]["completeness"]
                ax.plot(xs[-1] + (2 if mode == "all" else 1), term, marker=mk, color=color,
                        markerfacecolor=color if term >= 1 - 1e-9 else "white", markersize=5.5,
                        markeredgewidth=1.0, zorder=6)
            ax.set_ylim(-0.05, 1.08)
            if i == 0:
                ax.set_title(mlabel, fontsize=7.5, color=INK)
            if j == 0:
                ax.set_ylabel(f"{TASK_LABEL[tid]}\nfraction of properties met", fontsize=7, color=INK)
            if i == len(tasks) - 1 and mode != "all":
                ax.set_xlabel("state-changing command", fontsize=7, color=INK)
    if mode == "all":
        handles = [Line2D([], [], color=MUTED, linewidth=1.4, label="snapshot after every command"),
                   Line2D([], [], marker="|", color=MUTED, linestyle="", label="state-changing command"),
                   Line2D([], [], marker="x", color=INK, linestyle="", label="property lost"),
                   Line2D([], [], marker="o", color=MUTED, linestyle="", label="end-of-run check (after wait)")]
        ncol = 4
    else:
        handles = [Line2D([], [], color=MUTED, linewidth=1.4, label="per-command snapshot (~2 s after command)"),
                   Line2D([], [], marker="x", color=INK, linestyle="", label="property lost"),
                   Line2D([], [], marker="o", color=MUTED, linestyle="", label="end-of-run check (after convergence wait)")]
        ncol = 3
    fig.legend(handles=handles, loc="upper center", ncol=ncol, frameon=False, fontsize=7, bbox_to_anchor=(0.5, 1.0))
    if mode == "all":
        fig.supxlabel("command number (reads included)", fontsize=7, color=INK, y=0.01)
        fig.tight_layout(rect=(0, 0.03, 1, 0.93))
    else:
        fig.tight_layout(rect=(0, 0, 1, 0.93))
    save(fig, path)


def fig_convergence_lag(lag_rows, path, mode="labelled"):
    rows = [r for r in lag_rows if r["n_runs"] > 0]
    fig, ax = plt.subplots(figsize=(7.2, 0.22 * len(rows) + 0.9))
    style(ax)
    # one hue, three steps (sequential, part-to-whole)
    dark, mid, light = "#2b6cb0", "#7fa8d8", "#d4e2f4"
    ylabels = []
    for y, r in enumerate(rows):
        n = r["n_runs"]
        a = r["n_true_after_last_change"] / n
        b = (r["n_true_by_submit"] - r["n_true_after_last_change"]) / n
        c = 1 - a - b
        ax.barh(y, a, color=dark, height=0.62, edgecolor="white", linewidth=1.0)
        ax.barh(y, b, left=a, color=mid, height=0.62, edgecolor="white", linewidth=1.0)
        ax.barh(y, c, left=a + b, color=light, height=0.62, edgecolor="white", linewidth=1.0)
        label = (f"{r['n_true_after_last_change']}/{r['n_true_by_submit']}/{n}" if mode == "all"
                 else f"{r['n_true_after_last_change']}/{n}")
        ax.text(1.01, y, label, va="center", fontsize=6.5, color=MUTED)
        ylabels.append(f"{TASK_LABEL[r['task_id']]} · {r['property']}")
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels(ylabels, fontsize=6.8, color=INK)
    ax.invert_yaxis()
    ax.set_xlim(0, 1.12)
    ax.set_xlabel("share of successful runs (terminal C = 1.0)", fontsize=7, color=INK)
    if mode == "all":
        handles = [plt.Rectangle((0, 0), 1, 1, color=dark, label="true right after the last change"),
                   plt.Rectangle((0, 0), 1, 1, color=mid, label="became true during the agent's final reads"),
                   plt.Rectangle((0, 0), 1, 1, color=light, label="true only after the convergence wait")]
        ncol = 3
    else:
        handles = [plt.Rectangle((0, 0), 1, 1, color=dark, label="already true at the last per-command snapshot"),
                   plt.Rectangle((0, 0), 1, 1, color=light, label="true only after the convergence wait")]
        ncol = 2
    if mode == "all":
        fig.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, 1.0), ncol=ncol, frameon=False,
                   fontsize=6.8)
        fig.tight_layout(rect=(0, 0, 1, 0.965))
    else:
        ax.legend(handles=handles, loc="lower center", bbox_to_anchor=(0.45, 1.0), ncol=ncol, frameon=False,
                  fontsize=7)
        fig.tight_layout()
    save(fig, path)


def fig_process_fingerprint(rows, path):
    """Rows: models. Columns: behaviours over successful runs. Colour = column-normalised value."""
    ok = [r for r in rows if r["complete"]]
    by_task = defaultdict(list)
    for r in ok:
        by_task[r["task_id"]].append(r)
    cols = [
        ("writes", "state-changing\ncommands", "ratio"), ("reads", "read-only\ncommands", "ratio"),
        ("wall_time_s", "wall time", "ratio"), ("tokens", "tokens", "ratio"),
        ("recon_reads", "reads before\nfirst change", "median"), ("verify_reads", "reads after\nlast change", "median"),
        ("lines_per_write", "config lines\nper command", "median"),
        ("regressions", "properties lost\nmid-run", "sum"), ("disruptive_ops", "disruptive\nactions", "sum"),
        ("hidden_writes", "changes sent\nas reads", "sum"), ("phantom_writes", "reads sent\nas changes", "sum"),
        ("failed_commands", "failed\ncommands", "sum"),
    ]
    table = []
    for mid, _, _, _ in MODELS:
        mine = [r for r in ok if r["model"] == mid]
        row = []
        for key, _, agg in cols:
            if agg == "ratio":  # geometric mean of (run value / task median over all models)
                ratios = [r[key] / med([x[key] for x in by_task[r["task_id"]]]) for r in mine
                          if med([x[key] for x in by_task[r["task_id"]]])]
                row.append(gmean(ratios))
            elif agg == "median":
                row.append(med([r[key] for r in mine]))
            else:
                row.append(sum(r[key] for r in mine))
        table.append(row)
    fig, ax = plt.subplots(figsize=(7.2, 2.9))
    cmap = plt.get_cmap("Blues")
    for j, (key, label, agg) in enumerate(cols):
        vals = [t[j] for t in table]
        lo, hi = min(v for v in vals if v is not None), max(v for v in vals if v is not None)
        for i, v in enumerate(vals):
            norm = 0.0 if hi == lo or v is None else (v - lo) / (hi - lo)
            ax.add_patch(plt.Rectangle((j, i), 0.96, 0.92, color=cmap(0.08 + 0.72 * norm), linewidth=0))
            txt = "-" if v is None else (f"{v:.2f}×" if agg == "ratio" else
                                          f"{v:.0f}" if float(v).is_integer() else f"{v:.1f}")
            ax.text(j + 0.48, i + 0.46, txt, ha="center", va="center", fontsize=6.8,
                    color="white" if norm > 0.6 else INK)
    ax.set_xlim(0, len(cols))
    ax.set_ylim(len(MODELS), 0)
    ax.set_xticks([j + 0.48 for j in range(len(cols))])
    ax.set_xticklabels([c[1].replace("\n", " ") for c in cols], fontsize=6.4, color=INK,
                       rotation=35, ha="left", rotation_mode="anchor")
    ax.xaxis.tick_top()
    ax.set_yticks([i + 0.46 for i in range(len(MODELS))])
    ax.set_yticklabels([l for _, l, _, _ in MODELS], fontsize=7, color=INK)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(length=0)
    for x in (4, 7, 9):
        ax.axvline(x - 0.02, color="white", linewidth=3)
    fig.text(0.01, 0.01, "Successful runs only (C = 1.0). Cost: geometric mean of run / task median (1.00× = typical).\n"
             "Method: median per run. Events: totals over the model's successful runs. Darker = higher within the column.",
             fontsize=6, color=MUTED)
    fig.tight_layout(rect=(0, 0.08, 1, 1))
    save(fig, path)
    return cols, table


def save(fig, path: Path):
    fig.savefig(path.with_suffix(".pdf"))
    fig.savefig(path.with_suffix(".png"), dpi=220)
    plt.close(fig)


# ----------------------------------------------------------------------------- main
def main() -> None:
    global MODELS, M_LABEL, M_COLOR, M_MARK
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--runs-dir", type=Path, default=RUNS_DIR)
    ap.add_argument("--tasks-dir", type=Path, default=TASKS_DIR)
    ap.add_argument("--out-dir", type=Path, default=OUT_DIR)
    ap.add_argument("--paper-dir", type=Path, default=None, help="also copy the PDFs here")
    ap.add_argument("--snapshot-mode", choices=["auto", "all", "labelled"], default="auto",
                    help="harness snapshot policy; auto = 'all' if every run has one snapshot per command")
    ap.add_argument("--models", default=None,
                    help="comma-separated model ids to analyze, e.g. 'openai/gpt-5-mini,meta-llama/llama-3.3-70b-instruct'. "
                         "Each id gets a label, colour and marker automatically; overrides the built-in four.")
    args = ap.parse_args()
    if args.models:
        extra = []
        for mid in [m.strip() for m in args.models.split(",") if m.strip()]:
            label = mid.split("/")[-1].replace("-", " ").replace("_", " ")
            extra.append((mid, label, MODEL_PALETTE[len(extra) % len(MODEL_PALETTE)], MODEL_MARKERS_CYCLE[len(extra) % len(MODEL_MARKERS_CYCLE)]))
        MODELS = extra
        M_LABEL = {m: l for m, l, _, _ in MODELS}
        M_COLOR = {m: c for m, _, c, _ in MODELS}
        M_MARK = {m: k for m, _, _, k in MODELS}
    print(f"MODELS: {MODELS}")
    runs = load_runs(args.runs_dir)
    cohort_mode = set_cohort_mode(runs, args.snapshot_mode)
    print(f"snapshot mode: {cohort_mode}")
    props = task_properties(args.tasks_dir)
    rows = [run_metrics(d) for d in runs]
    write_csv(args.out_dir / "per_run_process.csv", rows)

    # task x model summary
    agg = []
    for tid, _ in TASKS:
        for mid, _, _, _ in MODELS:
            mine = [r for r in rows if r["task_id"] == tid and r["model"] == mid]
            if not mine:
                continue
            row = {"task_id": tid, "model": mid, "runs": len(mine), "complete": sum(r["complete"] for r in mine),
                   "C": "/".join(f"{r['C']:.2f}" for r in mine)}
            for key in ("writes", "reads", "wall_time_s", "tokens", "config_lines", "recon_reads", "verify_reads",
                        "regressions", "disruptive_ops", "hidden_writes", "phantom_writes", "failed_commands",
                        "lag_to_terminal", "thoughts"):
                vals = [r[key] for r in mine if r[key] is not None]
                row[f"{key}_median"] = med(vals)
                row[f"{key}_range"] = f"{min(vals)}-{max(vals)}" if vals else ""
            agg.append(row)
    write_csv(args.out_dir / "by_task_model.csv", agg)

    # spread among equal (perfect) scores
    spread = []
    for tid, _ in TASKS:
        ok = [r for r in rows if r["task_id"] == tid and r["complete"]]
        row = {"task_id": tid, "runs_at_C1": len(ok), "models_at_C1": len({r["model"] for r in ok})}
        for key in ("writes", "reads", "wall_time_s", "tokens", "config_lines"):
            vals = [r[key] for r in ok if r[key] > 0]
            row[f"{key}_min"], row[f"{key}_max"] = (min(vals), max(vals)) if vals else (None, None)
            row[f"{key}_ratio"] = round(max(vals) / min(vals), 1) if len(vals) > 1 else None
        spread.append(row)
    write_csv(args.out_dir / "spread_equal_score.csv", spread)

    write_csv(args.out_dir / "drops.csv", [x for d in runs for x in drop_rows(d)])
    write_csv(args.out_dir / "label_fidelity.csv", [x for d in runs for x in label_rows(d)])
    write_csv(args.out_dir / "designs.csv", [design_row(d) for d in runs if d["scoring"]["completeness"] >= 1 - 1e-9])

    # convergence lag per property (successful runs with at least one snapshot).
    # Three moments: right after the last state change; at submission (last snapshot, which in
    # 'all' mode follows the agent's final reads); after the convergence wait (terminal, C = 1.0).
    # In 'labelled' mode there are no snapshots after reads, so the middle moment is empty and
    # the first one is the last snapshot, as in the original analysis.
    lag = []
    for tid, _ in TASKS:
        ok = [d for d in runs if d["task_id"] == tid and d["scoring"]["completeness"] >= 1 - 1e-9
              and aligned(d, classify)]
        for p in props.get(tid, []):
            n_write = n_submit = 0
            for d in ok:
                al = aligned(d, classify)
                if snapshot_mode(d) == "all":
                    wsn = [a for a in al if a["kind"] == "write"]
                    after_write = wsn[-1] if wsn else al[0]
                else:
                    after_write = al[-1]
                at_write = bool(after_write["properties"].get(p))
                at_submit = bool(al[-1]["properties"].get(p))
                n_write += at_write
                n_submit += at_write or at_submit
            n = len(ok)
            lag.append({"task_id": tid, "property": p, "n_runs": n,
                        "n_true_after_last_change": n_write,
                        "n_true_by_submit": n_submit,
                        "n_true_only_after_wait": n - n_submit,
                        "share_true_after_last_change": round(n_write / n, 3) if n else 0.0,
                        "share_true_by_submit": round(n_submit / n, 3) if n else 0.0})
    write_csv(args.out_dir / "lag_by_property.csv", lag)

    fig_equal_score_cost(rows, args.out_dir / "fig_equal_score_cost")
    fig_trajectory_cases(runs, args.out_dir / "fig_trajectory_cases", mode=cohort_mode)
    fig_convergence_lag(lag, args.out_dir / "fig_convergence_lag", cohort_mode)
    cols, table = fig_process_fingerprint(rows, args.out_dir / "fig_process_fingerprint")
    write_csv(args.out_dir / "fingerprint.csv",
              [{"model": M_LABEL[mid], **{c[0]: (round(v, 3) if v is not None else None) for c, v in zip(cols, t)}}
               for (mid, _, _, _), t in zip(MODELS, table)])

    if args.paper_dir:
        import shutil
        for name in ("fig_equal_score_cost", "fig_trajectory_cases", "fig_convergence_lag", "fig_process_fingerprint"):
            shutil.copy(args.out_dir / f"{name}.pdf", args.paper_dir / f"{name}.pdf")

    n_ok = sum(r["complete"] for r in rows)
    print(f"{len(rows)} runs; {n_ok} reached C = 1.0; outputs in {args.out_dir}")


if __name__ == "__main__":
    main()
