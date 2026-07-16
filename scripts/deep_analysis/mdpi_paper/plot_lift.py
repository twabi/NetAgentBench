import json
from pathlib import Path
import collections
import numpy as np
import matplotlib.pyplot as plt
import sys

sys.path.insert(0, "/home/grimm/python_projects/benchmark/src")
sys.path.insert(0, "/home/grimm/python_projects/benchmark/scripts")
from deep_analysis.run_loader import load_and_enrich

data_dir = Path("/home/grimm/python_projects/benchmark/results/comparatives_all")
runs = load_and_enrich(data_dir)

tasks = [
    "ccna_rip_routing_basic",
    "troubleshoot_ospf_adjacency_issue",
    "ccnp_multiarea_ospf_intermediate",
    "troubleshoot_bgp_route_filtering",
    "ccie_bgp_dual_homing_expert"
]
labels = ['RIP', 'OSPF Adj', 'OSPF MA', 'BGP RF', 'BGP Dual']
patterns = ['sequential', 'debate', 'group_chat', 'concurrent']

# Group by task -> pattern -> model -> scores
scores = collections.defaultdict(lambda: collections.defaultdict(lambda: collections.defaultdict(list)))

for d in runs:
    task = d["task_id"]
    if task not in tasks: continue
    pat = d.get("_pattern", "UNKNOWN")
    mod = d.get("_model", "UNKNOWN")
    score = d.get("scoring", {}).get("final_score", 0)
    scores[task][pat][mod].append(score)

def get_balanced_mean(pat_data):
    # pat_data is dict: mod -> list of scores
    means = [np.mean(vals) for vals in pat_data.values() if vals]
    return np.mean(means) if means else 0

def bootstrap_lift(single_data, pat_data, n_boot=10000):
    np.random.seed(42)
    models = list(single_data.keys())
    lifts = []
    for _ in range(n_boot):
        m_single = []
        m_pat = []
        for mod in models:
            s_vals = single_data.get(mod, [])
            p_vals = pat_data.get(mod, [])
            if s_vals: m_single.append(np.mean(np.random.choice(s_vals, len(s_vals), replace=True)))
            if p_vals: m_pat.append(np.mean(np.random.choice(p_vals, len(p_vals), replace=True)))
        lift = (np.mean(m_pat) if m_pat else 0) - (np.mean(m_single) if m_single else 0)
        lifts.append(lift)
    lifts = np.array(lifts)
    return np.percentile(lifts, 2.5), np.percentile(lifts, 97.5)

lifts_dict = {p: [] for p in patterns}
err_low = {p: [] for p in patterns}
err_hi = {p: [] for p in patterns}

for task in tasks:
    single_data = scores[task]["single"]
    single_mean = get_balanced_mean(single_data)
    for pat in patterns:
        pat_data = scores[task][pat]
        pat_mean = get_balanced_mean(pat_data)
        lift = pat_mean - single_mean
        lo, hi = bootstrap_lift(single_data, pat_data, 10000)
        
        lifts_dict[pat].append(lift)
        err_low[pat].append(lift - lo)
        err_hi[pat].append(hi - lift)

x = np.arange(len(tasks))
width = 0.2

fig, ax = plt.subplots(figsize=(10, 5))
colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728']
pattern_labels = ['Sequential', 'Debate', 'Group Chat', 'Concurrent']

for i, pat in enumerate(patterns):
    pos = x - 1.5*width + i*width
    yerr = [err_low[pat], err_hi[pat]]
    ax.bar(pos, lifts_dict[pat], width, yerr=yerr, label=pattern_labels[i], color=colors[i], capsize=4, alpha=0.9)

ax.axhline(0, color='black', linewidth=1)
ax.set_ylabel('Model-Balanced Mean Pattern Lift')
ax.set_title('Pattern Lift Relative to Single-Agent Baseline by Task')
ax.set_xticks(x)
ax.set_xticklabels(labels)
ax.legend()

plt.tight_layout()
plt.savefig('/home/grimm/Documents/papers/mdpi_decentralized_paper/images/fig_pattern_lift.png', dpi=300)
